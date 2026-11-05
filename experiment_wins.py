"""Search for an honest axis where ideal QAE beats the best classical estimator on Floodline.

Prior result (README_multidriver.md): on the five-driver model, conditional MC on Sobol points
(CMC+QMC) needs 0.18-0.55x QAE's queries at d = 5, and exact enumeration wins on total work.
This script tests four axes where that verdict could flip. Protocol, fixed before running:

  A. rare events, relative error. P(water depth at a 3.0 ft street >= h) for h = 0.5 .. 5 ft
     (Irma-like depths), a from 0.61 down to 1.3e-4, same discretized model and tables as
     experiment_multi.py (only the tolerance TOL_FT is raised; drainage stays calibrated at
     0.5 ft). Targets are RELATIVE RMSE 1e-2, 3e-3, 1e-3. Arms: CMC+QMC; CMC + importance
     sampling + QMC (exponential tilt of W, P24, S, O, tilt picked on a pilot whose cost is
     reported); plain MC (exact binomial); exact enumeration (2^18 conditional evaluations,
     independent of a); ideal MLAE.
  B. dimension. The five physical drivers plus up to eight epistemic parameters the README
     flags as uncertain: CN ~ U(88, 95) (SMP Table 2-6 range), soil depth ~ U(3, 5) ft (SMP),
     outfall share ~ U(0.25, 0.75), catchment ratio ~ U(2, 4), well start ~ U(1.4, 1.8) ft
     (ASSUMPTION ranges, centred on the code's values), and the three tide-GEV parameters
     (normal approximation of a 200-refit parametric bootstrap). d = 5, 7, 9, 10, 13. Drainage
     is recalibrated per sample from the same 5-yr LOS anchor. The rule is evaluated in floating
     point on the benchmark driver grid (no integer quantization of R and T), so d = 5 here is
     close to, not equal to, experiment_multi's a. Arms: CMC+QMC (P3 integrated exactly), plain
     Sobol QMC over all d dims, ideal MLAE. Absolute RMSE 1e-3, 3e-4, 1e-4.
  C. nested expectation under GEV parameter uncertainty: G = E_theta[max(a(theta) - a0, 0)]
     with a(theta) = P(flood | tide-GEV parameters theta), a0 = a at the fitted theta (expected
     excess of the street's flood probability over its point estimate). Arms: white-box nested
     (outer Sobol over theta, inner CMC+QMC, N_in = N_out); black-box randomized MLMC
     (Blanchet-Glynn single-term, antithetic, inner = plain indicator draws). Quantum is a cost
     MODEL, not a simulation: the ideal lower bound C/eps with C from this run's MLAE fit at
     a = G's scale, i.e. the best case for the nested quantum algorithms (arXiv:2602.08120,
     2502.05094 carry extra polylog factors, ignored here in quantum's favour).

Accounting, identical across arms: one query = one evaluation of the flood rule at one full
driver vector (classical) or one application of A / A^dagger (quantum). Conditional arms count
one query per sample (white-box threshold inversion), as in experiment_multi; a black-box
simulator would pay ceil(log2(33)) = 6 per sample, reported alongside. QAE hit probabilities are
the closed form sin^2((2m+1) theta) at the exact a (fault-free circuit ASSUMED, as in
experiment_multi). RMSE over REPS replicates, OLS fit of log RMSE on log queries, 2000 bootstrap
resamples; queries at matched eps read off each bootstrap fit; ratio CI from independent
bootstraps of the two arms. A ratio whose 95% CI contains 1 is a tie. The smallest resolvable
ratio is the CI half-width, reported per cell (prior study: about +-10%).

Run: `uv run python experiment_wins.py` (about 30 min on 6 cores). Writes results_wins.json, results_wins.png.
"""

from __future__ import annotations

import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from scipy.stats import qmc

import experiment_multi as em
import flood
import multidriver as md
import qae

ROOT = Path(__file__).resolve().parent
Z_FT = 3.0
M_MAX = 20
NS = 2 ** np.arange(10, M_MAX + 1)
REPS = 64
WORKERS = 6
CHUNK = 2**17
DEPTHS = [0.5, 1.0, 2.0, 3.0, 5.0]
REL_EPS = [1e-2, 3e-3, 1e-3]
ABS_EPS = [1e-3, 3e-4, 1e-4]
IS_LAMBDAS, IS_PILOT = [0.0, 1.0, 2.0, 4.0, 6.0, 8.0], 2**12
SHOTS, K_MAX, FIT_FROM_K, QAE_TRIALS = 100, 13, 3, 200
TOL = 0.5
NOMINAL = {"CN": md.CN, "SOIL": md.SOIL_DEPTH_FT, "SHARE": md.OUTFALL_SHARE, "CATCH": md.CATCH_RATIO,
           "WELL": md.WELL_START_FT}  # fmt: skip
