"""Does the hybrid (classical conditioning + quantum mean of the residual) beat CMC + QMC?

Protocol (same conventions as experiment_multi.py, fixed before running):
  1. Truth a = exact enumeration of the five-driver model (multidriver.py) at the benchmark grid,
     streets at 3.0 and 6.0 ft NAVD88, 2050 NOAA Intermediate.
  2. Arms, all on the same discretized model and the same integer tables:
       cmc_qmc  conditional MC (P3 exact) on scrambled Sobol over (W, P24, S, O), N = 2**8..2**18,
                REPS replicates. One query = one p evaluation (a ptab read; a black-box simulator
                would need a 6-step bisection instead, reported as x6).
       qae      plain MLAE on the indicator (experiment_multi.qae_arm), closed-form hit probabilities.
       hybrid   per control-variate grid in hybrid.DROPS: a 2**10-point classical pilot picks the
                layer count and the shot split; each layer runs MLAE (closed-form hits at its exact
                amplitude, so a correct, fault-free circuit is ASSUMED at full scale; test_hybrid.py
                validates the circuit against the same law at reduced scale). Estimate =
                exact coarse-grid CV mean + sum of layer estimates.
       enum     exact enumeration of the 2**18 non-leaf cells (P3 exact), zero error.
  3. RMSE vs truth; queries ~ eps**-alpha from an OLS fit of log RMSE on log queries with
     2000-resample bootstrap CIs (experiment_multi.fit); matched-eps queries off each bootstrap
     fit; a ratio whose 95% CI contains 1 is a tie.
  4. Total cost in table reads (rule evaluations): hybrid = quantum queries + coarse CV cells +
     pilot reads; cmc_qmc = N; qae = queries; enum = 2**18. The best CV grid is picked per eps.
  5. Break-even surface (README_hybrid.md states every assumption): extrapolates the measured d = 5
     constants to more drivers and converts to wall clock with Babbush et al.'s 170 us Toffoli.

Run: `uv run python experiment_hybrid.py` (~15 min on 4 cores). Writes results_hybrid.json.
"""

from __future__ import annotations

import json
import math
import multiprocessing
import time
from pathlib import Path

import numpy as np
from scipy.stats import qmc

import experiment_multi as em
import hybrid as hy
import hybrid_circuit as hc
import multidriver as md
import qae

ROOT = Path(__file__).resolve().parent
STREETS = (3.0, 6.0)
NS = 2 ** np.arange(8, 19)
REPS = 128
SHOTS, K_MAX, FIT_FROM_K, TRIALS = 100, 12, 3, 300
WORKERS = 4
EPS = em.EPS_TARGETS
BISECTION = 6  # ceil(log2(32 + 1)) rule runs per conditional sample for a black-box simulator
D_GRID = list(range(5, 17))
EPS_GRID = np.logspace(-2, -6, 41)

_CTX: dict = {}


def cmc_rep(job: tuple[float, int]) -> np.ndarray:
    z, seed = job
    t = _CTX[z]["tabs"]["1k"]
    m = t.m
    u = qmc.Sobol(4, scramble=True, seed=seed).random_base2(int(math.log2(NS[-1])))
    y = t.p_of(m.bins_from_u_nonleaf(u))
    return np.cumsum(y)[NS - 1] / NS


def hybrid_trial(job: tuple[float, str, int]) -> np.ndarray:
    """One hybrid trial at every MLAE depth K: binomial shots per layer from the closed form."""
    z, key, seed = job
    c = _CTX[z]["hyb"][key]
    rng = np.random.default_rng(seed)
    out = []
    for k in range(1, K_MAX + 1):
        ms = qae.schedule(k)
        y = []
        for a_k, n in zip(c["a_k"], c["shots"]):
            p = np.sin((2 * np.array(ms) + 1) * np.arcsin(np.sqrt(a_k))) ** 2
            y.append(qae.mlae(rng.binomial(n, p), n, ms))
        out.append(c["cv"] + hy.combine(y, c["parts"], c["scale"]))
    return np.array(out)


