"""Smallest honest QAE run on real IBM hardware: Key West compound flood, one qubit per driver.

The 2-driver "rectangle" model from copula.py (annual-max tide >= NWS minor flood stage AND
annual-max 24-h rain >= the 10-year depth, Gaussian-copula coupled) coarsened to one bit per
driver. The coarsening is exact for this rule, because the rectangle event only depends on which
side of each threshold the driver falls:
    P(tide high), P(rain high | tide high), P(rain high | tide low)
are summed from the real discretized model, and a = P(tide high) * P(rain high | tide high)
equals copula.problem("rectangle")["a_true"] (asserted below).

A (3 qubits): RY loads the tide bit, RY + CRY load the rain bit given the tide bit, a Toffoli sets
the objective qubit iff both are high. Q = A S0 A^dagger S_chi, so P(obj = 1) after Q^m A is
sin^2((2m + 1) theta) with a = sin^2(theta).

    uv run python hw_demo.py dry   # ideal + noisy simulation of the chosen backend's snapshot, no account
    uv run python hw_demo.py run   # real QPU via the saved IBM Quantum account (or QISKIT_IBM_TOKEN)

Writes results_hw.json. This is a demonstration that the circuit runs on hardware and how
quickly noise erases the Grover signal, not a speed claim: on today's hardware classical wins.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.quantum_info import Statevector

import copula
import qae

ROOT = Path(__file__).resolve().parent
MS = [0, 1, 2, 3, 4, 5, 6]  # Grover depths plotted; MLAE uses the MLAE_MS subset
MLAE_MS = [0, 1, 2, 4]
SHOTS = 4000
MAX_EXECUTION_S = 300  # hard cap on billed QPU time for the whole job (5 of the 10 hackathon minutes)


def coarse_probs() -> dict:
    p = copula.problem("rectangle")
    tp, tt, rt = p["tide"]["probs"], p["tide_threshold_bin"], p["rain_threshold_bin"]
    rain_hi_by_bin = p["conditional_rain_probs"][:, rt:].sum(axis=1)[copula.regimes(len(tp), p["n_regimes"])]
    p_tide = float(tp[tt:].sum())
    p_rain_hi = float((tp[tt:] * rain_hi_by_bin[tt:]).sum() / p_tide)
    p_rain_lo = float((tp[:tt] * rain_hi_by_bin[:tt]).sum() / (1 - p_tide))
    a = p_tide * p_rain_hi
    assert abs(a - p["a_true"]) < 1e-12, (a, p["a_true"])
    return {"p_tide_high": p_tide, "p_rain_high_given_tide_high": p_rain_hi,
            "p_rain_high_given_tide_low": p_rain_lo, "a": a}  # fmt: skip


def a_circ(c: dict) -> QuantumCircuit:
    ang = lambda p: 2 * np.arcsin(np.sqrt(p))
    qc = QuantumCircuit(3, name="A")
    qc.ry(ang(c["p_tide_high"]), 0)
    qc.ry(ang(c["p_rain_high_given_tide_low"]), 1)
    qc.cry(ang(c["p_rain_high_given_tide_high"]) - ang(c["p_rain_high_given_tide_low"]), 0, 1)
    qc.ccx(0, 1, 2)
    return qc


def q_circ(a: QuantumCircuit) -> QuantumCircuit:
    qc = QuantumCircuit(3, name="Q")
    qc.z(2)  # S_chi: flip the sign of the flood states
    qc.compose(a.inverse(), inplace=True)
    qc.x([0, 1, 2])  # S_0 = reflection about |000>, up to a global phase
    qc.h(2)
    qc.ccx(0, 1, 2)
    qc.h(2)
    qc.x([0, 1, 2])
    qc.compose(a, inplace=True)
    return qc


def grover_circuits(a: QuantumCircuit) -> list[QuantumCircuit]:
    q = q_circ(a)
    out = []
    for m in MS:
        qc = a.copy()
        for _ in range(m):
            qc.compose(q, inplace=True)
        qc.measure_all()
        qc.name = f"m{m}"
        out.append(qc)
    return out


def ideal_law(a: float) -> list[float]:
    th = np.arcsin(np.sqrt(a))
    return [float(np.sin((2 * m + 1) * th) ** 2) for m in MS]


def check_against_closed_form(a: QuantumCircuit, target: float) -> float:
    """Statevector P(obj = 1) for every m vs sin^2((2m+1) theta); returns the max error."""
    q = q_circ(a)
    sv = Statevector(a)
    errs = []
    for m, law in zip(MS, ideal_law(target)):
        if m:
            sv = sv.evolve(q)
        errs.append(abs(float(sv.probabilities([2])[1]) - law))
    return max(errs)


def p_obj(counts: dict) -> float:
    total = sum(counts.values())
    return sum(v for k, v in counts.items() if (int(k.replace(" ", ""), 2) >> 2) & 1) / total  # objective = clbit 2


def mlae_from(ps: list[float]) -> float:
    hits = np.array([round(ps[MS.index(m)] * SHOTS) for m in MLAE_MS])
    return qae.mlae(hits, SHOTS, MLAE_MS)


def summarize(label: str, ps: list[float], a_true: float) -> dict:
    est = mlae_from(ps)
    print(f"{label:>10}: " + "  ".join(f"m{m}={p:.3f}" for m, p in zip(MS, ps)) + f"  | MLAE a={est:.4f}")
    return {"p_obj": ps, "mlae_a": est, "abs_err": abs(est - a_true)}


def main(mode: str) -> None:
    c = coarse_probs()
    a = a_circ(c)
    err = check_against_closed_form(a, c["a"])
    assert err < 1e-12, f"circuit disagrees with sin^2 law by {err:.2e}"
    law = ideal_law(c["a"])
    print(f"a = P(tide >= NWS minor AND rain >= 10-yr) = {c['a']:.5f}; circuit vs closed form max err {err:.1e}")
    circuits = grover_circuits(a)

    from qiskit_aer import AerSimulator
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    if mode == "dry":
        from qiskit_ibm_runtime.fake_provider import FakeFez

        backend = FakeFez()
    else:
        service = QiskitRuntimeService()
        backend = service.least_busy(operational=True, simulator=False, min_num_qubits=3)
    isa = transpile(circuits, backend, optimization_level=3, seed_transpiler=7)
    two_q = [sum(v for k, v in t.count_ops().items() if k in ("cz", "ecr", "cx")) for t in isa]
    print(f"backend {backend.name}: two-qubit gates per circuit {two_q}")

    out = {"backend": backend.name, "shots": SHOTS, "ms": MS, "mlae_ms": MLAE_MS, "model": c,
           "closed_form_max_err": err, "ideal_p_obj": law, "two_qubit_gates": two_q}  # fmt: skip
    summarize("ideal", law, c["a"])
    noisy = AerSimulator.from_backend(backend).run(isa, shots=SHOTS, seed_simulator=11).result()
    out["noisy_sim"] = summarize("noisy sim", [p_obj(noisy.get_counts(i)) for i in range(len(MS))], c["a"])

    if mode == "run":
        sampler = SamplerV2(mode=backend)
        sampler.options.max_execution_time = MAX_EXECUTION_S
        sampler.options.dynamical_decoupling.enable = True
        t0 = time.time()
        job = sampler.run(isa, shots=SHOTS)
        print(f"submitted job {job.job_id()} to {backend.name}; waiting...")
        res = job.result()
        ps = [p_obj(r.data.meas.get_counts()) for r in res]
        out["hardware"] = summarize("hardware", ps, c["a"])
        out["hardware"].update({"job_id": job.job_id(), "wall_s": round(time.time() - t0, 1),
                                "usage_s": job.usage(), "date": time.strftime("%Y-%m-%d")})  # fmt: skip
        print(f"QPU usage {out['hardware']['usage_s']} s")

    path = ROOT / ("results_hw.json" if mode == "run" else "results_hw_dry.json")
    path.write_text(json.dumps(out, indent=1))
    print(f"wrote {path.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("dry", "run"):
        sys.exit("usage: hw_demo.py dry|run")
    main(sys.argv[1])