RANGES = {"CN": (88, 95), "SOIL": (3, 5), "SHARE": (0.25, 0.75), "CATCH": (2, 4), "WELL": (1.4, 1.8)}
EXTRAS = ["CN", "SOIL", "SHARE", "CATCH", "WELL", "GEV_c", "GEV_loc", "GEV_scale"]
D_LIST = [5, 7, 9, 10, 13]
NEST_LOG2 = list(range(3, 10))  # N_out = N_in = 2^k, total cost 4^k
NEST_REPS = 48
MLMC_NS = 2 ** np.arange(8, 19)
MLMC_P = 2**-1.5  # level probability ratio: between the variance (2^-1.5 for a kinked g) and cost (2^-1) rates


# ----------------------------------------------------------------------------- shared helpers


def fit(q: np.ndarray, est: np.ndarray, truth: float, eps: list[float], rng: np.random.Generator) -> dict:
    em.EPS_TARGETS = eps  # em.fit reads its targets from this module global
    return em.fit(np.asarray(q, float), np.asarray(est, float), truth, rng)


def ratio(num: dict, den: dict, eps: list[float]) -> dict:
    out = {}
    for e in eps:
        r = num["_need"][e] / den["_need"][e]
        lo, med, hi = np.percentile(r, [2.5, 50, 97.5])
        out[str(e)] = {"ratio": float(med), "ci": [float(lo), float(hi)],
                       "verdict": "quantum wins" if lo > 1 else "classical wins" if hi < 1 else "tie"}  # fmt: skip
    return out


def qae_trial(job: tuple[float, int]) -> np.ndarray:
    a, seed = job
    rng = np.random.default_rng(seed)
    theta = np.arcsin(np.sqrt(a))
    out = []
    for k in range(1, K_MAX + 1):
        ms = qae.schedule(k)
        out.append(qae.mlae(rng.binomial(SHOTS, np.sin((2 * np.array(ms) + 1) * theta) ** 2), SHOTS, ms))
    return np.array(out)


def qae_arm(a: float, eps: list[float], relative: bool, pool, rng: np.random.Generator) -> dict:  # type: ignore[no-untyped-def]
    q = np.array([qae.queries(SHOTS, qae.schedule(k)) for k in range(1, K_MAX + 1)], float)
    est = np.array(pool.map(qae_trial, [(a, int(s)) for s in rng.integers(0, 2**31 - 1, QAE_TRIALS)]))
    if relative:
        est = est / a
    return fit(q[FIT_FROM_K - 1 :], est[:, FIT_FROM_K - 1 :], 1.0 if relative else a, eps, rng)


def running(y: np.ndarray) -> np.ndarray:
    return np.cumsum(y)[NS - 1] / NS


# ----------------------------------------------------------------------------- axis A: rare events

_RARE: dict[float, md.Model] = {}


def rare_model(h: float, drain: md.Drainage) -> md.Model:
    if h not in _RARE:
        md.TOL_FT = h  # only the tolerance moves; drain was calibrated at 0.5 ft
        _RARE[h] = md.Model(md.Config(z_ft=Z_FT), drain)
        md.TOL_FT = TOL
    return _RARE[h]


def cmc_is(m: md.Model, lam: float, u_nl: np.ndarray) -> np.ndarray:
    """Conditional MC (P3 exact) with the non-leaf drivers drawn from a tilted proposal."""
    t = md.Model.__new__(md.Model)
    t.__dict__.update(m.__dict__)
    t.pmf_w, t.pmf_s, t.pmf_o = em._tilt(m.pmf_w, lam), em._tilt(m.pmf_s, lam), em._tilt(m.pmf_o, lam)
    t.cond_p24 = em._tilt(m.cond_p24, lam)
    b = t.bins_from_u_nonleaf(u_nl)
    rw = m._regime(b["W"], m.cfg.n_w)
    w = (m.pmf_w[b["W"]] / t.pmf_w[b["W"]]) * (m.cond_p24[rw, b["P24"]] / t.cond_p24[rw, b["P24"]])
    w *= (m.pmf_s[b["S"]] / t.pmf_s[b["S"]]) * (m.pmf_o[b["O"]] / t.pmf_o[b["O"]])
    return w * m.cond_prob(b)


def rare_rep(job: tuple) -> np.ndarray:
    h, arm, lam, seed, drain = job
    m = rare_model(h, drain)
    u = qmc.Sobol(4, scramble=True, seed=seed).random_base2(M_MAX)
    f = (lambda x: m.cond_prob(m.bins_from_u_nonleaf(x))) if arm == "cmc_qmc" else (lambda x: cmc_is(m, lam, x))
    return running(np.concatenate([f(u[i : i + CHUNK]) for i in range(0, len(u), CHUNK)]))


