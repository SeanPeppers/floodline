"""Compound flood model: Key West storm tide (flood.py) correlated with Key West 24-hour
rainfall (rainfall.py) via a discretized Gaussian copula, plus the joint state-prep circuit.

What's real and measured: both marginals.
  - Tide: NOAA CO-OPS station 8724580, annual maxima for the 110 years of 1913-2025 with at
    least 10 months of data, GEV fit (flood.py).
  - Rain: NOAA Atlas 14 published 24-hour annual-maximum-series return-period depths for the
    same grid point, GEV fit to those 9 published points (rainfall.py).

What's a modeling ASSUMPTION, not measured: the correlation between them.
  - Wahl et al. 2015 (Nature Climate Change, doi:10.1038/nclimate2736) found statistically
    significant compound dependence between storm surge and precipitation at virtually all
    Gulf/east coast sites, including the Key West gauge per their Fig. 1b. That SIGN and
    SIGNIFICANCE claim is real and cited. Their variables (daily surge vs daily rain) differ
    from ours (annual-max total water level vs annual-max 24-h rain).
  - The exact tau magnitude at Key West is only in their Figure 1 (a plot), not an extractable
    table number, so TAU_ASSUMED is an ASSUMPTION: a representative moderate positive value.

Flood rules. Both are written as a separable integer test a[tide_bin] + b[rain_bin] >= 0, so one
circuit (a reversible adder into a two's-complement register, then its sign bit) serves both:
  - "rectangle": tide >= NWS minor stage AND rain >= 10-yr depth (a, b in {-1, 0}).
  - "realistic": drainage.py's low-street stage model (tide backflow throttles drainage, rain
    runoff by SCS curve number, 6-inch flood depth), whose boundary is a curved staircase.

No closed-form joint CDF is ever handed to either estimator. The circuit loads the tide
marginal, reads a coarse tide "regime" from its top qubits, and controlled-loads one of
N_REGIMES conditional rain distributions -- a discretized Rosenblatt/copula construction. The
classical estimators sample from this exact same discretized generative model and evaluate the
exact same integer flood test.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import DiagonalGate, QFTGate, StatePreparation
from scipy import stats

import drainage
import flood
import rainfall

TAU_ASSUMED = 0.3  # ASSUMPTION, NOT MEASURED -- see module docstring
RHO = float(np.sin(np.pi * TAU_ASSUMED / 2))  # Kendall tau -> Gaussian copula rho (Nelsen 2006, standard identity)
N_REGIMES = 4  # tide's top-2-qubit quartiles gate which conditional rain distribution loads
TIDE_THRESHOLD_KEY = "nws_minor"  # rectangle rule's tide threshold
RULES = ("rectangle", "realistic")


def _tide_regime_quantiles(tide_probs: np.ndarray) -> np.ndarray:
    """Midpoint cumulative-probability quantile of each of the N_REGIMES contiguous blocks of
    tide bins (regime = the top log2(N_REGIMES) bits of the tide bin index)."""
    n = len(tide_probs)
    block = n // N_REGIMES
    cdf = np.concatenate([[0.0], np.cumsum(tide_probs)])
    return np.array([0.5 * (cdf[r * block] + cdf[(r + 1) * block]) for r in range(N_REGIMES)])


def conditional_rain_probs(tide_probs: np.ndarray, gev: dict) -> np.ndarray:
    """(N_REGIMES, 2**rainfall.N_QUBITS): rain-bin probabilities conditional on each tide
    regime, under the Gaussian copula with correlation RHO."""
    z1 = stats.norm.ppf(np.clip(_tide_regime_quantiles(tide_probs), 1e-9, 1 - 1e-9))
    g_edges = np.clip(stats.genextreme.cdf(rainfall.edges(), gev["c"], gev["loc"], gev["scale"]), 1e-9, 1 - 1e-9)
    z2_edges = stats.norm.ppf(g_edges)
    rows = []
    for z1r in z1:
        cond_z2 = (z2_edges - RHO * z1r) / np.sqrt(1 - RHO**2)
        rows.append(np.diff(np.concatenate([[0.0], stats.norm.cdf(cond_z2), [1.0]])))
    return np.array(rows)


def regimes(n_tide: int, n_regimes: int) -> np.ndarray:
    return np.minimum(np.arange(n_tide) // (n_tide // n_regimes), n_regimes - 1)


def hit_mask(a_tab: np.ndarray, b_tab: np.ndarray) -> np.ndarray:
    return a_tab[:, None] + b_tab[None, :] >= 0


def true_a(tide_probs: np.ndarray, cond_rain_probs: np.ndarray, mask: np.ndarray) -> float:
    """Exact P(flood) under the discretized joint model: sum over cells of P(tide bin) *
    P(rain bin | that bin's regime) * mask. Closed-form over the grid the circuit loads."""
    joint = tide_probs[:, None] * cond_rain_probs[regimes(len(tide_probs), cond_rain_probs.shape[0])]
    return float((joint * mask).sum())


def rule_tables(rule: str, tide_t: int, rain_t: int) -> dict:
    """Integer tables (a per tide bin, b per rain bin) for flood <=> a + b >= 0."""
    if rule == "rectangle":
        a = np.where(np.arange(2**flood.N_QUBITS) >= tide_t, 0, -1)
        b = np.where(np.arange(2**rainfall.N_QUBITS) >= rain_t, 0, -1)
        return {"a": a, "b": b, "unit_ft": None}
    if rule == "realistic":
        return drainage.integer_tables()
    raise ValueError(f"unknown rule {rule!r}; pick one of {RULES}")


def sum_bits(a_tab: np.ndarray, b_tab: np.ndarray) -> int:
    """Two's-complement width holding every a + b without wrapping."""
    lo, hi = int(a_tab.min() + b_tab.min()), int(a_tab.max() + b_tab.max())
    m = 1
    while not (-(2 ** (m - 1)) <= lo and hi <= 2 ** (m - 1) - 1):
        m += 1
    return m


def problem(rule: str = "realistic") -> dict:
    """Everything the joint experiment needs: both marginals, the conditional rain tables, and
    the flood rule as integer tables."""
    tide = flood.problem()
    rain = rainfall.problem()
    tide_t = flood.threshold_index(tide["thresholds_m_above_mhhw"][TIDE_THRESHOLD_KEY])
    rain_t = rain["threshold_bin"]
    cond = conditional_rain_probs(tide["probs"], rain["gev"])
    tab = rule_tables(rule, tide_t, rain_t)
    mask = hit_mask(tab["a"], tab["b"])
    return {
        "rule": rule, "tide": tide, "rain": rain, "tide_threshold_bin": tide_t, "rain_threshold_bin": rain_t,
        "tau_assumed": TAU_ASSUMED, "rho": RHO, "n_regimes": N_REGIMES, "conditional_rain_probs": cond,
        "a_tab": tab["a"], "b_tab": tab["b"], "unit_ft": tab["unit_ft"], "mask": mask,
        "tide_alone": float(tide["probs"][tide_t:].sum()), "a_true": true_a(tide["probs"], cond, mask),
    }  # fmt: skip


def _add_table(qc: QuantumCircuit, table: np.ndarray, data: list[int], acc: list[int], sign: int) -> None:
    """In the Fourier basis of acc (m qubits), add sign*table[x] for data register value x: for
    each acc bit k, a diagonal phase exp(2 pi i table[x] 2^k / 2^m) on (data, acc[k]) -- the
    Draper adder generalized from one constant to an arbitrary integer function of a register."""
    m = len(acc)
    for k, q in enumerate(acc):
        ph = np.exp(2j * np.pi * sign * table * 2**k / 2**m)
        qc.append(DiagonalGate(np.concatenate([np.ones(len(table)), ph]).tolist()), data + [q])


def state_prep(
    tide_probs: np.ndarray, cond_rain_probs: np.ndarray, a_tab: np.ndarray, b_tab: np.ndarray
) -> QuantumCircuit:
    """Builds A: entangled tide+rain joint state prep (discretized Gaussian copula), then the
    flood oracle: S = a[tide] + b[rain] computed into an m-qubit two's-complement register with
    a QFT (Draper) adder, obj = NOT sign(S), adder uncomputed so acc returns to |0>.
    Layout [tide (n_t) | rain (n_r) | obj | acc (m)]: qae.grover reflects about range(obj + 1),
    and acc is clean after A, exactly as the comparator ancillas were before."""
    n_t = int(np.log2(len(tide_probs)))
    n_r = int(np.log2(cond_rain_probs.shape[1]))
    reg_bits = int(np.log2(cond_rain_probs.shape[0]))
    tide, rain = list(range(n_t)), list(range(n_t, n_t + n_r))
    orc = flood_oracle(a_tab, b_tab)
    qc = QuantumCircuit(orc.num_qubits, name="A", metadata=orc.metadata)
    qc.append(StatePreparation(np.sqrt(tide_probs)), tide)
    reg_qubits = tide[-reg_bits:]  # top bits of the tide bin index = coarse tide regime
    for r in range(cond_rain_probs.shape[0]):
        qc.append(StatePreparation(np.sqrt(cond_rain_probs[r])).control(reg_bits, ctrl_state=r), reg_qubits + rain)
    qc.compose(orc, inplace=True)
    return qc


def flood_oracle(a_tab: np.ndarray, b_tab: np.ndarray) -> QuantumCircuit:
    """|x>|y>|0>|0^m> -> |x>|y>|[a[x] + b[y] >= 0]>|0^m> on [tide | rain | obj | acc]."""
    n_t, n_r = int(np.log2(len(a_tab))), int(np.log2(len(b_tab)))
    m = sum_bits(a_tab, b_tab)
    tide, rain = list(range(n_t)), list(range(n_t, n_t + n_r))
    obj = n_t + n_r
    acc = list(range(obj + 1, obj + 1 + m))
    qc = QuantumCircuit(obj + 1 + m, name="flood", metadata={"obj": obj, "acc_bits": m})
    qc.h(acc)  # = QFT|0>
    _add_table(qc, a_tab, tide, acc, +1)
    _add_table(qc, b_tab, rain, acc, +1)
    qc.append(QFTGate(m).inverse(), acc)  # acc = |S mod 2^m>
    qc.cx(acc[-1], obj)  # sign bit: 1 iff S < 0
    qc.x(obj)
    qc.append(QFTGate(m), acc)
    _add_table(qc, b_tab, rain, acc, -1)
    _add_table(qc, a_tab, tide, acc, -1)
    qc.h(acc)
    return qc


def compound_hits(
    tide_probs: np.ndarray, cond_rain_probs: np.ndarray, mask: np.ndarray, u1: np.ndarray, u2: np.ndarray
) -> np.ndarray:
    """Vectorized honest classical draw from the SAME discretized generative model the circuit
    encodes: u1 picks a tide bin from the marginal CDF, u2 picks a rain bin from the regime-
    conditional CDF for that draw's tide regime, then the SAME integer flood test (as a mask).
    u1, u2 in [0, 1) -- iid uniforms for plain MC, or a 2-D Sobol point for QMC."""
    tide_bin = np.minimum(np.searchsorted(np.cumsum(tide_probs), u1, side="right"), len(tide_probs) - 1)
    regime = regimes(len(tide_probs), cond_rain_probs.shape[0])[tide_bin]
    rain_cdf_table = np.cumsum(cond_rain_probs, axis=1)
    rain_bin = np.minimum((rain_cdf_table[regime] < u2[:, None]).sum(axis=1), cond_rain_probs.shape[1] - 1)
    return mask[tide_bin, rain_bin]


if __name__ == "__main__":
    for rule in RULES:
        p = problem(rule)
        a_circ = state_prep(p["tide"]["probs"], p["conditional_rain_probs"], p["a_tab"], p["b_tab"])
        print(f"{rule}: a_true={p['a_true']:.5f} tide_alone(minor)={p['tide_alone']:.4f} "
              f"qubits={a_circ.num_qubits} acc_bits={a_circ.metadata['acc_bits']}")  # fmt: skip
