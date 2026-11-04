"""Query-complexity benchmark: MLAE vs plain and stratified Monte Carlo on the Key West flood tail.

Protocol (fixed before running):
  1. Truth a = P(annual peak >= NWS major flood stage) under the GEV fitted to the real
     NOAA record, discretized on 2^5 bins. Both methods estimate this same a.
  2. Budgets: MLAE schedules K = 1..K_MAX (m in {0,1,2,...,2^(K-2)}, SHOTS shots each).
     Monte Carlo is run at exactly the same query budgets. One query = one call of A,
     the same unit as one classical draw.
     A third, classical control arm uses the same budgets: stratified sampling (one uniform
     per stratum of [0,1], through the inverse CDF). In 1-D this also reaches O(1/N).
  3. TRIALS independent seeded repeats per (method, budget). Error metric = RMSE vs a.
  4. Scaling exponent: OLS slope of log RMSE on log queries over the fit range, CI by
     bootstrapping trials (resample trials within each budget, refit). Report
     queries ~ eps^(-alpha), alpha = -1/slope. Textbook: MC alpha = 2, QAE alpha = 1.
  5. Hardware realism: transpile A and Q to IBM Heron (FakeFez), count CZ/depth per
     schedule step, and run the first few Q^m A circuits under the FakeFez noise model.

Run: `uv run python experiment.py`   (~6 min)
"""

import json
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from qiskit import transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeFez

import flood
import qae

load_dotenv()

SAVE_ACCOUNT = False  # Flip to True once, locally, to cache an IBM credential.
RUN_ON_HARDWARE = False  # Keep False. Simulator only for this prototype.
if RUN_ON_HARDWARE or SAVE_ACCOUNT:
    from qiskit_ibm_runtime import QiskitRuntimeService

    QiskitRuntimeService.save_account(
        channel="ibm_quantum_platform", token=os.environ["IBM_QUANTUM_API_KEY"], overwrite=True
    )
    raise NotImplementedError("hardware path not built: the noisy-sim section shows why (see README)")

ROOT = Path(__file__).resolve().parent
SHOTS = 100
K_MAX = 11
FIT_FROM_K = 3  # K=1 is plain sampling (m=0 only); K=2 is still in the pre-asymptotic regime
TRIALS = 500
BOOT = 2000
EPS_TARGETS = [1e-3, 3e-4, 1e-4]
ARMS = {
    "qae": ("MLAE (quantum)", "C0"),
    "mc": ("plain Monte Carlo", "C1"),
    "strat": ("stratified sampling (classical, 1-D)", "C2"),
}
NOISY_MS = [0, 1, 2, 4]
NOISY_SHOTS = 4000


def fit_slope(q: np.ndarray, err: np.ndarray) -> tuple[float, float]:
    slope, icpt = np.polyfit(np.log(q), np.log(err), 1)
    return float(slope), float(icpt)


def rmse(est: np.ndarray, a: float) -> np.ndarray:
    return np.sqrt(((est - a) ** 2).mean(axis=-1))


def scaling(q: np.ndarray, est: np.ndarray, a: float, rng: np.random.Generator) -> dict:
    """est: (budgets, trials). Point fit + bootstrap over trials for slope and matched-eps queries."""
    slope, icpt = fit_slope(q, rmse(est, a))
    boots = []
    for _ in range(BOOT):
        idx = rng.integers(0, est.shape[1], est.shape[1])
        boots.append(fit_slope(q, rmse(est[:, idx], a)))
    bs = np.array(boots)
    alpha = -1 / bs[:, 0]
    need = {e: np.exp((np.log(e) - bs[:, 1]) / bs[:, 0]) for e in EPS_TARGETS}
    return {
        "slope": slope, "slope_ci": np.percentile(bs[:, 0], [2.5, 97.5]).tolist(),
        "alpha": -1 / slope, "alpha_ci": np.percentile(alpha, [2.5, 97.5]).tolist(),
        "intercept": icpt, "_need_boot": need,
    }  # fmt: skip


def hardware_cost(a_circ, q_circ, schedule: list[int]) -> dict:  # type: ignore[no-untyped-def]
    backend = FakeFez()
    out: dict = {}
    for name, c in (("A", a_circ), ("Q", q_circ)):
        tc = transpile(c, backend, optimization_level=3, seed_transpiler=0)
        out[name] = {"cz": tc.count_ops().get("cz", 0), "depth": tc.depth(), "physical_qubits": len(tc.layout.final_index_layout())}  # fmt: skip
    cz_err = float(np.median([p.error for p in backend.target["cz"].values() if p and p.error is not None]))
    out["cz_error_median"] = cz_err
    out["per_m"] = []
    for m in schedule:
        cz = out["A"]["cz"] + m * out["Q"]["cz"]
        out["per_m"].append({"m": m, "cz": cz, "depth": out["A"]["depth"] + m * out["Q"]["depth"],
                             "cz_only_fidelity": (1 - cz_err) ** cz})  # fmt: skip
    return out


def noisy_run(a_circ, q_circ, ideal: np.ndarray, a: float) -> dict:  # type: ignore[no-untyped-def]
    """Q^m A under the FakeFez noise model; MLAE on the noisy counts for the same schedule."""
    backend = FakeFez()
    sim = AerSimulator.from_backend(backend)
    obj = a_circ.metadata["obj"]
    hits = []
    for m in NOISY_MS:
        c = qae.circuit(a_circ, q_circ, m)
        c.measure_all()
        tc = transpile(c, backend, optimization_level=3, seed_transpiler=0)
        counts = sim.run(tc, shots=NOISY_SHOTS, seed_simulator=m).result().get_counts()
        hits.append(sum(v for k, v in counts.items() if k[::-1][obj] == "1"))
    h = np.array(hits)
    est = qae.mlae(h, NOISY_SHOTS, NOISY_MS)
    return {"ms": NOISY_MS, "shots": NOISY_SHOTS, "p_noisy": (h / NOISY_SHOTS).tolist(), "p_ideal": ideal.tolist(),
            "mlae_noisy_estimate": est, "mlae_noisy_abs_err": abs(est - a)}  # fmt: skip