def rare_pilot(job: tuple) -> float:
    h, lam, seed, drain = job
    m = rare_model(h, drain)
    return float(cmc_is(m, lam, np.random.default_rng(seed).random((IS_PILOT, 4))).var())


def rare_exact(job: tuple) -> float:
    h, drain = job
    return rare_model(h, drain).exact()


def axis_rare(pool, rng: np.random.Generator, drain: md.Drainage) -> dict:  # type: ignore[no-untyped-def]
    out: dict = {}
    truths = pool.map(rare_exact, [(h, drain) for h in DEPTHS])
    for h, a in zip(DEPTHS, truths):
        t0 = time.time()
        var = pool.map(rare_pilot, [(h, lam, int(rng.integers(2**31)), drain) for lam in IS_LAMBDAS])
        lam = IS_LAMBDAS[int(np.argmin(var))]
        res: dict = {"a": a, "is_lambda": lam, "is_pilot_var": var, "is_pilot_queries": IS_PILOT * len(IS_LAMBDAS),
                     "enumeration_evals": 2**18, "arms": {}}  # fmt: skip
        for arm in ("cmc_qmc", "cmc_is_qmc"):
            est = np.array(pool.map(rare_rep, [(h, arm, lam, int(s), drain) for s in rng.integers(0, 2**31 - 1, REPS)]))
            res["arms"][arm] = fit(NS, est / a, 1.0, REL_EPS, rng)
        inc = rng.binomial(np.diff(np.concatenate([[0], NS])), a, size=(REPS * 4, len(NS)))
        res["arms"]["mc"] = fit(NS, np.cumsum(inc, 1) / NS / a, 1.0, REL_EPS, rng)
        res["arms"]["qae"] = qae_arm(a, REL_EPS, True, pool, rng)
        res["vs_qae"] = {k: ratio(v, res["arms"]["qae"], REL_EPS) for k, v in res["arms"].items() if k != "qae"}
        res["enum_vs_qae"] = {str(e): float(2**18 / np.median(res["arms"]["qae"]["_need"][e])) for e in REL_EPS}
        out[str(h)] = res
        print(f"[rare] h={h} a={a:.3g} lam={lam} " + " ".join(
            f"{k}:{v[str(REL_EPS[-1])]['ratio']:.3g}{v[str(REL_EPS[-1])]['ci']}" for k, v in res["vs_qae"].items())
            + f" ({time.time() - t0:.0f}s)", flush=True)  # fmt: skip
    return out


def cmc_w(m: md.Model, u: np.ndarray) -> np.ndarray:
    """Conditional MC over the TIDE instead of the rain burst: draw P24 (marginal), P3 | P24, S, O
    on u's four columns, then integrate W exactly over its posterior given P24's bin (Bayes on the
    copula regimes). The rule is monotone in the W bin (higher still water raises the coastal
    stage and cuts outfall head), so the threshold bin is found by bisection, as in cond_prob."""
    p24_marg = m.pmf_w_regimes() @ m.cond_p24
    b = {"P24": md._inv(np.cumsum(p24_marg), u[:, 0])}
    b["P3"] = md._inv_rows(np.cumsum(m.cond_p3, 1), m._regime(b["P24"], m.cfg.n_p24), u[:, 1])
    b["S"], b["O"] = md._inv(np.cumsum(m.pmf_s), u[:, 2]), md._inv(np.cumsum(m.pmf_o), u[:, 3])
    reg = np.arange(len(m.pmf_w)) >> (m.cfg.n_w - m.cfg.regime_bits)
    post = m.pmf_w[None, :] * m.cond_p24[reg][:, b["P24"]].T
    post /= post.sum(1, keepdims=True)
    n = len(m.pmf_w)
    lo, hi = np.zeros(len(u), np.int64), np.full(len(u), n, np.int64)
    while np.any(lo < hi):
        mid = (lo + hi) // 2
        hit = m.indicator({**b, "W": np.minimum(mid, n - 1)})
        act = lo < hi
        hi, lo = np.where(act & hit, mid, hi), np.where(act & ~hit, mid + 1, lo)
    cdf = np.concatenate([np.zeros((len(u), 1)), np.cumsum(post, 1)], 1)
    return 1 - cdf[np.arange(len(u)), lo]


def rare2_rep(job: tuple) -> np.ndarray:
    h, seed, drain = job
    m = rare_model(h, drain)
    u = qmc.Sobol(4, scramble=True, seed=seed).random_base2(M_MAX)
    return running(np.concatenate([cmc_w(m, u[i : i + CHUNK]) for i in range(0, len(u), CHUNK)]))


A_REF = 0.6147930463523252  # h = 0.5 truth: the MLAE constant is measured here, where MLAE is well behaved


