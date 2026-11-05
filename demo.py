"""Live demo: QAE vs plain Monte Carlo vs Sobol QMC converging on the Key West compound
tide+rain flood probability (realistic low-street rule, drainage.py), animated in real time. Judge-facing prop for the FGCU
Quantum Hackathon 2026 -- same estimators, same query accounting, same cached data and K_MAX
as experiment.py; this just animates the convergence instead of plotting it once. Reuses
`EPS_TARGETS[0]` (eps=1e-3 absolute, the first row of the matched_eps table already verified
in README.md) as the "converged" band, so the on-screen markers are the exact numbers already
reported, not new ones.

Run: `uv run python demo.py`  (precompute ~40s -- dominated by the same exact_hit_probs call
experiment.py makes -- then a ~40s animated window)
"""

import json
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import animation
from scipy.stats import qmc

import copula
import qae
from experiment import ARMS, EPS_TARGETS, K_MAX, SHOTS

ROOT = Path(__file__).resolve().parent
SUBFRAMES = 8  # interpolated animation frames between each real budget point
HOLD_FRAMES = 15  # extra frames holding the final state so judges can read it
INTERVAL_MS = 500


def precompute() -> dict:
    """One live seeded trial per budget per arm (not an average) -- the jitter is the point: it is
    what makes the RMSE-vs-queries gap in README.md visible instead of abstract. The "converged"
    markers below are NOT re-derived from this one noisy run; they are read straight out of
    results.json's matched_eps table (the already-verified, 500-trial, bootstrap-CI numbers), so a
    particular unlucky live draw can never contradict the reported claim.
    """
    p = copula.problem()
    a = p["a_true"]
    tide_probs, cond, mask = p["tide"]["probs"], p["conditional_rain_probs"], p["mask"]
    a_circ = copula.state_prep(tide_probs, cond, p["a_tab"], p["b_tab"])
    q_circ = qae.grover(a_circ)
    ks = list(range(1, K_MAX + 1))
    q = np.array([qae.queries(SHOTS, qae.schedule(k)) for k in ks], dtype=float)
    p_hit = dict(zip(qae.schedule(K_MAX), qae.exact_hit_probs(a_circ, q_circ, qae.schedule(K_MAX))))
    rng = np.random.default_rng(0)

    est = {name: np.empty(len(ks)) for name in ARMS}
    for i, k in enumerate(ks):
        ms = qae.schedule(k)
        probs = np.array([p_hit[m] for m in ms])
        n = int(q[i])
        est["qae"][i] = qae.mlae(rng.binomial(SHOTS, probs), SHOTS, ms)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            u = qmc.Sobol(d=2, scramble=True, seed=int(rng.integers(0, 2**31 - 1))).random(n)
        est["qmc"][i] = copula.compound_hits(tide_probs, cond, mask, u[:, 0], u[:, 1]).mean()
        est["mc"][i] = rng.binomial(n, a) / n

    matched = next(
        row for row in json.loads((ROOT / "results.json").read_text())["matched_eps"] if row["eps"] == EPS_TARGETS[0]
    )
    conv = {name: matched[f"{name}_queries"] for name in ARMS}
    return {"a": a, "q": q, "est": est, "conv": conv, "eps_band": EPS_TARGETS[0]}


def build_anim(data: dict) -> animation.FuncAnimation:
    a, q, est, conv, eps_band = data["a"], data["q"], data["est"], data["conv"], data["eps_band"]
    n_seg = len(q) - 1
    total_frames = n_seg * SUBFRAMES + 1 + HOLD_FRAMES

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.set_xscale("log")
    ax.set_xlim(q[0] * 0.8, q[-1] * 1.3)
    ax.set_ylim(0, max(est[n].max() for n in ARMS) * 1.3 + a)
    ax.axhline(a, color="k", ls="--", lw=1, label=f"true P(low-street flood >= 6 in) = {a:.4f}")
    ax.axhspan(a - eps_band, a + eps_band, color="k", alpha=0.08, label=f"converged band (+/-{eps_band:.0e})")
    ax.set_xlabel("oracle queries so far (= classical draws, log scale)")
    ax.set_ylabel("running probability estimate")
    ax.set_title("Key West compound tide+rain flood probability: quantum vs. classical, live")
    ax.grid(True, which="both", alpha=0.25)

    lines = {
        name: ax.plot([], [], "-o", color=col, label=lab, markevery=[-1], ms=8)[0] for name, (lab, col) in ARMS.items()
    }
    qtext = ax.text(0.02, 0.95, "", transform=ax.transAxes, va="top", fontsize=11, family="monospace")
    marked: dict[str, bool] = {name: False for name in ARMS}
    ax.legend(loc="lower right", fontsize=8)

    def interp(frame: int) -> tuple[int, float]:
        pos = min(frame / SUBFRAMES, n_seg)
        seg = min(int(pos), n_seg - 1)
        return seg, pos - seg

    def frame_query(frame: int) -> float:
        seg, frac = interp(frame)
        return float(np.exp(np.log(q[seg]) * (1 - frac) + np.log(q[seg + 1]) * frac))

    def update(frame: int) -> list:
        seg, frac = interp(frame)
        q_cur = frame_query(frame)
        for name, line in lines.items():
            y_cur = est[name][seg] * (1 - frac) + est[name][seg + 1] * frac
            xs = np.append(q[: seg + 1], q_cur)
            ys = np.append(est[name][: seg + 1], y_cur)
            line.set_data(xs, ys)
            if not marked[name] and conv[name] is not None and q_cur >= conv[name]:
                marked[name] = True
                ax.axvline(conv[name], color=ARMS[name][1], ls=":", lw=1.5, alpha=0.8)
                ax.annotate(f"{ARMS[name][0]}\nconverged: {conv[name]:,.0f}q", (conv[name], a),
                            xytext=(8, 25 + 25 * list(ARMS).index(name)), textcoords="offset points",
                            fontsize=8, color=ARMS[name][1])  # fmt: skip
        qtext.set_text(f"queries so far: {q_cur:,.0f}")
        return [*lines.values(), qtext]

    return animation.FuncAnimation(fig, update, frames=total_frames, interval=INTERVAL_MS, blit=False, repeat=True)


if __name__ == "__main__":
    data = precompute()
    assert 0 < data["a"] < 1
    # QAE and QMC must converge on-screen -- that's the demo's point. Plain MC's convergence
    # point (>100k queries, vs. ~13k animated here) is legitimately off-screen: it needing far
    # more queries than is practical to animate within K_MAX IS the visible result, not a bug.
    for name in ("qae", "qmc"):
        assert data["q"][-1] >= data["conv"][name], f"K_MAX too small: {name}'s marker falls outside the animated range"
    print(f"true a = {data['a']:.5f}; queries to reach +/-{data['eps_band']:.0e} (from results.json):", data["conv"])
    ani = build_anim(data)
    plt.tight_layout()
    plt.show()