def prepare(z: float, drain: md.Drainage) -> dict:
    m = md.Model(md.Config(z_ft=z), drain)
    b, w = hy.nonleaf_cells(m)
    tabs = {k: hy.tables(m, d) for k, d in hy.DROPS.items()}
    ctx: dict = {"tabs": tabs, "a": float(w @ tabs["1k"].p_of(b)), "hyb": {}}
    for key, t in tabs.items():
        pl = hy.pilot(t, seed=int(z * 100))
        r = t.residual(b)
        a_k = [float(w @ hy.encode(r, p)) for p in pl["parts"]]
        ex = hy.exact_parts(t)
        ctx["hyb"][key] = {"parts": pl["parts"], "a_k": a_k, "shots": [SHOTS] * len(pl["parts"]),  # MLAE with few shots per power is unstable when deep
                           "cv": hy.cv_mean(t), "scale": t.scale, "coarse_cells": t.coarse_cells,
                           "pilot": {k: v for k, v in pl.items() if k != "parts"},
                           "sigma_eff_exact": hy.sigma_eff(hy.layer_sigmas(r, w, pl["parts"], t.scale)),
                           "exact": ex}  # fmt: skip
    return ctx


def study(z: float, pool, rng: np.random.Generator) -> dict:  # type: ignore[no-untyped-def]
    ctx = _CTX[z]
    a = ctx["a"]
    out: dict = {"z_ft": z, "a": a, "enumeration_reads": 2**18, "arms": {}, "hybrid": {}}
    t0 = time.time()
    est = np.array(pool.map(cmc_rep, [(z, int(s)) for s in rng.integers(0, 2**31 - 1, REPS)]))
    out["arms"]["cmc_qmc"] = em.fit(NS.astype(float), est, a, rng)
    out["arms"]["qae"] = em.qae_arm(a, rng, pool)
    fq = out["arms"]["qae"]
    out["mlae_k"] = float(np.median(np.array(fq["rmse"]) * np.array(fq["queries_axis"])) / math.sqrt(a * (1 - a)))
    for key, c in ctx["hyb"].items():
        q = np.array([sum(n * sum(2 * mm + 1 for mm in qae.schedule(k)) for n in c["shots"])
                      for k in range(1, K_MAX + 1)], dtype=float)  # fmt: skip
        est = np.array(pool.map(hybrid_trial, [(z, key, int(s)) for s in rng.integers(0, 2**31 - 1, TRIALS)]))
        # Fit against the circuit's own target E[Pq]/S: the fixed-point bias (|a_q - a| ~1e-5, in
        # results as exact.quant_bias) is a separate, fixed error and is < 1% of eps = 1e-4 in quadrature.
        f = em.fit(q[FIT_FROM_K - 1 :], est[:, FIT_FROM_K - 1 :], c["exact"]["a_quantized"], rng)
        overhead = c["coarse_cells"] + c["pilot"]["reads"] * len(hy.DROPS)  # every grid's pilot is paid for
        out["hybrid"][key] = {**f, "overhead_reads": overhead, **{k: v for k, v in c.items() if k != "a_k"},
                              "a_k": c["a_k"]}  # fmt: skip
        print(f"  z={z} hybrid {key}: alpha {f['alpha']:.2f} {np.round(f['alpha_ci'], 2)}, "
              f"sigma_eff {c['sigma_eff_exact']:.3f} (plain {math.sqrt(a * (1 - a)):.3f}), "
              f"layers {c['pilot']['n_layers']}", flush=True)  # fmt: skip
    out["matched"] = matched(out)
    out["envelope"] = envelope(out)
    print(f"z={z} done in {time.time() - t0:.0f}s", flush=True)
    return out


def _ci(x: np.ndarray) -> list[float]:
    return [float(v) for v in np.percentile(x, [2.5, 97.5])]


