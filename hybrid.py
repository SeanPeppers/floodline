"""Hybrid classical-quantum estimator for the five-driver model, plus a swappable estimator engine.

The split (README_hybrid.md explains every choice and what it buys):
  classical  conditional MC's analytic step: the 3-h burst P3 is integrated exactly, so the
             remaining integrand p(x) = P(flood | W, P24, S, O) is a number in [0, 1] per cell.
             R_int is monotone in the P3 bin, so p depends on x only through
             (p24, g >> g_drop, t = T_int[c, g]): one 2**(n_p24 + n_gr + n_k) lookup table `ptab`.
             The tide-alone region needs no special case: t = 0 there, and ptab[., ., 0] = 1.
  classical  a control variate g(x) = p at the midpoint of x's coarse cell (`drop` low bits per
             driver removed) and its exact mean, one table read per coarse cell.
  quantum    the mean of the residual r(x) = p(x) - g(x) in [-1, 1]. Amplitude encoding of a
             [-1, 1] variable pays for its range, not its spread, and r does reach +-1 (coarse
             cells straddle jumps of the drainage threshold). So r is cut into dyadic layers
             (a layer cake: |r| = sum_j clip(|r| - c_j, 0, c_{j+1} - c_j), cuts 0, 2**-(L-1), ..., 1/2, 1,
             separately for r > 0 and r < 0). Each layer is a [0, 1] variable with its own MLAE
             run; the queries are split across layers by the optimal (sigma_k)**(2/3) rule. This
             is a few-level version of Montanaro's variance-adaptive estimator (arXiv:1504.06987).
p and g are carried on the circuit as b-bit fixed point (P = round(p * (2**b - 1))). The CV mean
uses the same rounded g, so only p's rounding biases the answer (|bias| <= 2**-(b+1));
`exact_parts` reports the actual bias.

Engine: estimate(cfg, eps, backend) with backend "classical" (CMC + Sobol, production),
"quantum-sim" (the hybrid circuit on Aer, reduced grid only) or "quantum-resource" (counts only).
"""

from __future__ import annotations

import itertools
import math
import time
from dataclasses import dataclass, replace
from typing import Any

import numpy as np
from scipy.stats import qmc

import multidriver as md
import qae

BITS = 14  # fixed-point bits of p and g on the circuit; worst-case bias 3e-5, measured ~1e-5
PILOT_LOG2 = 10  # Sobol pilot that picks the layer count and the shot split
MAX_LAYERS = 6
MAX_SIM_QUBITS = 22  # statevector limit on this 15 GB machine with other jobs running
# Coarse-grid menu for the control variate at the benchmark resolution (bits dropped per driver).
# W and P24 never drop past their copula regime bits, so the coarse point shares x's conditional rows.
DROPS = {"1k": {"W": 3, "P24": 2, "S": 2, "O": 1}, "8k": {"W": 2, "P24": 1, "S": 1, "O": 1},
         "16k": {"W": 1, "P24": 1, "S": 1, "O": 1}, "64k": {"W": 1, "P24": 0, "S": 1, "O": 0}}  # fmt: skip
# MLAE constant on this repo's estimator (100 shots per power): RMSE ~= MLAE_K * sqrt(a(1-a)) / queries.
# Measured by experiment_hybrid.py (results_hybrid.json, "mlae_k"): 17.75 at 3.0 ft, 17.37 at 6.0 ft.
MLAE_K = 17.5
TOFFOLI_S = 170e-6  # Babbush et al. arXiv:2011.04149: ~170 us per Toffoli (surface code, d = 30, 1 us cycle)


# ----------------------------------------------------------------------------- tables


def ptab(m: md.Model) -> np.ndarray:
    """p[p24, g >> g_drop, t] = P(flood | P24 bin, coarse groundwater, threshold t), P3 integrated."""
    if m.leaf != "P3":
        raise ValueError("the hybrid integrates the 3-h burst exactly, so it needs all five drivers")
    n24, _, ngr = m.R.shape
    nt = 2**m.cfg.n_k
    cdf3 = np.concatenate([np.zeros((m.cond_p3.shape[0], 1)), np.cumsum(m.cond_p3, 1)], 1)
    reg24 = np.arange(n24) >> (m.cfg.n_p24 - m.cfg.regime_bits)
    out = np.empty((n24, ngr, nt))
    for i in range(n24):
        for j in range(ngr):
            k = np.searchsorted(m.R[i, :, j], np.arange(nt), side="left")  # first P3 bin with R >= t
            out[i, j] = 1 - cdf3[reg24[i], k]
    return np.clip(out, 0.0, 1.0)