def axis_rare2(pool, rng: np.random.Generator, drain: md.Drainage, rare: dict) -> dict:  # type: ignore[no-untyped-def]
    """Second pass on the rare-event axis, after the first showed two artefacts:
    (1) MLAE with 100 shots per power stalls for a < 1e-2 (wrong-fringe outliers: its RMSE stops
        falling past ~2e5 queries), which would hand the classical arms a fake win. Quantum gets
        its BEST case instead: the ideal-QAE law, queries for abs error eps at a scale with
        sqrt(a(1-a)) / eps, with the constant and exponent from an MLAE fit at a = A_REF
        (the convention floodline_cli.qae_line already uses). Fringe-safe variants (IQAE)
        approach this; MLAE as run here does not.
    (2) The classical arms in pass 1 integrate the RAIN burst, but the deep tail is tide-driven
        (tide alone is 69% of a at h = 5 ft). A skeptic integrates the tide instead: cmc_w_qmc."""
    out: dict = {}
    for h in DEPTHS:
        t0 = time.time()
        a = rare[str(h)]["a"]
        est = np.array(pool.map(rare2_rep, [(h, int(s), drain) for s in rng.integers(0, 2**31 - 1, REPS)]))
        res: dict = {"a": a, "arms": {"cmc_w_qmc": fit(NS, est / a, 1.0, REL_EPS, rng)}}
        scale = np.sqrt(A_REF * (1 - A_REF)) / np.sqrt(a * (1 - a))
        eq = [e * a * scale for e in REL_EPS]  # same RMSE-to-sqrt(a(1-a)) ratio at A_REF
        qm = qae_arm(A_REF, eq, False, pool, rng)
        qm["_need"] = {e: qm["_need"][x] for e, x in zip(REL_EPS, eq)}
        for key in ("queries", "queries_ci", "extrapolated"):
            qm[key] = {str(e): qm[key][str(x)] for e, x in zip(REL_EPS, eq)}
        res["arms"]["qae_ideal_law"] = qm
        res["vs_qae"] = {"cmc_w_qmc": ratio(res["arms"]["cmc_w_qmc"], qm, REL_EPS)}
        res["enum_over_qae"] = {str(e): float(2**18 / qm["queries"][str(e)]) for e in REL_EPS}
        out[str(h)] = res
        r = res["vs_qae"]["cmc_w_qmc"]
        print(f"[rare2] h={h} a={a:.3g} cmc_w alpha={res['arms']['cmc_w_qmc']['alpha']:.2f} "
              + " ".join(f"eps{e}: qae={qm['queries'][str(e)]:.3g} cmcw/qae={r[str(e)]['ratio']:.3g}{r[str(e)]['ci']}"
                         for e in REL_EPS) + f" ({time.time() - t0:.0f}s)", flush=True)  # fmt: skip
    return out


# ----------------------------------------------------------------------------- axis B / C: epistemic model