def matched(res: dict) -> list[dict]:
    rows = []
    cm, qa = res["arms"]["cmc_qmc"]["_need"], res["arms"]["qae"]["_need"]
    for e in EPS:
        tot = {k: h["_need"][e] + h["overhead_reads"] for k, h in res["hybrid"].items()}
        best = min(tot, key=lambda k: float(np.median(tot[k])))
        hq = res["hybrid"][best]["_need"][e]
        row = {"eps": e, "best_cv_grid": best,
               "hybrid_queries": float(np.median(hq)), "hybrid_queries_ci": _ci(hq),
               "hybrid_total_reads": float(np.median(tot[best])), "hybrid_total_ci": _ci(tot[best]),
               "cmc_qmc_queries": float(np.median(cm[e])), "cmc_qmc_ci": _ci(cm[e]),
               "cmc_qmc_blackbox_reads": float(np.median(cm[e])) * BISECTION,
               "qae_queries": float(np.median(qa[e])), "qae_ci": _ci(qa[e]),
               "enumeration_reads": res["enumeration_reads"],
               "hybrid_over_qae_queries": float(np.median(hq / qa[e])), "hybrid_over_qae_ci": _ci(hq / qa[e]),
               "hybrid_queries_over_cmc_qmc": float(np.median(hq / cm[e])), "hybrid_queries_over_cmc_qmc_ci": _ci(hq / cm[e]),
               "hybrid_total_over_cmc_qmc": float(np.median(tot[best] / cm[e])),
               "hybrid_total_over_cmc_qmc_ci": _ci(tot[best] / cm[e]),
               "hybrid_total_over_blackbox_cmc_qmc_ci": _ci(tot[best] / (BISECTION * cm[e]))}  # fmt: skip
        lo, hi = row["hybrid_total_over_cmc_qmc_ci"]
        row["verdict_vs_cmc_qmc"] = "hybrid wins" if hi < 1 else "cmc_qmc wins" if lo > 1 else "tie"
        rows.append(row)
    return rows


def envelope(res: dict) -> dict:
    """Total reads when the CV grid is chosen per eps (the multilevel knob), and its slope."""
    tot = []
    for e in EPS_GRID:
        tot.append(min(math.exp((math.log(e) - h["intercept"]) / h["slope"]) + h["overhead_reads"]
                       for h in res["hybrid"].values()))  # fmt: skip
    sel = (EPS_GRID <= 1e-3) & (EPS_GRID >= 1e-5)
    s = np.polyfit(np.log(EPS_GRID[sel]), np.log(np.array(tot)[sel]), 1)[0]
    return {"eps": EPS_GRID.tolist(), "total_reads": tot, "alpha_1e-3_to_1e-5": float(-s)}


# ----------------------------------------------------------------------------- break-even


def classical_seconds_per_sample(z: float, drain: md.Drainage) -> dict:
    m = md.Model(md.Config(z_ft=z), drain)
    t = _CTX[z]["tabs"]["1k"]
    u = qmc.Sobol(4, seed=0).random_base2(16)
    t0 = time.perf_counter()
    m.cond_prob(m.bins_from_u_nonleaf(u))
    t_bis = (time.perf_counter() - t0) / len(u)
    t0 = time.perf_counter()
    t.p_of(m.bins_from_u_nonleaf(u))
    t_tab = (time.perf_counter() - t0) / len(u)
    return {"bisection_s": t_bis, "table_s": t_tab}


def breakeven(res: dict, tc: dict) -> dict:
    """Model-based extrapolation from the measured d = 5 constants (assumptions in README_hybrid.md):
    classical  N_c(eps, d) = N_c(1e-3, 5) * (eps / 1e-3) ** -alpha_c(d), alpha_c(d) =
               1 / (1/2 + r / (d - 1)) (Novak-Heinrich randomized rate for a (d-1)-dim r-smooth
               integrand), r fitted so alpha_c(5) = the measured CMC+QMC exponent.
    hybrid     N_h = K_h * sigma_eff / eps (measured constant at d = 5, held fixed in d) +
               coarse CV cells, which grow as cells_5 ** ((d - 1) / 4) (same bits per driver).
    cost/query classical t_c(d) = t_c(5) (d - 1) / 4 s; quantum Toffoli(A_h, d) = Toffoli(5) (d - 1) / 4
               at 170 us each (Babbush et al.), all serial on one machine each.
    gate error deepest MLAE circuit Q^m A_h must succeed half the time: p2q <= ln 2 / CX(deepest)."""
    cm = res["arms"]["cmc_qmc"]
    alpha5 = cm["alpha"]
    r_s = 4 * (1 / alpha5 - 0.5)
    n_c5 = cm["queries"][str(1e-3)]
    key = min(res["hybrid"], key=lambda k: res["hybrid"][k]["queries"][str(1e-4)] + res["hybrid"][k]["overhead_reads"])
    h = res["hybrid"][key]
    t = _CTX[res["z_ft"]]["tabs"][key]
    cnt = hc.count(t, tuple(h["parts"][0]))
    k_h = h["queries"][str(1e-4)] * 1e-4  # queries * eps at the measured slope ~ -1
    rows = []
    for d in D_GRID:
        f = (d - 1) / 4
        a_c = 1 / (0.5 + r_s / (d - 1))
        cells = h["coarse_cells"] ** f
        tof, cx = cnt["toffoli"] * f, cnt["cx_equiv"] * f
        win_reads = win_wall = None
        for e in EPS_GRID:
            n_c = n_c5 * (e / 1e-3) ** -a_c
            n_h = k_h / e
            if win_reads is None and n_h + cells < n_c:
                win_reads = float(e)
            if win_wall is None and n_h * tof * hy.TOFFOLI_S < n_c * tc["bisection_s"] * f:
                win_wall = float(e)
        row = {"d": d, "alpha_classical": a_c, "cv_cells": cells, "a_h_toffoli": tof,
               "eps_star_reads": win_reads, "eps_star_wallclock": win_wall}  # fmt: skip
        for tag, e_star in (("reads", win_reads), ("wallclock", win_wall)):
            if e_star is not None:
                n_h = k_h / e_star
                m_max = hy.mlae_m_for(n_h * max(h["shots"]) / sum(h["shots"]))
                deep = cx * (2 * m_max + 1)
                row[f"p2q_needed_at_{tag}"] = math.log(2) / deep
                row[f"hours_quantum_at_{tag}"] = n_h * tof * hy.TOFFOLI_S / 3600
                row[f"seconds_classical_at_{tag}"] = n_c5 * (e_star / 1e-3) ** -a_c * tc["bisection_s"] * f
        rows.append(row)
    return {"cv_grid": key, "r_smoothness_fit": r_s, "k_h": k_h, "a_h_counts_d5": cnt, "classical_s": tc,
            "rows": rows}  # fmt: skip