def _coarsen(b: dict[str, np.ndarray], drop: dict[str, int]) -> dict[str, np.ndarray]:
    out = dict(b)
    for k, d in drop.items():
        if d:
            out[k] = ((b[k] >> d) << d) + (1 << (d - 1))
    return out


def check_drop(m: md.Model, drop: dict[str, int]) -> None:
    r = m.cfg.regime_bits
    if drop["W"] > m.nbits["W"] - r or drop["P24"] > m.nbits["P24"] - r:
        raise ValueError("W and P24 may only drop bits below their copula regime bits")
    if drop["S"] > m.nbits["S"] or drop["O"] > m.nbits["O"] or min(drop.values()) < 0:
        raise ValueError(f"bad coarse drop {drop}")


@dataclass
class Tables:
    """Everything the hybrid needs from one model, in fixed point with scale S = 2**bits - 1."""

    m: md.Model
    bits: int
    drop: dict[str, int]
    p: np.ndarray  # ptab
    pq: np.ndarray  # round(ptab * S)
    gq: np.ndarray  # [o_c, s_c, p24_c, w_c] round(g * S); C-order flatten = the circuit's QROM address
    scale: int

    def _t(self, b: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
        g = b["S"] + b["O"]
        return g >> self.m.g_shift, self.m.T[b["W"] + b["S"], g]

    def p_of(self, b: dict[str, np.ndarray]) -> np.ndarray:
        return self.p[(b["P24"], *self._t(b))]

    def pq_of(self, b: dict[str, np.ndarray]) -> np.ndarray:
        return self.pq[(b["P24"], *self._t(b))]

    def gq_of(self, b: dict[str, np.ndarray]) -> np.ndarray:
        d = self.drop
        return self.gq[b["O"] >> d["O"], b["S"] >> d["S"], b["P24"] >> d["P24"], b["W"] >> d["W"]]

    def residual(self, b: dict[str, np.ndarray]) -> np.ndarray:
        """Integer residual Pq - Gq in [-S, S]."""
        return self.pq_of(b) - self.gq_of(b)

    @property
    def coarse_cells(self) -> int:
        return int(self.gq.size)


def tables(m: md.Model, drop: dict[str, int], bits: int = BITS) -> Tables:
    check_drop(m, drop)
    p = ptab(m)
    s = 2**bits - 1
    sizes = [2 ** (m.nbits[k] - drop[k]) for k in ("O", "S", "P24", "W")]
    oc, sc, pc, wc = np.meshgrid(*(np.arange(n) for n in sizes), indexing="ij")
    rep = _coarsen({"W": wc << drop["W"], "P24": pc << drop["P24"], "S": sc << drop["S"], "O": oc << drop["O"]}, drop)
    t = Tables(m, bits, dict(drop), p, np.rint(p * s).astype(np.int64), np.zeros(oc.shape, np.int64), s)
    t.gq = np.rint(t.p_of(rep) * s).astype(np.int64)
    return t


# ----------------------------------------------------------------------------- exact pieces


def nonleaf_cells(m: md.Model) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Every (W, P24, S, O) cell and its probability: the enumeration baseline (2**18 at benchmark)."""
    names = m.nonleaf()
    sizes = [2 ** m.nbits[x] for x in names]
    idx = np.arange(int(np.prod(sizes)))
    b: dict[str, np.ndarray] = {}
    for name, size in zip(reversed(names), reversed(sizes)):
        b[name], idx = idx % size, idx // size
    w = m.pmf_w[b["W"]] * m.pmf_s[b["S"]] * m.pmf_o[b["O"]] * m.cond_p24[m._regime(b["W"], m.cfg.n_w), b["P24"]]
    return b, w


def _block(pmf: np.ndarray, drop: int) -> np.ndarray:
    return pmf.reshape(-1, 2**drop).sum(-1)


def cv_mean(t: Tables) -> float:
    """Exact E[Gq] / S from the coarse cells alone: one table read per coarse cell. Coarse-cell
    masses factor because W's coarse blocks never split a copula regime."""
    m, d = t.m, t.drop
    mw = _block(m.pmf_w, d["W"])
    reg = np.arange(len(mw)) >> (m.cfg.n_w - d["W"] - m.cfg.regime_bits)
    m24 = m.cond_p24.reshape(len(m.cond_p24), -1, 2 ** d["P24"]).sum(-1)[reg]  # [w_c, p24_c]
    ms, mo = _block(m.pmf_s, d["S"]), _block(m.pmf_o, d["O"])
    mass = mo[:, None, None, None] * ms[None, :, None, None] * (m24 * mw[:, None]).T[None, None]
    return float((mass * t.gq).sum()) / t.scale


def exact_parts(t: Tables) -> dict[str, float]:
    """Full-enumeration truth for every piece (validation only: this is the 2**18 cost)."""
    b, w = nonleaf_cells(t.m)
    p, r = t.p_of(b), t.residual(b) / t.scale
    a = float(w @ p)
    a_q = float(w @ t.pq_of(b)) / t.scale
    return {"a": a, "a_quantized": a_q, "quant_bias": a_q - a, "e_g": float(w @ t.gq_of(b)) / t.scale,
            "e_r": float(w @ r), "sd_indicator": math.sqrt(a * (1 - a)),
            "sd_p": math.sqrt(max(float(w @ p**2) - a * a, 0.0)),
            "sd_r": math.sqrt(max(float(w @ r**2) - float(w @ r) ** 2, 0.0)),
            "sup_abs_r": float(np.abs(r).max()), "p_abs_r_gt_0.3": float(w @ (np.abs(r) > 0.3)),
            "enumeration_reads": len(w)}  # fmt: skip


# ----------------------------------------------------------------------------- the layer split


def layers(n_layers: int, scale: int) -> list[tuple[int, int, int]]:
    """(sign, lo, hi) integer cuts: dyadic 0, S/2**(L-1), ..., S/2, S for each sign."""
    cuts = [0] + [round(scale / 2**j) for j in range(n_layers - 1, -1, -1)]
    cuts = sorted(set(cuts))
    return [(s, lo, hi) for s in (1, -1) for lo, hi in itertools.pairwise(cuts)]


def encode(r: np.ndarray, part: tuple[int, int, int]) -> np.ndarray:
    """Amplitude y in [0, 1] of one layer for integer residuals r."""
    s, lo, hi = part
    return np.clip(s * r - lo, 0, hi - lo) / (hi - lo)


def combine(y: list[float], parts: list[tuple[int, int, int]], scale: int) -> float:
    """E[r] / S from the layer means."""
    return sum(s * (hi - lo) / scale * yk for yk, (s, lo, hi) in zip(y, parts))


def layer_sigmas(r: np.ndarray, w: np.ndarray, parts: list[tuple[int, int, int]], scale: int) -> list[float]:
    """MLAE's per-layer error constant in probability units: width * sqrt(a_k (1 - a_k))."""
    out = []
    for part in parts:
        ak = float(w @ encode(r, part)) / float(w.sum())
        out.append((part[2] - part[1]) / scale * math.sqrt(max(ak * (1 - ak), 0.0)))
    return out


def sigma_eff(sig: list[float]) -> float:
    """Total-query constant with the same shots on every layer (what experiment_hybrid.py runs):
    each layer gets Q / n queries, error_k = K sigma_k n / Q, so Q = K * n * sqrt(sum sigma_k**2) / eps.
    An optimal split, (sum sigma_k**(2/3))**(3/2), is up to ~2x smaller, but MLAE with few shots per
    power is unstable at deep schedules, so we do not claim it."""
    return len(sig) * math.sqrt(sum(x * x for x in sig))


def pilot(t: Tables, seed: int = 0) -> dict:
    """2**PILOT_LOG2 Sobol points of r choose the layer count (min sigma_eff). Its cost (two table
    reads per point) is charged to the hybrid. Every layer is run even if the pilot saw it empty:
    a pilot can miss a rare tail, and a skipped layer would bias the estimate."""
    u = qmc.Sobol(len(t.m.nonleaf()), scramble=True, seed=seed).random_base2(PILOT_LOG2)
    r = t.residual(t.m.bins_from_u_nonleaf(u))
    w = np.ones(len(r))
    best = min(range(1, MAX_LAYERS + 1), key=lambda n: sigma_eff(layer_sigmas(r, w, layers(n, t.scale), t.scale)))
    parts = layers(best, t.scale)
    sig = layer_sigmas(r, w, parts, t.scale)
    return {"n_layers": best, "parts": parts, "sigma_pilot": sig, "sigma_eff_pilot": sigma_eff(sig),
            "reads": 2 * len(r)}  # fmt: skip


# ----------------------------------------------------------------------------- classical engine


def cmc_qmc(m: md.Model, n_log2: int, scrambles: int, seed: int = 0, tab: Tables | None = None) -> np.ndarray:
    """Production classical arm: conditional MC (P3 exact) on scrambled Sobol, one estimate per
    scramble. With `tab`, p is one ptab read per point (the same values as Model.cond_prob)."""
    dims = len(m.nonleaf())
    out = []
    for i in range(scrambles):
        b = m.bins_from_u_nonleaf(qmc.Sobol(dims, scramble=True, seed=seed + i).random_base2(n_log2))
        out.append(float((tab.p_of(b) if tab is not None else m.cond_prob(b)).mean()))
    return np.array(out)


def classical(cfg: md.Config, eps: float, drain: md.Drainage | None = None, seed: int = 0) -> dict:
    """Doubles the Sobol budget until the 95% half-width over 16 scrambles is <= eps (2**20 cap)."""
    t0 = time.perf_counter()
    m = md.Model(cfg, drain)
    est, hw, n_log2 = np.zeros(16), math.inf, 8
    for n_log2 in range(8, 21):
        est = cmc_qmc(m, n_log2, 16, seed)
        hw = 1.96 * float(est.std(ddof=1)) / 4
        if hw <= eps:
            break
    return {"backend": "classical", "p_flood": float(est.mean()), "ci95_halfwidth": hw,
            "samples": 16 * 2**n_log2, "seconds": time.perf_counter() - t0, "model": m}  # fmt: skip


# ----------------------------------------------------------------------------- quantum engines

SIM_GRID: dict[str, Any] = {
    "delta_ft": 1.0,
    "n_w": 2,
    "n_s": 1,
    "n_o": 1,
    "n_p24": 2,
    "n_p3": 1,
    "regime_bits": 1,
    "n_k": 2,
    "g_drop": 1,
}
SIM_DROP = {"W": 1, "P24": 1, "S": 1, "O": 0}
SIM_BITS = 2


def quantum_sim(cfg: md.Config, eps: float, drain: md.Drainage | None = None, seed: int = 0,
                shots: int = 400, k_max: int = 5) -> dict:  # fmt: skip
    """The hybrid circuit at the reduced grid SIM_GRID (the benchmark grid needs ~70 qubits). For
    each layer, one Aer statevector run gives P(obj = 1) after Q^m A_h at every m in
    qae.schedule(k_max) (qae.exact_hit_probs); `shots` measurements per m are then drawn from those
    probabilities, which is the same distribution as sampling the circuit shot by shot, at a
    fraction of the run time. MLAE per layer. `eps` is only reported against: the reduced grid
    cannot be refined on a laptop."""
    import hybrid_circuit as hc

    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    m = md.Model(replace(cfg, **SIM_GRID), drain)
    t = tables(m, SIM_DROP, SIM_BITS)
    parts = layers(1, t.scale)
    ms = qae.schedule(k_max)
    y, qubits, n_q = [], 0, 0
    for part in parts:
        a_circ, q_circ, lay = hc.build(t, part)
        qubits = lay["total_qubits"]
        if qubits > MAX_SIM_QUBITS:
            raise ValueError(f"{qubits} qubits exceeds the {MAX_SIM_QUBITS}-qubit simulation limit")
        hits = rng.binomial(shots, np.clip(qae.exact_hit_probs(a_circ, q_circ, ms), 0.0, 1.0))
        y.append(qae.mlae(hits, shots, ms))
        n_q += qae.queries(shots, ms)
    est = cv_mean(t) + combine(y, parts, t.scale)
    truth = exact_parts(t)
    return {"backend": "quantum-sim", "p_flood": est, "exact_same_grid": truth["a"],
            "abs_error": abs(est - truth["a"]), "eps_requested": eps, "oracle_queries": n_q,
            "qubits": qubits, "grid": SIM_GRID, "seconds": time.perf_counter() - t0, "model": m}  # fmt: skip


def mlae_m_for(queries: float, shots: int = 100) -> int:
    """Deepest Grover power of the first MLAE schedule that spends `queries`."""
    for k in range(1, 40):
        if qae.queries(shots, qae.schedule(k)) >= queries:
            return qae.schedule(k)[-1]
    return qae.schedule(39)[-1]


def quantum_resource(cfg: md.Config, eps: float, drain: md.Drainage | None = None) -> dict:
    """Queries, qubits, Toffoli/CX and the two-qubit error the deepest circuit needs, without
    running anything. Each CV grid in DROPS gets a pilot; the one with the fewest total reads
    (coarse cells + MLAE_K * sigma_eff / eps) is used, and every pilot is charged.
    Assumes a correct, fault-free circuit (validated at reduced scale by test_hybrid.py)."""
    import hybrid_circuit as hc

    m = md.Model(cfg, drain)
    best = None
    for d in DROPS.values():
        tt = tables(m, d)
        pp = pilot(tt)
        cost = tt.coarse_cells + MLAE_K * pp["sigma_eff_pilot"] / eps
        if best is None or cost < best[0]:
            best = (cost, tt, pp)
    assert best is not None
    _, t, pl = best
    q_h = MLAE_K * pl["sigma_eff_pilot"] / eps
    sig_ind = math.sqrt(0.25)  # plain QAE's constant is sqrt(a(1-a)) <= 1/2
    cnt = hc.count(t, pl["parts"][0])
    m_max = mlae_m_for(q_h / len(pl["parts"]))  # each layer runs its own MLAE schedule
    q_cx = 2 * cnt["cx_equiv"] + 4 * cnt["qubits"]  # A, A^dagger, two reflections (~2n CX each)
    deep_cx = cnt["cx_equiv"] + m_max * q_cx
    return {"backend": "quantum-resource", "eps": eps, "oracle_queries": q_h,
            "plain_qae_queries_upper": MLAE_K * sig_ind / eps, "sigma_eff": pl["sigma_eff_pilot"],
            "layers": pl["n_layers"], "cv_coarse_cells": t.coarse_cells, "qubits": cnt["qubits"],
            "a_toffoli": cnt["toffoli"], "a_cx_equiv": cnt["cx_equiv"], "deepest_m": m_max,
            "deepest_cx_equiv": deep_cx, "total_toffoli": cnt["toffoli"] * q_h,  # one query = one A_h or A_h^dagger
            "two_qubit_error_for_50pct_success": math.log(2) / deep_cx,
            "ft_hours_at_170us_per_toffoli": cnt["toffoli"] * q_h * TOFFOLI_S / 3600,
            "classical_reads": t.coarse_cells + pl["reads"] * len(DROPS), "model": m}  # fmt: skip


BACKENDS = {"classical": classical, "quantum-sim": quantum_sim, "quantum-resource": quantum_resource}


def estimate(model_config: md.Config, eps: float, backend: str = "classical", **kw: object) -> dict:
    """One interface, three engines. Returns a dict; "model" holds the md.Model that was used."""
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {list(BACKENDS)}")
    if not 0 < eps < 0.5:
        raise ValueError("eps must be in (0, 0.5)")
    return BACKENDS[backend](model_config, eps, **kw)  # type: ignore[operator, arg-type]
