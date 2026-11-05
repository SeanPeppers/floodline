"""Does QAE beat the best classical estimator on the real multi-driver Key West model?

Protocol (fixed before running; same conventions as experiment.py and the toy crossover study):
  1. Truth a = Model.exact(): P(flood) on the discretized joint model of multidriver.py, for a
     street at Z_FT ft NAVD88 in 2050 (NOAA 2022 Intermediate). Configurations nest the drivers:
     d=2 (W, P24), d=3 (+S), d=4 (+O), d=5 (+P3). Frozen drivers sit at their median.
     A second street (Z_FT_2) repeats the whole study as a robustness check.
  2. One query = one evaluation of the flood indicator at one full driver vector (classical), or
     one application of A or A^dagger (quantum). Every classical arm samples the SAME discretized
     model through the SAME integer tables the circuit loads.
  3. Classical arms, N = 2^10 .. 2^20, REPS independent replicates each:
       mc        plain Monte Carlo. N iid indicator draws is exactly Binomial(N, a); the test
                 checks that against real draws through the model.
       qmc       scrambled Sobol through the Rosenblatt inverse CDFs, d dimensions.
       cmc       conditional MC: the rain-chain leaf (P3 at d=5, else P24) integrated exactly given
                 the other drivers; iid over the remaining d-1 dimensions.
       cmc_qmc   the same conditional integrand on scrambled Sobol over d-1 dimensions.
       is        importance sampling, exponential tilt of every driver toward high bins; tilt
                 chosen on a pilot run whose cost is reported separately.
     Conditional arms count one query per sample (white-box: the threshold of a monotone rule can
     be inverted in closed form). A black-box simulator would need a bisection of ceil(log2(n+1))
     runs per sample instead; that factor is reported, not hidden.
  4. Quantum arm: MLAE (qae.mlae), SHOTS per Grover power, m in {0, 1, 2, ..., 2^(K-2)}, K up to
     K_MAX, QAE_TRIALS trials. Hit probabilities come from the closed form sin^2((2m+1) theta)
     with a = Model.exact(). This ASSUMES a correct, fault-free circuit at full resolution; the
     circuit itself is validated against that law by exact statevector simulation at reduced
     resolution (test_multidriver.py), not at full resolution, which does not fit in memory.
  5. Error = RMSE over replicates; queries ~ eps^-alpha from an OLS fit of log RMSE on log N;
     95% CIs by bootstrapping replicates; matched-eps queries read off each bootstrap fit. A ratio
     whose 95% CI contains 1 is reported as a tie, not a win.

Run: `uv run python experiment_multi.py` (about 40 min on 4 cores). Writes results_multi.json and
results_multi.png.
"""

from __future__ import annotations

import json
import time
from multiprocessing import Pool
from multiprocessing.pool import Pool as PoolType
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import qmc

import multidriver as md
import multidriver_circuit as mc
import qae

ROOT = Path(__file__).resolve().parent
Z_FT, Z_FT_2 = 3.0, 6.0  # 3 ft: between the frequently flooded ~1 ft intersections and the 4 ft of
# Bahama Village (SMP); 6 ft: an upland street, where the event is rarer and rain-driven
CONFIGS = {2: ("W", "P24"), 3: ("W", "P24", "S"), 4: ("W", "P24", "S", "O"), 5: md.DRIVERS}
M_MIN, M_MAX = 10, 20
NS = 2 ** np.arange(M_MIN, M_MAX + 1)
REPS = 128
BOOT = 2000
EPS_TARGETS = [1e-3, 3e-4, 1e-4]
SHOTS, K_MAX, FIT_FROM_K, QAE_TRIALS = 100, 13, 3, 500
IS_LAMBDAS = [0.0, 0.5, 1.0, 2.0, 3.0, 4.0, 6.0]
IS_PILOT = 2**14
WORKERS = 4  # other jobs share this 15 GB machine
ARMS = {"qae": ("MLAE (quantum, ideal)", "C0"), "mc": ("plain MC", "C1"), "qmc": ("Sobol QMC", "C2"),
        "is": ("importance sampling", "C4"), "cmc": ("conditional MC", "C5"),
        "cmc_qmc": ("conditional MC + Sobol", "C3")}  # fmt: skip