def strip(o):  # type: ignore[no-untyped-def]
    if isinstance(o, dict):
        return {str(k): strip(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [strip(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    return o


def main() -> None:
    rng = np.random.default_rng(2027)
    drain = md.calibrate_drainage()
    for z in STREETS:
        _CTX[z] = prepare(z, drain)
    out: dict = {"protocol": {"ns": NS.tolist(), "reps": REPS, "shots": SHOTS, "k_max": K_MAX, "trials": TRIALS,
                              "eps": EPS, "drops": hy.DROPS, "bits": hy.BITS}, "studies": {}}  # fmt: skip
    em.QAE_TRIALS, em.K_MAX = TRIALS, K_MAX  # set before forking: qae_trial reads em.K_MAX
    with multiprocessing.get_context("fork").Pool(WORKERS) as pool:  # workers inherit _CTX
        for z in STREETS:
            out["studies"][str(z)] = study(z, pool, rng)
    for z in STREETS:
        s = out["studies"][str(z)]
        s["breakeven"] = breakeven(s, classical_seconds_per_sample(z, drain))
    (ROOT / "results_hybrid.json").write_text(json.dumps(strip(out), indent=1))
    for z in STREETS:
        s = out["studies"][str(z)]
        print(f"\nstreet {z} ft, a = {s['a']:.4f}; MLAE constant K = {s['mlae_k']:.2f}")
        for name, f in s["arms"].items():
            print(f"  {name:8s} alpha {f['alpha']:.2f} [{f['alpha_ci'][0]:.2f}, {f['alpha_ci'][1]:.2f}]")
        for key, f in s["hybrid"].items():
            print(f"  hyb {key:4s} alpha {f['alpha']:.2f} [{f['alpha_ci'][0]:.2f}, {f['alpha_ci'][1]:.2f}]")
        print(f"  hybrid envelope alpha (CV grid chosen per eps) {s['envelope']['alpha_1e-3_to_1e-5']:.2f}")
        for r in s["matched"]:
            print(f"  eps {r['eps']:.0e}: hybrid q {r['hybrid_queries']:.3g} + {r['hybrid_total_reads'] - r['hybrid_queries']:.3g} "
                  f"({r['best_cv_grid']}) | cmc_qmc {r['cmc_qmc_queries']:.3g} | qae {r['qae_queries']:.3g} | enum 2.6e5 | "
                  f"total/cmc {r['hybrid_total_over_cmc_qmc']:.2f} {np.round(r['hybrid_total_over_cmc_qmc_ci'], 2)} "
                  f"-> {r['verdict_vs_cmc_qmc']}")  # fmt: skip
        for r in s["breakeven"]["rows"]:
            print(
                f"  d={r['d']:2d} alpha_c {r['alpha_classical']:.2f}: eps* reads {r['eps_star_reads']}, wall {r['eps_star_wallclock']}"
            )


if __name__ == "__main__":
    main()