def run(k_max: int = K_MAX, trials: int = TRIALS, noisy: bool = True, out_name: str = "results") -> dict:
    p = flood.problem()
    a = p["a_true"]
    a_circ = qae.state_prep(p["probs"], p["threshold_bin"])
    q_circ = qae.grover(a_circ)
    full_ms = qae.schedule(k_max)
    p_hit = dict(zip(full_ms, qae.exact_hit_probs(a_circ, q_circ, full_ms)))
    rng = np.random.default_rng(0)

    ks = list(range(1, k_max + 1))
    q = np.array([qae.queries(SHOTS, qae.schedule(k)) for k in ks], dtype=float)
    cdf = np.cumsum(p["probs"])
    est = {name: np.empty((len(ks), trials)) for name in ARMS}
    for i, k in enumerate(ks):
        ms = qae.schedule(k)
        probs = np.array([p_hit[m] for m in ms])
        n = int(q[i])
        strata = np.arange(n)
        for t in range(trials):
            est["qae"][i, t] = qae.mlae(rng.binomial(SHOTS, probs), SHOTS, ms)
            # One uniform per stratum [j/N, (j+1)/N), pushed through the binned inverse CDF.
            u = (strata + rng.random(n)) / n
            est["strat"][i, t] = (np.searchsorted(cdf, u, side="right") >= p["threshold_bin"]).mean()
        # N iid draws from the binned GEV counted against the threshold is exactly Binomial(N, a).
        est["mc"][i] = rng.binomial(n, a, size=trials) / n

    fit = slice(FIT_FROM_K - 1, None)
    sc = {name: scaling(q[fit], e[fit], a, rng) for name, e in est.items()}
    matched = []
    for e in EPS_TARGETS:
        need = {name: s["_need_boot"][e] for name, s in sc.items()}
        row: dict = {"eps": e, "rel_eps": e / a, "mc_queries_analytic": a * (1 - a) / e**2}
        for name in ARMS:
            row[f"{name}_queries"] = float(np.median(need[name]))
        for name in ("mc", "strat"):
            ratio = need[name] / need["qae"]
            row[f"{name}_over_qae"] = float(np.median(ratio))
            row[f"{name}_over_qae_ci"] = np.percentile(ratio, [2.5, 97.5]).tolist()
        matched.append(row)
    for s in sc.values():
        del s["_need_boot"]

    r = {name: rmse(e, a) for name, e in est.items()}
    out = {
        "problem": {k: v for k, v in p.items() if k not in ("probs", "amax", "yrs")},
        "shots": SHOTS, "trials": trials, "fit_from_k": FIT_FROM_K,
        "budgets": [{"k": k, "max_m": qae.schedule(k)[-1], "queries": int(q[i]),
                     **{f"rmse_{name}": float(r[name][i]) for name in ARMS},
                     "rmse_mc_analytic": float(np.sqrt(a * (1 - a) / q[i]))} for i, k in enumerate(ks)],
        "scaling": sc, "matched_eps": matched,
        "width_logical_qubits": a_circ.num_qubits,
        "hardware": hardware_cost(a_circ, q_circ, full_ms),
    }  # fmt: skip
    if noisy:
        out["noisy_fakefez"] = noisy_run(a_circ, q_circ, np.array([p_hit[m] for m in NOISY_MS]), a)
    (ROOT / f"{out_name}.json").write_text(json.dumps(out, indent=2))
    if out_name == "results":
        plot(out, q, r, a)
    return out


def plot(out: dict, q: np.ndarray, r: dict[str, np.ndarray], a: float) -> None:
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(12, 4.8))
    xs = q[FIT_FROM_K - 1 :]
    for key, (label, col) in ARMS.items():
        ax.loglog(q, r[key], "o", color=col, label=label)
        s = out["scaling"][key]
        ax.loglog(xs, np.exp(s["intercept"]) * xs ** s["slope"], "-", color=col, alpha=0.7,
                  label=f"fit: queries ~ eps^-{s['alpha']:.2f} [{s['alpha_ci'][0]:.2f}, {s['alpha_ci'][1]:.2f}]")  # fmt: skip
    ax.set_xlabel("oracle queries (calls of A)")
    ax.set_ylabel(f"RMSE of estimated P(flood >= NWS major), a = {a:.4f}")
    ax.set_title(f"Key West annual-peak tail, {out['trials']} trials per point")
    ax.legend(fontsize=8)
    ax.grid(True, which="both", alpha=0.3)

    hw = out["hardware"]["per_m"]
    ms = [h["m"] for h in hw]
    bx.semilogy(ms[1:], [h["cz"] for h in hw][1:], "s-", color="C3", label="CZ gates in Q^m A (FakeFez)")
    bx.set_xscale("log", base=2)
    bx.set_xlabel("Grover power m")
    bx.set_ylabel("CZ count")
    bx.axhline(1 / out["hardware"]["cz_error_median"], ls="--", color="gray", label="1 / median CZ error")
    bx.set_title("Circuit cost per schedule step")
    bx.legend(fontsize=8)
    bx.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(ROOT / "results.png", dpi=130)


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("scaling", "matched_eps", "width_logical_qubits")}, indent=2))
    print(json.dumps(r["hardware"], indent=2))
    print(json.dumps(r.get("noisy_fakefez"), indent=2))
