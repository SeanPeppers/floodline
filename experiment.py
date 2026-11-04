"""Query-complexity benchmark: MLAE vs plain Monte Carlo vs Sobol QMC on the Key West
compound tide+rain flood tail.

Protocol (fixed before running):
  1. Truth a = P(tide >= NWS minor stage AND 24-hr rain >= its 10-yr return level), under the
     discretized Gaussian-copula joint model (copula.py). All three methods estimate this same a.
  2. Budgets: MLAE schedules K = 1..K_MAX (m in {0,1,2,...,2^(K-2)}, SHOTS shots each).
     Monte Carlo is run at exactly the same query budgets. One query = one call of A,
     the same unit as one classical draw from the joint model.
     A second, classical control arm uses the same budgets: 2-D Sobol low-discrepancy
     quasi-Monte Carlo through copula.compound_hits -- the 1-D stratified-sampling trick the
     single-variable build used doesn't generalize to a joint (tide, rain) distribution, so
     this is the honest smarter-than-plain-MC control for a 2-D problem.
  3. TRIALS independent seeded repeats per (method, budget). Error metric = RMSE vs a.
  4. Scaling exponent: OLS slope of log RMSE on log queries over the fit range, CI by
     bootstrapping trials (resample trials within each budget, refit). Report
     queries ~ eps^(-alpha), alpha = -1/slope. Textbook: MC alpha = 2, QAE alpha = 1.
  5. Hardware realism: transpile A and Q to IBM Heron (FakeFez), count CZ/depth per
     schedule step, and run the first couple of Q^m A circuits under a noise model built
     from FakeFez's real calibration data, restricted to the ~17 qubits actually used (see
     restricted_noise below -- using the full 156-qubit backend noise model here would make
     Aer allocate a statevector sized to the whole chip for a circuit that only touches a
     fraction of it).

Run: `uv run python experiment.py`   (~7 min; the compound circuit's controlled, regime-gated
rain state prep is far more gate-dense per Grover step than the single-variable build was, so
K_MAX and the noisy-run budget are both smaller here -- see K_MAX, NOISY_MS, NOISY_SHOTS below.)
"""

import json
import os
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from qiskit import transpile
from qiskit.transpiler import CouplingMap
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_aer.noise.device import basic_device_gate_errors, basic_device_readout_errors
from qiskit_ibm_runtime.fake_provider import FakeFez
from scipy.stats import qmc

import copula
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
K_MAX = 7  # max Grover power m=32; exact_hit_probs' single-circuit simulation cost grows with
# total gates (~size(A) + m*size(Q)), and the compound circuit's Q is ~5x flood.py's -- K_MAX=11
# (m up to 512) would take the better part of an hour here. See README for the tradeoff.
FIT_FROM_K = 3
TRIALS = 500
BOOT = 2000
EPS_TARGETS = [1e-3, 3e-4, 1e-4]
ARMS = {
    "qae": ("MLAE (quantum)", "C0"),
    "mc": ("plain Monte Carlo", "C1"),
    "qmc": ("Sobol QMC (classical, 2-D)", "C2"),
}
NOISY_MS = [0, 1]  # smaller than the single-variable build's [0,1,2,4]: at ~1.8s/shot (m=0) and
# ~6s/shot (m=1) on this circuit's restricted-noise simulation, m=2 alone would cost ~20+ minutes.
NOISY_SHOTS = 40


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


def _connected_patch(adj: dict[int, set[int]], n: int) -> list[int]:
    """BFS outward from qubit 0 on a coupling graph until n qubits are collected."""
    patch, seen, frontier = [0], {0}, [0]
    while len(patch) < n:
        nxt = sorted({nb for q in frontier for nb in adj[q]} - seen)
        if not nxt:
            raise RuntimeError("coupling graph has no connected patch this large")
        take = nxt[: n - len(patch)]
        patch += take
        seen |= set(take)
        frontier = take
    return patch


def restricted_noise(backend, n_qubits: int) -> tuple[NoiseModel, CouplingMap]:  # type: ignore[no-untyped-def]
    """Real IBM calibration data (FakeFez: a recorded snapshot of a 156-qubit Heron r2
    processor, shipped in qiskit-ibm-runtime -- no network call, no hardware job), restricted
    to a connected n_qubits patch of the real coupling graph and relabeled to 0..n_qubits-1.
    Building the noise model and transpile target this way, instead of
    AerSimulator.from_backend(backend) on the full 156-qubit target, keeps Aer from ever
    allocating a statevector sized to the whole chip for a circuit that only uses n_qubits of
    it (same pattern as quantum_eraser/eraser.py's 2-qubit restriction, generalized here to an
    arbitrary BFS-found patch)."""
    cmap = backend.coupling_map
    adj: dict[int, set[int]] = {q: set() for q in range(cmap.size())}
    for u, v in cmap.get_edges():
        adj[u].add(v)
        adj[v].add(u)
    patch = _connected_patch(adj, n_qubits)
    relabel = {q: i for i, q in enumerate(patch)}
    qset = set(patch)
    edges = [[relabel[u], relabel[v]] for u, v in cmap.get_edges() if u in qset and v in qset]
    nm = NoiseModel()
    for name, qs, err in basic_device_gate_errors(target=backend.target):
        if set(qs) <= qset:
            nm.add_quantum_error(err, name, [relabel[q] for q in qs])
    for qs, err in basic_device_readout_errors(target=backend.target):
        if set(qs) <= qset:
            nm.add_readout_error(err, [relabel[q] for q in qs])
    return nm, CouplingMap(edges)


