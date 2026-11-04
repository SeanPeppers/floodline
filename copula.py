"""Compound flood model: Key West storm tide (flood.py) correlated with Key West 24-hour
rainfall (rainfall.py) via a discretized Gaussian copula, plus the joint state-prep circuit.

What's real and measured: both marginals.
  - Tide: NOAA CO-OPS station 8724580, 110 years of annual maxima, GEV fit (flood.py,
    unchanged from the single-variable build).
  - Rain: NOAA Atlas 14 published 24-hour annual-maximum-series return-period depths for the
    same grid point, Gumbel fit to those 9 published points (rainfall.py).

What's a modeling ASSUMPTION, not measured: the correlation between them.
  - Wahl et al. 2015 (Nature Climate Change, doi:10.1038/nclimate2736) directly studied Key
    West (their tide gauge #17, with 8 precipitation stations in a 25 km radius) and found a
    statistically significant POSITIVE Kendall's-tau dependence between storm surge and
    precipitation extremes at "virtually all sites along the Gulf and east coast" in their
    Case I analysis, Key West included. That SIGN and SIGNIFICANCE claim is real and cited.
  - The exact tau magnitude they measured at Key West is reported only in their Figure 1 (a
    plot), not as an extractable table number, so the magnitude used below (TAU_ASSUMED) is
    an ASSUMPTION: a representative moderate positive value, not Key West's measured number.

No closed-form joint CDF is ever handed to either estimator. The circuit below builds the
joint distribution structurally: it loads the tide marginal, reads off a coarse tide "regime"
from its top qubits, and controlled-loads one of N_REGIMES conditional rain distributions
depending on that regime -- a discretized Rosenblatt/copula construction, not a flat
2**(n_tide+n_rain)-entry precomputed joint array. The classical estimators in experiment.py
sample from this exact same discretized generative model (draw a tide bin, then a rain bin
conditioned on its regime) -- never by inverting a 2-D joint CDF.
"""

from __future__ import annotations

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import IntegerComparatorGate, StatePreparation
from scipy import stats

import flood
import rainfall

TAU_ASSUMED = 0.3  # ASSUMPTION, NOT MEASURED -- see module docstring
RHO = float(np.sin(np.pi * TAU_ASSUMED / 2))  # Kendall tau -> Gaussian copula rho (Nelsen 2006, standard identity)
N_REGIMES = 4  # tide's top-2-qubit quartiles gate which conditional rain distribution loads
TIDE_THRESHOLD_KEY = "nws_minor"  # compound event: coastal flooding alone at NWS *minor* stage
# plus rain heavy enough to matter, since real-world compound-flood case studies pair modest
# coastal flooding with heavy rainfall (one driver alone wouldn't be "compound"). A modeling
# choice, not an official joint NWS/FEMA standard -- there isn't one.


def _tide_regime_quantiles(tide_probs: np.ndarray) -> np.ndarray:
    """Midpoint cumulative-probability quantile of each of the N_REGIMES contiguous blocks of
    tide bins (regime = the top log2(N_REGIMES) bits of the tide bin index)."""
    n = len(tide_probs)
    block = n // N_REGIMES
    cdf = np.concatenate([[0.0], np.cumsum(tide_probs)])
    return np.array([0.5 * (cdf[r * block] + cdf[(r + 1) * block]) for r in range(N_REGIMES)])


def conditional_rain_probs(tide_probs: np.ndarray, rain_loc: float, rain_scale: float) -> np.ndarray:
    """(N_REGIMES, 2**rainfall.N_QUBITS): rain-bin probabilities conditional on each tide
    regime, under the Gaussian copula with correlation RHO."""
    u1 = np.clip(_tide_regime_quantiles(tide_probs), 1e-9, 1 - 1e-9)
    z1 = stats.norm.ppf(u1)
    n = 2**rainfall.N_QUBITS
    edges = rainfall.GRID_LO + rainfall.BIN_W * np.arange(1, n)
    g_edges = np.clip(stats.gumbel_r.cdf(edges, rain_loc, rain_scale), 1e-9, 1 - 1e-9)
    z2_edges = stats.norm.ppf(g_edges)
    rows = []
    for z1r in z1:
        cond_z2 = (z2_edges - RHO * z1r) / np.sqrt(1 - RHO**2)
        cond_cdf = np.concatenate([[0.0], stats.norm.cdf(cond_z2), [1.0]])
        rows.append(np.diff(cond_cdf))
    return np.array(rows)


