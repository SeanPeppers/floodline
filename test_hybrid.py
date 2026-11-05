"""Regression test for the hybrid estimator (hybrid.py, hybrid_circuit.py).

  1. The hybrid circuit A_h at reduced resolution (all four non-leaf drivers, the CV QROM, both
     adders, the T and p QROMs, the residual adder and the arcsin-sqrt rotation) gives
     P(obj = 1) = E[layer amplitude] from enumeration, and Q^m A_h follows sin^2((2m+1) theta),
     by exact statevector simulation (qae.exact_hit_probs). Every layer of a 2-level split.
  2. The gate counter matches the built circuit.
  3. ptab (P3 integrated by table lookup) equals Model.cond_prob (bisection) on all 2**18 cells.
  4. The estimator identity: cv_mean + combine(layer means) = E[Pq] / S, cv_mean from coarse
     cells equals the full-grid mean of g, and the fixed-point bias is inside its 2**-(b+1) bound.

Run: `uv run python test_hybrid.py`  (~1 min)
"""

import numpy as np

import hybrid as hy
import hybrid_circuit as hc
import multidriver as md
import qae

DRAIN = md.calibrate_drainage()


def test_circuit_reduced() -> None:
    m = md.Model(md.replace(md.Config(z_ft=2.0), **hy.SIM_GRID), DRAIN)
    t = hy.tables(m, hy.SIM_DROP, hy.SIM_BITS)
    # With 1-bit drops the coarse midpoint is the upper bin, so the real CV gives r <= 0 only. The
    # circuit does not care what the CV table holds, so a seeded random table exercises both signs.
    t.gq = np.random.default_rng(7).integers(0, t.scale + 1, t.gq.shape)
    b, w = hy.nonleaf_cells(m)
    r = t.residual(b)
    assert np.any(r > 0) and np.any(r < 0), "degenerate reduced model: residual has one sign"
    ms = [0, 1, 2, 4]
    parts = hy.layers(2, t.scale)
    for part in parts:
        a_circ, q_circ, lay = hc.build(t, part)
        assert lay["total_qubits"] <= hy.MAX_SIM_QUBITS, lay
        ops, counted = a_circ.count_ops(), hc.count(t, part)
        assert counted["toffoli"] == ops.get("ccx", 0) and counted["cx"] == ops.get("cx", 0), (counted, ops)
        a_k = float(w @ hy.encode(r, part))
        law = np.sin((2 * np.array(ms) + 1) * np.arcsin(np.sqrt(a_k))) ** 2
        exact = qae.exact_hit_probs(a_circ, q_circ, ms)
        err = float(np.abs(exact - law).max())
        assert err < 1e-9, (part, exact, law)
        print(f"layer {part}: {lay['total_qubits']} qubits, a_k = {a_k:.6f}, max |P - sin^2 law| = {err:.1e}")


def test_ptab_and_identity() -> None:
    m = md.Model(md.Config(z_ft=3.0), DRAIN)
    b, w = hy.nonleaf_cells(m)
    t = hy.tables(m, hy.DROPS["1k"])
    assert np.allclose(t.p_of(b), m.cond_prob(b), atol=1e-12), "ptab disagrees with Model.cond_prob"
    ex = hy.exact_parts(t)
    assert abs(hy.cv_mean(t) - ex["e_g"]) < 1e-12, (hy.cv_mean(t), ex["e_g"])
    r = t.residual(b)
    for n in (1, 3):
        parts = hy.layers(n, t.scale)
        y = [float(w @ hy.encode(r, p)) for p in parts]
        total = hy.cv_mean(t) + hy.combine(y, parts, t.scale)
        assert abs(total - ex["a_quantized"]) < 1e-12, (n, total, ex["a_quantized"])
    assert abs(ex["quant_bias"]) <= 0.5 / t.scale, ex
    print(f"ptab == cond_prob on {len(w)} cells; a = {ex['a']:.6f}, fixed-point bias {ex['quant_bias']:.1e}")


if __name__ == "__main__":
    test_ptab_and_identity()
    test_circuit_reduced()
    print("hybrid test passed")