BASIS_FEZ = ["cz", "rz", "sx", "x"]  # FakeFez's native gate set


def noisy_run(a_circ, q_circ, ideal: np.ndarray, a: float) -> dict:  # type: ignore[no-untyped-def]
    """Q^m A under FakeFez's real calibration data (restricted to the qubits used); MLAE on the
    noisy counts for the same schedule."""
    backend = FakeFez()
    nm, cmap = restricted_noise(backend, a_circ.num_qubits)
    sim = AerSimulator(noise_model=nm)
    obj = a_circ.metadata["obj"]
    hits = []
    for m in NOISY_MS:
        c = qae.circuit(a_circ, q_circ, m)
        c.measure_all()
        tc = transpile(c, basis_gates=BASIS_FEZ, coupling_map=cmap, optimization_level=1, seed_transpiler=0)
        counts = sim.run(tc, shots=NOISY_SHOTS, seed_simulator=m).result().get_counts()
        hits.append(sum(v for k, v in counts.items() if k[::-1][obj] == "1"))
    h = np.array(hits)
    est = qae.mlae(h, NOISY_SHOTS, NOISY_MS)
    return {"ms": NOISY_MS, "shots": NOISY_SHOTS, "p_noisy": (h / NOISY_SHOTS).tolist(), "p_ideal": ideal.tolist(),
            "mlae_noisy_estimate": est, "mlae_noisy_abs_err": abs(est - a)}  # fmt: skip


def _json_problem(p: dict) -> dict:
    """copula.problem()'s dict, minus the large ndarrays, with the rest made JSON-safe."""
    tide = {k: v for k, v in p["tide"].items() if k not in ("probs", "amax", "yrs")}
    rain = {k: v for k, v in p["rain"].items() if k != "probs"}
    return {
        "tide": tide, "rain": rain, "tide_threshold_bin": p["tide_threshold_bin"],
        "rain_threshold_bin": p["rain_threshold_bin"], "tau_assumed": p["tau_assumed"], "rho": p["rho"],
        "n_regimes": p["n_regimes"], "a_true": p["a_true"],
        "conditional_rain_probs": p["conditional_rain_probs"].tolist(),
    }  # fmt: skip


def run(k_max: int = K_MAX, trials: int = TRIALS, noisy: bool = True, out_name: str = "results") -> dict:
    p = copula.problem()
    a = p["a_true"]
    tide_probs, cond = p["tide"]["probs"], p["conditional_rain_probs"]
    tide_t, rain_t = p["tide_threshold_bin"], p["rain_threshold_bin"]
    a_circ = copula.state_prep(tide_probs, cond, tide_t, rain_t)
    q_circ = qae.grover(a_circ)
    full_ms = qae.schedule(k_max)
    p_hit = dict(zip(full_ms, qae.exact_hit_probs(a_circ, q_circ, full_ms)))
    rng = np.random.default_rng(0)

    ks = list(range(1, k_max + 1))
    q = np.array([qae.queries(SHOTS, qae.schedule(k)) for k in ks], dtype=float)
    est = {name: np.empty((len(ks), trials)) for name in ARMS}
    for i, k in enumerate(ks):
        ms = qae.schedule(k)
        probs = np.array([p_hit[m] for m in ms])
        n = int(q[i])
        for t in range(trials):
            est["qae"][i, t] = qae.mlae(rng.binomial(SHOTS, probs), SHOTS, ms)
            with warnings.catch_warnings():  # Sobol warns when n isn't a power of 2; the budgets
                warnings.simplefilter("ignore", UserWarning)  # here (2m+1 sums) never are.
                u = qmc.Sobol(d=2, scramble=True, seed=int(rng.integers(0, 2**31 - 1))).random(n)
            est["qmc"][i, t] = copula.compound_hits(tide_probs, cond, tide_t, rain_t, u[:, 0], u[:, 1]).mean()
        # N iid draws from the binned joint model counted against both thresholds is exactly Binomial(N, a).
        est["mc"][i] = rng.binomial(n, a, size=trials) / n

    fit = slice(FIT_FROM_K - 1, None)
    sc = {name: scaling(q[fit], e[fit], a, rng) for name, e in est.items()}
    matched = []
    for e in EPS_TARGETS:
        need = {name: s["_need_boot"][e] for name, s in sc.items()}
        row: dict = {"eps": e, "rel_eps": e / a, "mc_queries_analytic": a * (1 - a) / e**2}
        for name in ARMS:
            row[f"{name}_queries"] = float(np.median(need[name]))
        for name in ("mc", "qmc"):
            ratio = need[name] / need["qae"]
            row[f"{name}_over_qae"] = float(np.median(ratio))
            row[f"{name}_over_qae_ci"] = np.percentile(ratio, [2.5, 97.5]).tolist()
        matched.append(row)
    for s in sc.values():
        del s["_need_boot"]

    r = {name: rmse(e, a) for name, e in est.items()}
    out = {
        "problem": _json_problem(p),
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
    ax.set_ylabel(f"RMSE of estimated P(tide >= NWS minor AND rain >= 10yr), a = {a:.4f}")
    ax.set_title(f"Key West compound tide+rain tail, {out['trials']} trials per point")
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