def true_a(tide_probs: np.ndarray, cond_rain_probs: np.ndarray, tide_t: int, rain_t: int) -> float:
    """Exact P(tide >= tide_t AND rain >= rain_t) under the discretized joint model: sum over
    tide bins at or past the threshold of tide_probs[bin] * (that bin's regime's conditional
    rain tail). Closed-form over the same finite grid the circuit loads -- no sampling."""
    n = len(tide_probs)
    block = n // cond_rain_probs.shape[0]
    rain_tail = cond_rain_probs[:, rain_t:].sum(axis=1)
    regimes = np.minimum(np.arange(n) // block, cond_rain_probs.shape[0] - 1)
    return float((tide_probs[tide_t:] * rain_tail[regimes[tide_t:]]).sum())


def problem() -> dict:
    """Everything the joint experiment needs: both marginals, the conditional rain tables,
    and the two threshold bins."""
    tide = flood.problem()
    rain = rainfall.problem()
    tide_t = flood.threshold_index(tide["thresholds_m_above_mhhw"][TIDE_THRESHOLD_KEY])
    rain_t = rain["threshold_bin"]
    cond = conditional_rain_probs(tide["probs"], rain["gumbel"]["loc"], rain["gumbel"]["scale"])
    return {
        "tide": tide, "rain": rain, "tide_threshold_bin": tide_t, "rain_threshold_bin": rain_t,
        "tau_assumed": TAU_ASSUMED, "rho": RHO, "n_regimes": N_REGIMES, "conditional_rain_probs": cond,
        "a_true": true_a(tide["probs"], cond, tide_t, rain_t),
    }  # fmt: skip


def state_prep(tide_probs: np.ndarray, cond_rain_probs: np.ndarray, tide_t: int, rain_t: int) -> QuantumCircuit:
    """Builds A: entangled tide+rain joint state prep (discretized Gaussian copula) followed by
    a compound comparator that flips the objective qubit iff tide_bin >= tide_t AND
    rain_bin >= rain_t. Qubit layout mirrors qae.state_prep's pattern (logical qubits first,
    ancillas trailing) so qae.grover/circuit/schedule/mlae/exact_hit_probs all work unchanged:
    [tide_data (n_t) | rain_data (n_r) | tide_hit | rain_hit | obj | tide_anc (n_t-1) | rain_anc (n_r-1)]
    """
    n_t = int(np.log2(len(tide_probs)))
    n_r = int(np.log2(cond_rain_probs.shape[1]))
    reg_bits = int(np.log2(cond_rain_probs.shape[0]))

    tide_data = list(range(n_t))
    rain_data = list(range(n_t, n_t + n_r))
    tide_hit = n_t + n_r
    rain_hit = tide_hit + 1
    obj = rain_hit + 1
    total = obj + 1 + (n_t - 1) + (n_r - 1)

    qc = QuantumCircuit(total, name="A", metadata={"obj": obj})
    qc.append(StatePreparation(np.sqrt(tide_probs)), tide_data)

    reg_qubits = tide_data[-reg_bits:]  # top bits of the tide bin index = coarse tide regime
    for r in range(cond_rain_probs.shape[0]):
        prep = StatePreparation(np.sqrt(cond_rain_probs[r])).control(reg_bits, ctrl_state=r)
        qc.append(prep, reg_qubits + rain_data)

    qc.append(IntegerComparatorGate(n_t, tide_t, geq=True), tide_data + [tide_hit])
    qc.append(IntegerComparatorGate(n_r, rain_t, geq=True), rain_data + [rain_hit])
    qc.ccx(tide_hit, rain_hit, obj)
    return qc


def compound_hits(
    tide_probs: np.ndarray, cond_rain_probs: np.ndarray, tide_t: int, rain_t: int, u1: np.ndarray, u2: np.ndarray
) -> np.ndarray:
    """Vectorized honest classical draw from the SAME discretized generative model the circuit
    encodes: u1 picks a tide bin from the marginal CDF, u2 picks a rain bin from the regime-
    conditional CDF for that draw's tide regime. u1, u2 in [0, 1) -- iid uniforms for plain MC,
    or the two coordinates of a low-discrepancy (Sobol) point for QMC. No joint CDF inversion."""
    n_regimes = cond_rain_probs.shape[0]
    tide_cdf = np.cumsum(tide_probs)
    tide_bin = np.searchsorted(tide_cdf, u1, side="right")
    block = len(tide_probs) // n_regimes
    regime = np.minimum(tide_bin // block, n_regimes - 1)
    rain_cdf_table = np.cumsum(cond_rain_probs, axis=1)
    rain_bin = (rain_cdf_table[regime] < u2[:, None]).sum(axis=1)
    return (tide_bin >= tide_t) & (rain_bin >= rain_t)


if __name__ == "__main__":
    p = problem()
    print("tide a (marginal) =", p["tide"]["a_true"], "tide_threshold_bin =", p["tide_threshold_bin"])
    print("rain threshold_bin =", p["rain_threshold_bin"], "rho =", p["rho"])
    print("conditional_rain_probs:\n", p["conditional_rain_probs"])
    a_circ = state_prep(
        p["tide"]["probs"], p["conditional_rain_probs"], p["tide_threshold_bin"], p["rain_threshold_bin"]
    )
    print("circuit qubits:", a_circ.num_qubits, "obj:", a_circ.metadata["obj"])
