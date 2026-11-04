"""Smoke test: circuit correctness against qiskit's reference sampler and the closed-form
Grover law, MC-binomial equivalence, then a tiny end-to-end run.

Run: `uv run python smoke_test.py`  (~3 min)
"""

import numpy as np
from qiskit.primitives import StatevectorSampler

import copula
import experiment
import flood
import qae

p = flood.problem()
a = p["a_true"]
assert 0 < a < 0.2 and abs(a - p["empirical_exceed"] / p["n_years"]) < 0.05, a

A = qae.state_prep(p["probs"], p["threshold_bin"])
Q = qae.grover(A)
ms = [0, 1, 2, 4]
exact = qae.exact_hit_probs(A, Q, ms)
theta = np.arcsin(np.sqrt(a))
law = np.sin((2 * np.array(ms) + 1) * theta) ** 2
assert np.abs(exact - law).max() < 1e-9, (exact, law)
print(f"exact P(obj=1) matches sin^2((2m+1)theta): max |diff| = {np.abs(exact - law).max():.1e}")

# The fast path (exact probs + binomial shots) must agree with real circuit sampling.
shots = 20000
obj = A.metadata["obj"]
for m, pe in zip(ms[:3], exact[:3]):
    c = qae.circuit(A, Q, m)
    c.measure_all()
    counts = StatevectorSampler(seed=m).run([c], shots=shots).result()[0].data.meas.get_counts()
    ps = sum(v for k, v in counts.items() if k[::-1][obj] == "1") / shots
    assert abs(ps - pe) < 5 * np.sqrt(pe * (1 - pe) / shots) + 1e-9, (m, ps, pe)
    print(f"m={m}: StatevectorSampler {ps:.4f} vs exact {pe:.4f}")

# Classical draws from the binned distribution are Binomial(N, a): check on real draws.
rng = np.random.default_rng(1)
draws = rng.choice(len(p["probs"]), size=200000, p=p["probs"])
mc = (draws >= p["threshold_bin"]).mean()
assert abs(mc - a) < 5 * np.sqrt(a * (1 - a) / 200000), (mc, a)

assert abs(qae.mlae(np.round(law * 1000).astype(int), 1000, ms) - a) < 1e-3

# Regression guard for exact_hit_probs on the compound (tide+rain, entangled, controlled-gate)
# circuit specifically: an earlier version of exact_hit_probs flattened Q in isolation via
# transpile(..., basis_gates=["cx", "u"]) before composing, which silently produced the WRONG
# unitary for this circuit (passed fine on the simpler single-variable flood circuit above,
# so that check alone wouldn't have caught it) -- caught only by comparing against this
# closed-form law on the actual compound circuit.
pc = copula.problem()
Ac = copula.state_prep(
    pc["tide"]["probs"], pc["conditional_rain_probs"], pc["tide_threshold_bin"], pc["rain_threshold_bin"]
)
Qc = qae.grover(Ac)
ms_c = [0, 1, 2, 4]
exact_c = qae.exact_hit_probs(Ac, Qc, ms_c)
theta_c = np.arcsin(np.sqrt(pc["a_true"]))
law_c = np.sin((2 * np.array(ms_c) + 1) * theta_c) ** 2
assert np.abs(exact_c - law_c).max() < 1e-9, (exact_c, law_c)
print(f"compound circuit: exact P(obj=1) matches sin^2((2m+1)theta): max |diff| = {np.abs(exact_c - law_c).max():.1e}")

out = experiment.run(k_max=5, trials=40, noisy=False, out_name="smoke_results")
for b in out["budgets"]:
    assert np.isfinite(b["rmse_qae"]) and np.isfinite(b["rmse_mc"]), b
last = out["budgets"][-1]
assert last["rmse_qae"] < last["rmse_mc"] and last["rmse_qmc"] < last["rmse_mc"], last
print("\nsmoke test passed")
