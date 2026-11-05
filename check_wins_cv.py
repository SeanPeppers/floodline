"""Skeptic check for the dimension axis: CMC+QMC with a control variate = the same conditional
integrand at nominal epistemic parameters (same Sobol point), whose mean is known in advance."""

import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.stats import qmc

import experiment_wins as ew
import multidriver as md

N_EXTRA = 8
PIN = np.r_[ew.MID, 0.5, 0.5, 0.5]


def setup():  # type: ignore[no-untyped-def]
    drain = md.calibrate_drainage()
    return (drain, *ew.gev_uncertainty())


def pinned_ref(job):  # type: ignore[no-untyped-def]
    seed, ctx = job
    e = ew.epi(N_EXTRA, ctx)
    u = qmc.Sobol(4, scramble=True, seed=seed).random_base2(20)
    return float(np.mean([e.cond_prob(np.hstack([u[i : i + ew.CHUNK], np.tile(PIN, (ew.CHUNK, 1))])).mean()
                          for i in range(0, len(u), ew.CHUNK)]))  # fmt: skip


def rep(job):  # type: ignore[no-untyped-def]
    seed, log2n, ctx = job
    e = ew.epi(N_EXTRA, ctx)
    u = qmc.Sobol(e.d - 1, scramble=True, seed=seed).random_base2(log2n)
    f = e.cond_prob(u)
    pin = u.copy()
    pin[:, 4:] = PIN
    return float(f.mean()), float((f - e.cond_prob(pin)).mean())


if __name__ == "__main__":
    ctx = setup()
    a = json.loads(Path("results_wins.json").read_text())["dim"]["13"]["a"]
    with Pool(int(sys.argv[1]) if len(sys.argv) > 1 else 2) as pool:
        a_pin = float(np.mean(pool.map(pinned_ref, [(9000 + i, ctx) for i in range(16)])))
        print("a_pin", a_pin, flush=True)
        for log2n in (14, 16, 18):
            r = np.array(pool.map(rep, [(7000 + i, log2n, ctx) for i in range(24)]))
            rm_plain = np.sqrt(((r[:, 0] - a) ** 2).mean())
            rm_cv = np.sqrt(((r[:, 1] + a_pin - a) ** 2).mean())
            print(f"N=2^{log2n}: rmse plain {rm_plain:.2e} (cost N)  cv {rm_cv:.2e} (cost 2N)", flush=True)