class EpiModel:
    """The five-driver model with `n_extra` epistemic parameters as extra random dimensions,
    flood rule in floating point on the benchmark driver grid. Column order of u:
    W, P24, P3, S, O, then EXTRAS[:n_extra]. Unused extras sit at the code's nominal values."""

    def __init__(self, n_extra: int, drain: md.Drainage, gev_mean: np.ndarray, gev_chol: np.ndarray):
        md.TOL_FT = TOL
        self.m = md.Model(md.Config(z_ft=Z_FT), drain)
        self.n_extra, self.anchor = n_extra, drain.anchor
        self.gev_mean, self.gev_chol = gev_mean, gev_chol
        m = self.m
        self.cdf_w, self.cdf_s, self.cdf_o = np.cumsum(m.pmf_w), np.cumsum(m.pmf_s), np.cumsum(m.pmf_o)
        self.cdf24, self.cdf3 = np.cumsum(m.cond_p24, 1), np.cumsum(m.cond_p3, 1)

    @property
    def d(self) -> int:
        return 5 + self.n_extra

    def w_bins(self, u_w: np.ndarray, u_gev: np.ndarray | None) -> np.ndarray:
        if u_gev is None:
            return md._inv(self.cdf_w, u_w)
        z = stats.norm.ppf(np.clip(u_gev, 1e-12, 1 - 1e-12))
        full = np.zeros((len(u_w), 3))
        full[:, : z.shape[1]] = z
        th = self.gev_mean + full @ self.gev_chol.T
        w_ft = self.m.mhhw + stats.genextreme.ppf(u_w, th[:, 0], th[:, 1], th[:, 2]) * md.FT_PER_M
        k = np.rint((w_ft - self.m.cfg.w_lo_ft) / self.m.cfg.delta_ft)
        return np.clip(np.nan_to_num(k, nan=0.0), 0, len(self.cdf_w) - 1).astype(np.int64)

    def params(self, ux: np.ndarray) -> dict[str, np.ndarray]:
        n = len(ux)
        p = {k: np.full(n, float(v)) for k, v in NOMINAL.items()}
        for i, name in enumerate(EXTRAS[: min(self.n_extra, 5)]):
            lo, hi = RANGES[name]
            p[name] = lo + (hi - lo) * ux[:, i]
        an = self.anchor
        r = runoff(
            np.full(n, an["p24_in"]), np.full(n, an["p3_in"]), np.full(n, an["g_ft"]), an["z_ft"], p["CN"], p["SOIL"]
        )
        need = r - 12 * TOL / p["CATCH"]
        out = np.sqrt(an["z_ft"] + TOL - an["c_ft"])
        well = an["z_ft"] + TOL - an["g_ft"] - p["WELL"]
        if np.any(need <= 0) or np.any(well <= 0):
            raise RuntimeError("degenerate drainage anchor inside the epistemic ranges")
        p["k_out"] = p["SHARE"] * need / (md.BURST_HOURS * out)
        p["k_well"] = (1 - p["SHARE"]) * need / (md.BURST_HOURS * well)
        return p

    def bins(self, u: np.ndarray) -> dict[str, np.ndarray]:
        m = self.m
        gev = u[:, 10 : 10 + self.n_extra - 5] if self.n_extra > 5 else None
        b = {"W": self.w_bins(u[:, 0], gev)}
        b["P24"] = md._inv_rows(self.cdf24, m._regime(b["W"], m.cfg.n_w), u[:, 1])
        b["P3"] = md._inv_rows(self.cdf3, m._regime(b["P24"], m.cfg.n_p24), u[:, 2])
        b["S"], b["O"] = md._inv(self.cdf_s, u[:, 3]), md._inv(self.cdf_o, u[:, 4])
        return b

    def flood(self, b: dict[str, np.ndarray], p: dict[str, np.ndarray]) -> np.ndarray:
        m, z, d = self.m, Z_FT, self.m.cfg.delta_ft
        s = m.s_lo + d * b["S"]
        c = m.w_nodes[b["W"]] + s
        g = m.mhhw + s + m.o_lo + d * b["O"]
        r = runoff(m.p24_nodes[b["P24"]], m.p3_nodes[b["P3"]], g, z, p["CN"], p["SOIL"])
        out, well = np.sqrt(np.maximum(z + TOL - c, 0)), np.maximum(z + TOL - g - p["WELL"], 0)
        drain = md.BURST_HOURS * (p["k_out"] * out + p["k_well"] * well)
        base = np.maximum(np.maximum(c, g), z) - z
        return base + p["CATCH"] * np.maximum(r - drain, 0) / 12 >= TOL

    def indicator(self, u: np.ndarray) -> np.ndarray:
        return self.flood(self.bins(u), self.params(u[:, 5:]))

    def cond_prob(self, u_nl: np.ndarray) -> np.ndarray:
        """P(flood | everything but P3); u_nl has the P3 column removed. Monotone in the P3 bin."""
        u = np.insert(u_nl, 2, 0.0, axis=1)
        b, p = self.bins(u), self.params(u[:, 5:])
        rows = self.m.cond_p3[self.m._regime(b["P24"], self.m.cfg.n_p24)]
        n = rows.shape[1]
        lo, hi = np.zeros(len(u), np.int64), np.full(len(u), n, np.int64)
        while np.any(lo < hi):
            mid = (lo + hi) // 2
            hit = self.flood({**b, "P3": np.minimum(mid, n - 1)}, p)
            act = lo < hi
            hi, lo = np.where(act & hit, mid, hi), np.where(act & ~hit, mid + 1, lo)
        cdf = np.concatenate([np.zeros((len(u), 1)), np.cumsum(rows, 1)], 1)
        return 1 - cdf[np.arange(len(u)), lo]


def runoff(p24, p3, g, z, cn, soil):  # type: ignore[no-untyped-def]
    p3 = np.minimum(p3, p24)
    s_r = (1000 / cn - 10) * np.clip((z - g) / soil, 0, 1)
    pa = (p24 - p3) / 2
    return md.scs_runoff(pa + p3, s_r) - md.scs_runoff(pa, s_r)


_EPI: dict[int, EpiModel] = {}


def epi(n_extra: int, ctx: tuple) -> EpiModel:
    if n_extra not in _EPI:
        _EPI[n_extra] = EpiModel(n_extra, *ctx)
    return _EPI[n_extra]


