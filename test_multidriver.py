"""Regression test for the multi-driver model and its circuits.

  1. The reduced-resolution circuit A (20 qubits, all five drivers, both adders, both QROMs, the
     comparator) gives P(obj = 1) = Model.exact(), and Q^m A follows sin^2((2m+1) theta), by exact
     statevector simulation (qae.exact_hit_probs: compose the un-flattened circuits, decompose once).
  2. The same for the d=2 code path (no adders, no groundwater register).
  3. Every classical arm in experiment_multi.py is unbiased for Model.exact() on real draws
     through the model: plain sampling, conditional MC, importance sampling.
  4. The integer runoff table is monotone in the rain bins, which conditional MC's bisection needs.
  5. The gate counter used for grids too big to build (count_a) matches the built circuit.
  6. The GEV rain marginals reproduce NOAA Atlas 14's published AMS depths (24 h and 3 h).

Run: `uv run python test_multidriver.py`  (~2 min)
"""

import numpy as np

import experiment_multi as em
import multidriver as md
import multidriver_circuit as mc
import qae

REDUCED = md.Config(z_ft=2.0, delta_ft=1.0, n_w=2, n_s=1, n_o=1, n_p24=2, n_p3=1, regime_bits=1, n_k=3, g_drop=1)
DRAIN = md.calibrate_drainage()


def _check_circuit(cfg: md.Config, ms: list[int], max_qubits: int) -> None:
    m = md.Model(cfg, DRAIN)
    a = m.exact()
    a_circ, q_circ, lay = mc.build(m)
    assert lay["total_qubits"] <= max_qubits, lay
    ops, counted = a_circ.count_ops(), mc.count_a(m)
    assert counted["toffoli"] == ops.get("ccx", 0) and counted["cx"] == ops.get("cx", 0), (counted, ops)
    exact = qae.exact_hit_probs(a_circ, q_circ, ms)
    law = np.sin((2 * np.array(ms) + 1) * np.arcsin(np.sqrt(a))) ** 2
    err = float(np.abs(exact - law).max())
    assert err < 1e-9, (cfg.drivers, exact, law)
    print(f"circuit {'+'.join(m.random)}: {lay['total_qubits']} qubits, a = {a:.6f}, max |P - law| = {err:.1e}")


def test_circuit_reduced_d5() -> None:
    _check_circuit(REDUCED, [0, 1, 2, 4], 24)


def test_circuit_reduced_d2() -> None:
    _check_circuit(md.replace(REDUCED, drivers=("W", "P24"), n_p24=3, g_drop=0), [0, 1, 3], 24)


def test_estimators_unbiased() -> None:
    m = md.Model(md.Config(), DRAIN)
    a = m.exact()
    rng = np.random.default_rng(3)
    n = 400_000
    u = rng.random((n, len(m.random)))
    hit = m.indicator(m.bins_from_u(u))
    assert abs(hit.mean() - a) < 5 * np.sqrt(a * (1 - a) / n), (hit.mean(), a)
    c = m.cond_prob(m.bins_from_u_nonleaf(rng.random((n, len(m.random) - 1))))
    assert abs(c.mean() - a) < 5 * c.std() / np.sqrt(n), (c.mean(), a)
    w = em.is_estimates(m, 2.0, rng.random((n, len(m.random))))
    assert abs(w.mean() - a) < 5 * w.std() / np.sqrt(n), (w.mean(), a)
    print(f"estimators unbiased at a = {a:.5f}: MC {hit.mean():.5f}, CMC {c.mean():.5f}, IS {w.mean():.5f}")


def test_rain_fit() -> None:
    pf = md.pfds_ams()
    t = 1 / np.array(md.rainfall.AMS_RETURN_PERIODS, dtype=float)
    for dur in ("24h", "3h"):
        depths = np.array(pf[dur])
        rel = np.abs(md.stats.genextreme.isf(t, *md.rainfall.fit_gev(depths)) - depths) / depths
        assert rel.max() < 0.06, (dur, rel)
        print(
            f"GEV {dur}: max relative error vs Atlas 14 AMS = {rel.max():.1%} (T = {md.rainfall.AMS_RETURN_PERIODS[rel.argmax()]} yr)"
        )


def test_runoff_monotone() -> None:
    m = md.Model(md.Config(), DRAIN)
    assert (np.diff(m.R, axis=0) >= 0).all() and (np.diff(m.R, axis=1) >= 0).all()
    assert (np.diff(m.T, axis=0) <= 0).all(), "more coastal water must never make flooding harder"


if __name__ == "__main__":
    test_rain_fit()
    test_runoff_monotone()
    test_estimators_unbiased()
    test_circuit_reduced_d2()
    test_circuit_reduced_d5()
    print("multidriver test passed")