_MODELS: dict[tuple, md.Model] = {}


def model_for(z: float, d: int) -> md.Model:
    key = (z, d)
    if key not in _MODELS:
        _MODELS[key] = md.Model(md.Config(z_ft=z, drivers=CONFIGS[d]))
    return _MODELS[key]


def _tilt(p: np.ndarray, lam: float) -> np.ndarray:
    k = np.arange(p.shape[-1]) / max(p.shape[-1] - 1, 1)
    q = p * np.exp(lam * k)
    return q / q.sum(axis=-1, keepdims=True)


def is_estimates(m: md.Model, lam: float, u: np.ndarray) -> np.ndarray:
    """Per-sample weighted indicator under the tilted proposal (unbiased for a)."""
    t = md.Model.__new__(md.Model)
    t.__dict__.update(m.__dict__)
    t.pmf_w, t.pmf_s, t.pmf_o = _tilt(m.pmf_w, lam), _tilt(m.pmf_s, lam), _tilt(m.pmf_o, lam)
    t.cond_p24, t.cond_p3 = _tilt(m.cond_p24, lam), _tilt(m.cond_p3, lam)
    b = t.bins_from_u(u)
    rw, r24 = m._regime(b["W"], m.cfg.n_w), m._regime(b["P24"], m.cfg.n_p24)
    w = (m.pmf_w[b["W"]] / t.pmf_w[b["W"]]) * (m.cond_p24[rw, b["P24"]] / t.cond_p24[rw, b["P24"]])
    w *= (m.pmf_s[b["S"]] / t.pmf_s[b["S"]]) * (m.pmf_o[b["O"]] / t.pmf_o[b["O"]])
    if m.nbits["P3"]:
        w *= m.cond_p3[r24, b["P3"]] / t.cond_p3[r24, b["P3"]]
    return w * m.indicator(b)


def pick_lambda(m: md.Model, seed: int) -> tuple[float, list[float]]:
    rng = np.random.default_rng(seed)
    var = [float(is_estimates(m, lam, rng.random((IS_PILOT, len(m.random)))).var()) for lam in IS_LAMBDAS]
    return IS_LAMBDAS[int(np.argmin(var))], var


def one_rep(job: tuple) -> np.ndarray:
    """Running estimates at every N in NS for one replicate of one arm."""
    z, d, arm, seed, lam = job
    m = model_for(z, d)
    n_max = int(NS[-1])
    dims = len(m.random) - (1 if arm.startswith("cmc") else 0)
    if arm in ("qmc", "cmc_qmc"):
        u = qmc.Sobol(d=dims, scramble=True, seed=seed).random_base2(M_MAX)
    else:
        u = np.random.default_rng(seed).random((n_max, dims))
    if arm in ("qmc",):
        y = m.indicator(m.bins_from_u(u)).astype(float)
    elif arm.startswith("cmc"):
        y = np.concatenate([m.cond_prob(m.bins_from_u_nonleaf(u[i : i + 2**18])) for i in range(0, n_max, 2**18)])
    elif arm == "is":
        y = np.concatenate([is_estimates(m, lam, u[i : i + 2**18]) for i in range(0, n_max, 2**18)])
    else:
        raise ValueError(arm)
    return np.cumsum(y)[NS - 1] / NS


