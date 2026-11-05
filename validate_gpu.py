"""Exact statevector check of the five-driver circuit at 20-32 qubits on a GPU (Aer + cuStateVec).

Same method as test_multidriver.py: qae.exact_hit_probs composes the un-flattened A and Q with
save_probabilities checkpoints and decomposes once. Here its AerSimulator is pointed at the GPU in
double precision. P(obj = 1) after Q^m A is compared with sin^2((2m+1) theta), a = Model.exact().
A complex128 statevector takes 16 * 2**n bytes: 32 GB at 31 qubits (fits a 40 GB A100), 64 GB at
32 (needs an 80 GB GPU). q31 and q32 were not run: Colab gave us only a 24 GB L4.

Run: `python validate_gpu.py [GPU|CPU] [config names...]` (needs qiskit-aer-gpu for GPU); results
are appended to validate_gpu_results.json in the working directory. Needs the multidriver.py that
fits the rain marginals with rainfall.fit_gev.
"""

import json
import sys
import time
from functools import partial
from pathlib import Path

import numpy as np
from qiskit_aer import AerSimulator

import multidriver as md
import multidriver_circuit as mc
import qae

BASE = md.Config(z_ft=2.0, delta_ft=1.0, n_w=2, n_s=1, n_o=1, n_p24=2, n_p3=1, regime_bits=1, n_k=3, g_drop=1)
CONFIGS = {  # name: (overrides of BASE, Grover powers m)
    "q20": ({}, [0, 1, 2, 4]),
    "q23": ({"n_w": 3, "n_p3": 2, "delta_ft": 0.5}, [0, 1, 2, 4]),
    "q26": ({"n_w": 3, "n_s": 2, "n_p24": 3, "n_p3": 2, "delta_ft": 0.5}, [0, 1, 2, 4]),
    "q29": ({"n_w": 3, "n_s": 2, "n_o": 2, "n_p24": 3, "n_p3": 2, "n_k": 4, "delta_ft": 0.5}, [0, 1, 2, 4]),
    "q30": ({"n_w": 4, "n_s": 2, "n_p24": 3, "n_p3": 2, "n_k": 4, "delta_ft": 0.25}, [0, 1, 2]),
    "q31": ({"n_w": 4, "n_s": 2, "n_o": 2, "n_p24": 3, "n_p3": 2, "n_k": 4, "delta_ft": 0.25}, [0, 1, 2]),
    "q32": ({"n_w": 4, "n_s": 2, "n_o": 2, "n_p24": 3, "n_p3": 3, "n_k": 4, "delta_ft": 0.25}, [0, 1, 2]),
}
OUT = Path("validate_gpu_results.json")


def run(name: str, device: str, drain: md.Drainage) -> dict:
    over, ms = CONFIGS[name]
    m = md.Model(md.replace(BASE, **over), drain)
    a = m.exact()
    a_circ, q_circ, lay = mc.build(m)
    a_cx = int(a_circ.decompose(reps=6).count_ops().get("cx", 0))
    qae.AerSimulator = partial(AerSimulator, device=device, precision="double")
    t0 = time.time()
    sim = qae.exact_hit_probs(a_circ, q_circ, ms)
    wall = time.time() - t0
    law = np.sin((2 * np.array(ms) + 1) * np.arcsin(np.sqrt(a))) ** 2
    rec = {"config": name, "device": device, "total_qubits": lay["total_qubits"], "data_qubits": lay["data_qubits"],
           "nbits": m.nbits, "n_k": m.cfg.n_k, "a": a, "ms": ms, "sim": sim.tolist(), "law": law.tolist(),
           "max_abs_err": float(np.abs(sim - law).max()), "A_cx_flat": a_cx, "A_toffoli": mc.count_a(m)["toffoli"],
           "wall_s": wall}  # fmt: skip
    print(json.dumps(rec), flush=True)
    return rec


if __name__ == "__main__":
    device = sys.argv[1] if len(sys.argv) > 1 else "GPU"
    names = sys.argv[2:] or list(CONFIGS)
    drain = md.calibrate_drainage()
    results = json.loads(OUT.read_text()) if OUT.exists() else []
    for name in names:
        results.append(run(name, device, drain))
        OUT.write_text(json.dumps(results, indent=1))
        assert results[-1]["max_abs_err"] < 1e-9, results[-1]