def dim_rep(job: tuple) -> np.ndarray:
    n_extra, arm, seed, log2n, ctx = job
    e = epi(n_extra, ctx)
    dims = e.d - (1 if arm == "cmc_qmc" else 0)
    u = qmc.Sobol(dims, scramble=True, seed=seed).random_base2(log2n)
    f = e.cond_prob if arm == "cmc_qmc" else (lambda x: e.indicator(x).astype(float))
    y = np.concatenate([f(u[i : i + CHUNK]) for i in range(0, len(u), CHUNK)])
    return running(y) if log2n == M_MAX else np.array([y.mean()])


def gev_uncertainty() -> tuple[np.ndarray, np.ndarray]:
    _, amax, _, _ = flood.load_annual_maxima()
    th0 = np.array(flood.fit_gev(amax))
    rng = np.random.default_rng(7)
    boot = np.array([flood.fit_gev(stats.genextreme.rvs(*th0, size=len(amax), random_state=rng)) for _ in range(200)])
    return th0, np.linalg.cholesky(np.cov(boot.T))


def axis_dim(pool, rng: np.random.Generator, ctx: tuple) -> dict:  # type: ignore[no-untyped-def]
    out: dict = {}
    for d in D_LIST:
        t0, n_extra = time.time(), d - 5
        ref = pool.map(dim_rep, [(n_extra, "cmc_qmc", 10**6 + i, 21, ctx) for i in range(32)])
        a = float(np.mean(ref))
        res: dict = {"a": a, "a_ref_se": float(np.std(ref, ddof=1) / np.sqrt(len(ref))), "extras": EXTRAS[:n_extra],
                     "arms": {}}  # fmt: skip
        for arm in ("cmc_qmc", "qmc"):
            est = np.array(
                pool.map(dim_rep, [(n_extra, arm, int(s), M_MAX, ctx) for s in rng.integers(0, 2**31 - 1, REPS)])
            )
            res["arms"][arm] = fit(NS, est, a, ABS_EPS, rng)
        res["arms"]["qae"] = qae_arm(a, ABS_EPS, False, pool, rng)
        res["vs_qae"] = {k: ratio(v, res["arms"]["qae"], ABS_EPS) for k, v in res["arms"].items() if k != "qae"}
        out[str(d)] = res
        print(f"[dim] d={d} a={a:.4f}+-{res['a_ref_se']:.1e} " + " ".join(
            f"{k}: alpha={v['alpha']:.2f}" for k, v in res["arms"].items()) + " | " + " ".join(
            f"{k}:{v[str(ABS_EPS[-1])]['ratio']:.3g}{v[str(ABS_EPS[-1])]['ci']}" for k, v in res["vs_qae"].items())
            + f" ({time.time() - t0:.0f}s)", flush=True)  # fmt: skip
    return out


# ----------------------------------------------------------------------------- axis C: nested expectation

# theta = the three tide-GEV parameters; the five physical epistemic extras are pinned at their
# nominal values through their uniforms, so the integrand is a(theta) of the base model.
NEST_EXTRA = 8
MID = np.array([(NOMINAL[k] - RANGES[k][0]) / (RANGES[k][1] - RANGES[k][0]) for k in EXTRAS[:5]])


def nest_inner(e: EpiModel, u_gev: np.ndarray, u_in: np.ndarray, cond: bool) -> np.ndarray:
    """a(theta) estimates, one per outer row of u_gev: mean over the inner points u_in (shared
    shape (n_in, 4 or 5)). cond: inner is CMC (white-box); else plain indicator draws (black-box)."""
    n_out, n_in = len(u_gev), len(u_in)
    ex = np.hstack([np.tile(MID, (n_out, 1)), u_gev])
    big_ex = np.repeat(ex, n_in, 0)
    big_in = np.tile(u_in, (n_out, 1))
    if cond:
        y = e.cond_prob(np.hstack([big_in, big_ex]))
    else:
        y = e.indicator(np.hstack([big_in, big_ex])).astype(float)
    return y.reshape(n_out, n_in).mean(1)


def nest_white_rep(job: tuple) -> np.ndarray:
    """Outer Sobol over theta (3 dims), inner CMC+QMC (4 dims), N_out = N_in = 2^k."""
    seed, a0, ctx = job
    e = epi(NEST_EXTRA, ctx)
    out = []
    for k in NEST_LOG2:
        uo = qmc.Sobol(3, scramble=True, seed=seed).random_base2(k)
        ui = qmc.Sobol(4, scramble=True, seed=seed + 1).random_base2(k)
        out.append(np.maximum(nest_inner(e, uo, ui, True) - a0, 0).mean())
    return np.array(out)


