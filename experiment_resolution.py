"""Two checks the 2-driver study raised, on the five-driver model (street 3.0 ft, 2050, Intermediate):

  1. Does discretization hide QMC's dimension penalty? Fit Sobol QMC's (and conditional MC +
     Sobol's) exponent at three grid resolutions: coarse, the benchmark grid, and fine.
  2. State preparation vs enumeration. A discretized model on n data qubits has 2**n joint cells;
     exact classical enumeration gives a with zero error at that cost (less with the rain leaf
     integrated exactly). Count A's logical gates at each resolution (multidriver_circuit.count_a,
     the same emission code as the validated circuit, without materializing it) next to both
     enumeration costs, up to a resolution where enumeration is out of reach.

Same fitting, replicate and bootstrap conventions as experiment_multi.py.
Run: `uv run python experiment_resolution.py` (about 1 h on 4 busy cores). Writes
results_multi_resolution.json and results_multi_resolution.png.
"""

from __future__ import annotations

import json
import time
from multiprocessing import Pool
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import qmc

import experiment_multi as em
import multidriver as md
import multidriver_circuit as mc

ROOT = Path(__file__).resolve().parent
BASE = md.Config(z_ft=em.Z_FT)
LEVELS = {
    "coarse": md.replace(BASE, delta_ft=0.5, n_w=4, n_s=2, n_o=1, n_p24=3, n_p3=3, regime_bits=2, n_k=6, g_drop=1),
    "benchmark": BASE,
    "fine": md.replace(BASE, delta_ft=1 / 32, n_w=8, n_s=6, n_o=5, n_p24=7, n_p3=7, n_k=8, g_drop=2),
    "finer": md.replace(BASE, delta_ft=1 / 64, n_w=9, n_s=7, n_o=6, n_p24=8, n_p3=8, n_k=9, g_drop=3),
}
SAMPLED = ("coarse", "benchmark", "fine")  # "finer" is costed only
REPS = 64
_MODELS: dict[md.Config, md.Model] = {}


def get_model(cfg: md.Config) -> md.Model:
    if cfg not in _MODELS:
        _MODELS[cfg] = md.Model(cfg)
    return _MODELS[cfg]


def one_rep(job: tuple[md.Config, str, int]) -> np.ndarray:
    cfg, arm, seed = job
    m = get_model(cfg)
    dims = len(m.random) - (1 if arm == "cmc_qmc" else 0)
    u = qmc.Sobol(d=dims, scramble=True, seed=seed).random_base2(em.M_MAX)
    step = 2**16  # the fine grid has 128-bin rows; keep per-worker arrays small
    if arm == "qmc":
        y = np.concatenate([m.indicator(m.bins_from_u(u[i : i + step])) for i in range(0, len(u), step)])
    else:
        y = np.concatenate([m.cond_prob(m.bins_from_u_nonleaf(u[i : i + step])) for i in range(0, len(u), step)])
    return np.cumsum(y.astype(float))[em.NS - 1] / em.NS


def main() -> None:
    rng = np.random.default_rng(7)
    out: dict = {"reps": REPS, "ns": em.NS.tolist(), "levels": {}}
    with Pool(em.WORKERS) as pool:
        for name, cfg in LEVELS.items():
            t0 = time.time()
            m = get_model(cfg)
            lv: dict = {"config": {k: v for k, v in cfg.__dict__.items() if k != "gev"}, "nbits": m.nbits,
                        "data_qubits": sum(m.nbits.values()), "grid_cells": m.grid_size(),
                        "nonleaf_cells": m.grid_size() // 2 ** m.nbits[m.leaf], "A": mc.count_a(m)}  # fmt: skip
            if name in SAMPLED:
                a = m.exact()
                lv["a"] = a
                for arm in ("qmc", "cmc_qmc"):
                    seeds = rng.integers(0, 2**31 - 1, REPS)
                    est = np.array(pool.map(one_rep, [(cfg, arm, int(s)) for s in seeds]))
                    lv[arm] = em.fit(em.NS.astype(float), est, a, rng)
                lv["qae"] = em.qae_arm(a, rng, pool)
            out["levels"][name] = lv
            print(f"{name}: data qubits {lv['data_qubits']}, A {lv['A']['cx_equiv']:.3g} CX-eq, "
                  f"enum {lv['nonleaf_cells']:.3g}/{lv['grid_cells']:.3g}"
                  + (f", a={lv['a']:.5f} qmc {lv['qmc']['alpha']:.2f} cmc_qmc {lv['cmc_qmc']['alpha']:.2f}" if "a" in lv else "")
                  + f" ({time.time() - t0:.0f}s)", flush=True)  # fmt: skip
            (ROOT / "results_multi_resolution.json").write_text(json.dumps(em.strip(out), indent=1, default=int))
    plot(em.strip(out))


def plot(out: dict) -> None:
    lv = out["levels"]
    names = list(lv)
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(12, 4.6))
    xs = [lv[n]["data_qubits"] for n in names]
    ax.semilogy(
        xs, [lv[n]["grid_cells"] for n in names], "o-", color="C1", label="exact enumeration, full joint (2^n cells)"
    )
    ax.semilogy(
        xs, [lv[n]["nonleaf_cells"] for n in names], "o--", color="C5", label="exact enumeration, rain burst integrated"
    )
    ax.semilogy(xs, [lv[n]["A"]["cx_equiv"] for n in names], "s-", color="C0", label="gates in one A (CX-equivalent)")
    ax.semilogy(xs, [lv[n]["A"]["toffoli"] for n in names], "s:", color="C0", label="Toffolis in one A")
    for n, x in zip(names, xs):
        ax.annotate(n, (x, lv[n]["grid_cells"]), textcoords="offset points", xytext=(4, 4), fontsize=8)
    ax.set_xlabel("data qubits (resolution of the discretized model)")
    ax.set_ylabel("count")
    ax.set_title("cost of one quantum query vs the whole classical answer")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7)
    sampled = [n for n in names if "a" in lv[n]]
    for arm, col, label in (
        ("qmc", "C2", "Sobol QMC"),
        ("cmc_qmc", "C3", "conditional MC + Sobol"),
        ("qae", "C0", "MLAE (ideal)"),
    ):
        al = [lv[n][arm]["alpha"] for n in sampled]
        ci = np.array([lv[n][arm]["alpha_ci"] for n in sampled])
        sx = [lv[n]["data_qubits"] for n in sampled]
        bx.errorbar(
            sx, al, yerr=[np.subtract(al, ci[:, 0]), ci[:, 1] - al], fmt="o-", color=col, capsize=3, label=label
        )
    bx.axhline(2 * 5 / 6, color="gray", ls="--", lw=0.8, label="He-Owen 2d/(d+1), d=5")
    bx.set_xlabel("data qubits (resolution)")
    bx.set_ylabel("alpha (queries ~ eps^-alpha), 95% CI")
    bx.set_title("does discretization hide QMC's dimension penalty? (d=5)")
    bx.grid(True, alpha=0.3)
    bx.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(ROOT / "results_multi_resolution.png", dpi=130)


if __name__ == "__main__":
    main()