def fit(q: np.ndarray, est: np.ndarray, a: float, rng: np.random.Generator) -> dict:
    """est: (reps, budgets). Same estimator as the toy crossover study and experiment.scaling()."""

    def sf(e: np.ndarray) -> tuple[float, float]:
        s, i = np.polyfit(np.log(q), np.log(np.sqrt(((e - a) ** 2).mean(0))), 1)
        return float(s), float(i)

    slope, icpt = sf(est)
    bs = np.array([sf(est[rng.integers(0, len(est), len(est))]) for _ in range(BOOT)])
    need = {e: np.exp((np.log(e) - bs[:, 1]) / bs[:, 0]) for e in EPS_TARGETS}
    return {
        "alpha": -1 / slope, "alpha_ci": np.percentile(-1 / bs[:, 0], [2.5, 97.5]).tolist(),
        "slope": slope, "intercept": icpt, "queries_axis": q.tolist(),
        "rmse": np.sqrt(((est - a) ** 2).mean(0)).tolist(),
        "queries": {str(e): float(np.median(need[e])) for e in EPS_TARGETS},
        "queries_ci": {str(e): np.percentile(need[e], [2.5, 97.5]).tolist() for e in EPS_TARGETS},
        "extrapolated": {str(e): bool(np.median(need[e]) > q[-1]) for e in EPS_TARGETS},
        "_need": need,
    }  # fmt: skip


def qae_trial(job: tuple[float, int]) -> np.ndarray:
    """One MLAE trial at every K: binomial shots from the closed-form hit probabilities."""
    a, seed = job
    rng = np.random.default_rng(seed)
    theta = np.arcsin(np.sqrt(a))
    out = []
    for k in range(1, K_MAX + 1):
        ms = qae.schedule(k)
        p = np.sin((2 * np.array(ms) + 1) * theta) ** 2
        out.append(qae.mlae(rng.binomial(SHOTS, p), SHOTS, ms))
    return np.array(out)


def qae_arm(a: float, rng: np.random.Generator, pool: PoolType) -> dict:
    q = np.array([qae.queries(SHOTS, qae.schedule(k)) for k in range(1, K_MAX + 1)], dtype=float)
    est = np.array(pool.map(qae_trial, [(a, int(s)) for s in rng.integers(0, 2**31 - 1, QAE_TRIALS)]))
    out = fit(q[FIT_FROM_K - 1 :], est[:, FIT_FROM_K - 1 :], a, rng)
    out["max_m"] = qae.schedule(K_MAX)[-1]
    out["m_needed"] = {str(e): _m_needed(out["queries"][str(e)]) for e in EPS_TARGETS}
    return out


def _m_needed(queries: float) -> int:
    """Largest Grover power in the first MLAE schedule whose query count reaches `queries`."""
    for k in range(1, 40):
        if qae.queries(SHOTS, qae.schedule(k)) >= queries:
            return qae.schedule(k)[-1]
    raise ValueError("budget out of range")