def nest_mlmc_rep(job: tuple) -> np.ndarray:
    """Randomized MLMC (single-term, Blanchet-Glynn): level L ~ Geom(MLMC_P), inner 2^(L+1) iid
    indicator draws, antithetic difference g(mean) - (g(mean_a) + g(mean_b))/2. Unbiased for G."""
    seed, a0, ctx = job
    e = epi(NEST_EXTRA, ctx)
    rng = np.random.default_rng(seed)
    n = int(MLMC_NS[-1])
    lev = np.minimum(rng.geometric(1 - MLMC_P, n) - 1, 16)
    pl = (1 - MLMC_P) * MLMC_P ** lev.astype(float)
    y, cost = np.zeros(n), np.zeros(n)
    for L in np.unique(lev):
        idx = np.flatnonzero(lev == L)
        m_in = 2 ** (L + 1)
        for s in range(0, len(idx), max(1, CHUNK // m_in)):
            j = idx[s : s + max(1, CHUNK // m_in)]
            ex = np.repeat(np.hstack([np.tile(MID, (len(j), 1)), rng.random((len(j), 3))]), m_in, 0)
            hits = e.indicator(np.hstack([rng.random((len(j) * m_in, 5)), ex])).reshape(len(j), m_in).astype(float)
            g_full = np.maximum(hits.mean(1) - a0, 0)
            if L == 0:  # base level: g of a 2-draw inner mean, no correction term
                y[j] = g_full / pl[j]
            else:
                g_a = np.maximum(hits[:, : m_in // 2].mean(1) - a0, 0)
                g_b = np.maximum(hits[:, m_in // 2 :].mean(1) - a0, 0)
                y[j] = (g_full - (g_a + g_b) / 2) / pl[j]
        cost[idx] = m_in
    cum_c = np.cumsum(cost)
    idx = np.searchsorted(cum_c, MLMC_NS) - 1
    idx = np.clip(idx, 0, n - 1)
    return np.array([y[: i + 1].mean() for i in idx]), cum_c[idx]


def axis_nested(pool, rng: np.random.Generator, ctx: tuple) -> dict:  # type: ignore[no-untyped-def]
    t0 = time.time()
    e = epi(NEST_EXTRA, ctx)
    mid = MID
    # a0 = a at the fitted GEV (z = 0 in the bootstrap normal), by CMC+QMC to ~1e-6
    u = qmc.Sobol(4, scramble=True, seed=11).random_base2(20)
    a0 = float(np.mean([e.cond_prob(np.hstack([u[i : i + CHUNK], np.tile(np.r_[mid, 0.5, 0.5, 0.5], (CHUNK, 1))]))
                        for i in range(0, len(u), CHUNK)]))  # fmt: skip
    # Reference G: 64 x 64 outer Sobol theta, inner CMC+QMC 2^14 each, 4 scrambles of the outer net.
    ref = []
    for s in range(4):
        uo = qmc.Sobol(3, scramble=True, seed=500 + s).random_base2(8)
        ui = qmc.Sobol(4, scramble=True, seed=600 + s).random_base2(14)
        a_th = np.concatenate([nest_inner(e, uo[i : i + 8], ui, True) for i in range(0, len(uo), 8)])
        ref.append(np.maximum(a_th - a0, 0).mean())
    G = float(np.mean(ref))
    res: dict = {"a0": a0, "G": G, "G_ref_se": float(np.std(ref, ddof=1) / 2), "arms": {}}
    print(f"[nested] a0={a0:.5f} G={G:.3g}+-{res['G_ref_se']:.1e} ({time.time() - t0:.0f}s)", flush=True)
    eps = [G * r for r in (0.1, 0.03, 0.01)]  # relative 10%, 3%, 1% of the target
    res["eps_abs"] = eps
    seeds = rng.integers(0, 2**31 - 1, NEST_REPS)
    wb = np.array(pool.map(nest_white_rep, [(int(s), a0, ctx) for s in seeds]))
    res["arms"]["white_nested_cmc_qmc"] = fit(4.0 ** np.array(NEST_LOG2), wb, G, eps, rng)
    mm = pool.map(nest_mlmc_rep, [(int(s), a0, ctx) for s in seeds])
    est, cost = np.array([x[0] for x in mm]), np.array([x[1] for x in mm]).mean(0)
    res["arms"]["blackbox_rmlmc"] = fit(cost, est, G, eps, rng)
    # Quantum best-case cost model: the MLAE constant at a ~ G (queries for abs error eps at a = G).
    res["arms"]["quantum_model"] = qae_arm(G, eps, False, pool, rng)
    res["vs_qae"] = {
        k: ratio(v, res["arms"]["quantum_model"], eps) for k, v in res["arms"].items() if k != "quantum_model"
    }
    print("[nested] " + " ".join(f"{k}: alpha={v['alpha']:.2f}" for k, v in res["arms"].items()) + " | " + " ".join(
        f"{k}:{v[str(eps[-1])]['ratio']:.3g}{v[str(eps[-1])]['ci']}" for k, v in res["vs_qae"].items())
        + f" ({time.time() - t0:.0f}s)", flush=True)  # fmt: skip
    return res


# ----------------------------------------------------------------------------- output


def plot(out: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    if "rare2" in out:
        ax = axes[0]
        hs = list(out["rare2"])
        a = [out["rare"][h]["a"] for h in hs]
        e = str(REL_EPS[1])
        arms = {"qae_ideal_law": "rare2", "cmc_qmc": "rare", "cmc_w_qmc": "rare2", "mc": "rare"}
        for (arm, src), col in zip(arms.items(), ("C0", "C3", "C5", "C1")):
            q = [out[src][h]["arms"][arm]["queries"][e] for h in hs]
            ci = np.array([out[src][h]["arms"][arm]["queries_ci"][e] for h in hs])
            ax.fill_between(a, ci[:, 0], ci[:, 1], color=col, alpha=0.2)
            ax.loglog(a, q, "o-", color=col, label=arm)
        ax.axhline(2**18, color="k", ls="--", lw=0.8, label="exact enumeration (2^18)")
        ax.set_xlabel("a = P(depth >= h), 3.0 ft street")
        ax.set_ylabel(f"queries for relative RMSE {REL_EPS[1]:g}")
        ax.set_title("A. rare events (QAE = ideal law, best case)")
        ax.legend(fontsize=7)
    if "dim" in out:
        ax = axes[1]
        ds = list(out["dim"])
        e = str(ABS_EPS[-1])
        for arm, col in (("qae", "C0"), ("cmc_qmc", "C3"), ("qmc", "C2")):
            q = [out["dim"][d]["arms"][arm]["queries"][e] for d in ds]
            ci = np.array([out["dim"][d]["arms"][arm]["queries_ci"][e] for d in ds])
            xs = [int(d) for d in ds]
            ax.fill_between(xs, ci[:, 0], ci[:, 1], color=col, alpha=0.2)
            ax.semilogy(xs, q, "o-", color=col, label=arm)
        ax.set_xlabel("random dimensions d (5 physical + epistemic)")
        ax.set_ylabel(f"queries for RMSE {ABS_EPS[-1]:g}")
        ax.set_title("B. dimension scaling")
        ax.legend(fontsize=7)
    if "nested" in out:
        ax = axes[2]
        n = out["nested"]
        for arm, col in (("quantum_model", "C0"), ("white_nested_cmc_qmc", "C3"), ("blackbox_rmlmc", "C1")):
            r = n["arms"][arm]
            q = np.array(r["queries_axis"])
            ax.loglog(q, r["rmse"], "o", ms=3, color=col)
            ax.loglog(
                q, np.exp(r["intercept"]) * q ** r["slope"], "-", color=col, label=f"{arm} alpha={r['alpha']:.2f}"
            )
        for e in n["eps_abs"]:
            ax.axhline(e, color="gray", lw=0.5, ls=":")
        ax.set_xlabel("queries (rule evaluations / A applications)")
        ax.set_ylabel("RMSE of G")
        ax.set_title("C. nested E[max(a(theta) - a0, 0)]")
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(ROOT / "results_wins.png", dpi=130)


def main() -> None:
    axes = sys.argv[1:] or ["rare", "dim", "nested"]
    rng = np.random.default_rng(1106)
    path = ROOT / "results_wins.json"
    out: dict = json.loads(path.read_text()) if path.exists() else {}
    out["protocol"] = {"ns": NS.tolist(), "reps": REPS, "depths_ft": DEPTHS, "rel_eps": REL_EPS, "abs_eps": ABS_EPS,
                       "d_list": D_LIST, "extras": EXTRAS, "ranges": RANGES, "shots": SHOTS, "k_max": K_MAX,
                       "qae_trials": QAE_TRIALS, "nest_log2": NEST_LOG2, "nest_reps": NEST_REPS,
                       "mlmc_p": MLMC_P}  # fmt: skip
    drain = md.calibrate_drainage()
    ctx = (drain, *gev_uncertainty())
    with Pool(WORKERS) as pool:
        for ax in axes:
            t0 = time.time()
            if path.exists():  # another axis may have finished in a separate run meanwhile
                out = {**json.loads(path.read_text()), **out}
            if ax == "rare":
                out["rare"] = axis_rare(pool, rng, drain)
            elif ax == "rare2":
                out["rare2"] = axis_rare2(pool, rng, drain, out["rare"])
            elif ax == "dim":
                out["dim"] = axis_dim(pool, rng, ctx)
            elif ax == "nested":
                out["nested"] = axis_nested(pool, rng, ctx)
            out[f"runtime_{ax}_s"] = time.time() - t0
            out = em.strip(out)
            path.write_text(json.dumps(out, indent=1))
    plot(out)


if __name__ == "__main__":
    main()