def study(z: float, pool: PoolType, rng: np.random.Generator) -> dict:
    out: dict = {"z_ft": z, "configs": {}}
    for d, drivers in CONFIGS.items():
        t0 = time.time()
        m = model_for(z, d)
        a = m.exact()
        lam, pilot_var = pick_lambda(m, int(rng.integers(2**31)))
        res: dict = {"drivers": list(drivers), "a": a, "model": m.summary(), "grid_cells": m.grid_size(),
                     "nonleaf_cells": int(m.grid_size() // 2 ** m.nbits[m.leaf]), "leaf": m.leaf,
                     "bisection_evals": int(np.ceil(np.log2(2 ** m.nbits[m.leaf] + 1))),
                     "is_lambda": lam, "is_pilot_queries": IS_PILOT * len(IS_LAMBDAS),
                     "is_pilot_var": dict(zip(map(str, IS_LAMBDAS), pilot_var)), "arms": {}}  # fmt: skip
        # Plain MC: N iid draws of the indicator is exactly Binomial(N, a); nested budgets from one stream.
        inc = rng.binomial(np.diff(np.concatenate([[0], NS])), a, size=(REPS * 4, len(NS)))
        res["arms"]["mc"] = fit(NS.astype(float), np.cumsum(inc, 1) / NS, a, rng)
        for arm in ("qmc", "cmc", "cmc_qmc", "is"):
            seeds = rng.integers(0, 2**31 - 1, REPS)
            est = np.array(pool.map(one_rep, [(z, d, arm, int(s), lam) for s in seeds]))
            res["arms"][arm] = fit(NS.astype(float), est, a, rng)
        res["arms"]["qae"] = qae_arm(a, rng, pool)
        res["matched"] = matched(res)
        out["configs"][d] = res
        print(f"z={z} d={d} a={a:.5f} " + " ".join(f"{k}:{v['alpha']:.2f}" for k, v in res["arms"].items())
              + f" ({time.time() - t0:.0f}s)", flush=True)  # fmt: skip
    return out


def matched(res: dict) -> list[dict]:
    rows = []
    arms = res["arms"]
    for e in EPS_TARGETS:
        row: dict = {"eps": e, "rel_eps": e / res["a"]}
        qn = arms["qae"]["_need"][e]
        for name, r in arms.items():
            row[f"{name}_queries"] = float(np.median(r["_need"][e]))
            if name != "qae":
                ratio = r["_need"][e] / qn  # independent bootstraps of independent arms
                lo, hi = np.percentile(ratio, [2.5, 97.5])
                row[f"{name}_over_qae"] = float(np.median(ratio))
                row[f"{name}_over_qae_ci"] = [float(lo), float(hi)]
                row[f"qae_beats_{name}"] = bool(lo > 1)
                row[f"{name}_beats_qae"] = bool(hi < 1)
        classical = [k for k in arms if k != "qae"]
        best = min(classical, key=lambda k: row[f"{k}_queries"])
        row["best_classical"] = best
        row["qae_beats_every_classical"] = all(row[f"qae_beats_{k}"] for k in classical)
        row["exact_enumeration_evals"] = res["nonleaf_cells"]
        rows.append(row)
    return rows


def crossover(study_out: dict, arm: str) -> dict:
    """Smallest d (linear interpolation of log ratio) where `arm` needs more queries than QAE."""
    ds = sorted(study_out["configs"])
    out = {}
    for e in EPS_TARGETS:
        lr = [float(np.log(study_out["configs"][d]["matched"][EPS_TARGETS.index(e)][f"{arm}_over_qae"])) for d in ds]
        dstar = None
        for i, v in enumerate(lr):
            if v > 0:
                dstar = ds[0] if i == 0 else ds[i - 1] + lr[i - 1] / (lr[i - 1] - v)
                break
        out[str(e)] = {"d_star": dstar, "log_ratio_by_d": dict(zip(map(str, ds), lr))}
    return out


def circuit_resources() -> dict:
    out = {}
    for d in CONFIGS:
        a_circ, q_circ, lay = mc.build(model_for(Z_FT, d))
        out[d] = {"layout": {k: v for k, v in lay.items() if k not in ("registers",)}, **mc.resources(a_circ, q_circ)}
        print(
            f"circuit d={d}: {out[d]['A']['qubits']} qubits, A cx={out[d]['A']['cx']}, Q cx={out[d]['Q']['cx']}",
            flush=True,
        )
    return out


def sensitivity() -> dict:
    """Model sensitivities of a (exact, d=5, Z_FT): tide-rain tau prior, and grid resolution."""
    base = md.Config(z_ft=Z_FT)
    drain = md.calibrate_drainage()
    out: dict = {f"tau_{t}": md.Model(md.replace(base, tau_wp=t), drain).exact() for t in (0.0, 0.1, 0.2, 0.3)}
    fine = md.replace(base, delta_ft=1 / 16, n_w=7, n_s=5, n_o=4, n_p24=6, n_p3=6, n_k=8, g_drop=2)
    out["fine_grid"] = md.Model(fine, drain).exact()
    out["benchmark_grid"] = md.Model(base, drain).exact()
    out["mechanisms"] = md.mechanisms(md.Model(base, drain))
    return out


def strip(o):  # type: ignore[no-untyped-def]
    if isinstance(o, dict):
        return {str(k): strip(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def plot(out: dict) -> None:
    st = out["studies"][str(Z_FT)]
    ds = sorted(st["configs"], key=int)
    fig, axes = plt.subplots(2, len(ds), figsize=(4.2 * len(ds), 8.4))
    for j, d in enumerate(ds):
        c = st["configs"][d]
        ax = axes[0, j]
        for name, (label, col) in ARMS.items():
            r = c["arms"][name]
            q = np.array(r["queries_axis"])
            ax.loglog(q, r["rmse"], "o", ms=3, color=col)
            ax.loglog(q, np.exp(r["intercept"]) * q ** r["slope"], "-", color=col, alpha=0.8,
                      label=f"{label}: a={r['alpha']:.2f} [{r['alpha_ci'][0]:.2f},{r['alpha_ci'][1]:.2f}]")  # fmt: skip
        for e in EPS_TARGETS:
            ax.axhline(e, color="gray", lw=0.5, ls=":")
        ax.set_title(f"d={d}: {'+'.join(c['drivers'])}\na = {c['a']:.4f}, street {Z_FT} ft NAVD88, 2050")
        ax.set_xlabel("queries")
        ax.grid(True, which="both", alpha=0.25)
        ax.legend(fontsize=6.5, loc="lower left")
    axes[0, 0].set_ylabel("RMSE of P(flood)")
    for j, e in enumerate(EPS_TARGETS):
        ax = axes[1, j]
        for name, (label, col) in ARMS.items():
            qs = [st["configs"][d]["arms"][name]["queries"][str(e)] for d in ds]
            ci = np.array([st["configs"][d]["arms"][name]["queries_ci"][str(e)] for d in ds])
            xs = [int(d) for d in ds]
            ax.fill_between(xs, ci[:, 0], ci[:, 1], color=col, alpha=0.2)
            ax.semilogy(xs, qs, "o-", color=col, label=label)
        ax.axhline(2.0**M_MAX, color="k", lw=0.6, ls="-.", label="largest classical N simulated")
        ax.set_title(f"queries to reach RMSE {e:g}")
        ax.set_xlabel("number of random drivers d")
        ax.set_xticks([int(d) for d in ds])
        ax.grid(True, which="both", alpha=0.25)
        ax.legend(fontsize=6.5)
    axes[1, 0].set_ylabel("queries (median of bootstrap fits, 95% CI band)")
    for ax in axes[1, len(EPS_TARGETS) :]:
        ax.axis("off")
    fig.suptitle("Real Key West multi-driver model: QAE (ideal) vs the classical field")
    fig.tight_layout()
    fig.savefig(ROOT / "results_multi.png", dpi=130)


def main() -> None:
    rng = np.random.default_rng(2026)
    t0 = time.time()
    out: dict = {"protocol": {"ns": NS.tolist(), "reps": REPS, "boot": BOOT, "eps": EPS_TARGETS, "shots": SHOTS,
                              "k_max": K_MAX, "qae_trials": QAE_TRIALS, "fit_from_k": FIT_FROM_K,
                              "is_lambdas": IS_LAMBDAS, "is_pilot": IS_PILOT}}  # fmt: skip
    out["sensitivity"] = sensitivity()
    print("sensitivity", json.dumps(strip(out["sensitivity"])), flush=True)
    out["circuits"] = circuit_resources()
    out["studies"] = {}
    with Pool(WORKERS) as pool:
        for z in (Z_FT, Z_FT_2):
            s = study(z, pool, rng)
            s["crossover"] = {arm: crossover(s, arm) for arm in ARMS if arm != "qae"}
            out["studies"][str(z)] = s
            (ROOT / "results_multi.json").write_text(json.dumps(strip(out), indent=1))
    out["runtime_s"] = time.time() - t0
    out = strip(out)
    (ROOT / "results_multi.json").write_text(json.dumps(out, indent=1))
    plot(out)


if __name__ == "__main__":
    main()
