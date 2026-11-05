"""Floodline CLI: annual compound flood probability for a Key West street.

  uv run python floodline_cli.py --year 2050 --scenario intermediate --elevation 3.0
  uv run python floodline_cli.py --year 2070 --scenario high --elevation 4 --exposure

The answer comes from the best classical estimator on the five-driver model (multidriver.py):
conditional Monte Carlo (rain burst integrated exactly) on scrambled Sobol points, with a 95%
interval from independent scrambles. Model uncertainty, which is far larger, is shown separately:
the GEV fit (parametric bootstrap of the 110 annual maxima) and the unsourced tide-rain
dependence (tau 0.1 to 0.3). The QAE line says what an ideal, fault-free quantum computer would
need to match the classical interval, using the circuit counts in results_multi.json.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.stats import qmc

import flood
import multidriver as md
import qae

ROOT = Path(__file__).resolve().parent
SCRAMBLES, LOG2_POINTS = 16, 14
GEV_BOOT = 30
NAMES = {"W": "peak water level (tide + surge)", "P24": "24-h rainfall", "P3": "3-h rain burst",
         "S": "sea-level rise to target year", "O": "groundwater offset"}  # fmt: skip


def grid_for(year: int, scenario: str, z: float, tau: float) -> md.Config:
    """Benchmark grid, widened for S when the SLR spread is large (late century, high scenario)."""
    _, s_lo, s_hi = md.slr_offset_ft(year, scenario)
    d = md.Config().delta_ft
    n_s = max(2, math.ceil(math.log2(max(8 * max(s_lo, s_hi) / d, 1))))
    return md.Config(year=year, scenario=scenario, z_ft=z, tau_wp=tau, n_s=n_s)


def estimate(m: md.Model, seed: int = 0, scrambles: int = SCRAMBLES, log2_n: int = LOG2_POINTS) -> tuple[float, float]:
    """Conditional MC on scrambled Sobol: (mean, 95% half-width over independent scrambles)."""
    dims = len(m.nonleaf())
    est = [float(m.cond_prob(m.bins_from_u_nonleaf(qmc.Sobol(dims, seed=seed + i).random_base2(log2_n))).mean())
           for i in range(scrambles)]  # fmt: skip
    return float(np.mean(est)), float(1.96 * np.std(est, ddof=1) / np.sqrt(scrambles))


def gev_interval(cfg: md.Config, drain: md.Drainage) -> tuple[float, float]:
    """90% interval of the answer over a parametric bootstrap of the GEV fit."""
    _, amax, _, _ = flood.load_annual_maxima()
    c, loc, scale = flood.fit_gev(amax)
    rng = np.random.default_rng(1)
    vals = []
    for _ in range(GEV_BOOT):
        resample = stats.genextreme.rvs(c, loc, scale, size=len(amax), random_state=rng)
        g = flood.fit_gev(resample)
        vals.append(estimate(md.Model(replace(cfg, gev=g), drain), scrambles=4, log2_n=12)[0])
    lo, hi = np.percentile(vals, [5, 95])
    return float(lo), float(hi)


def qae_line(a: float, half_width: float) -> str:
    path = ROOT / "results_multi.json"
    if not path.exists():
        return "QAE estimate unavailable: run `uv run python experiment_multi.py` first."
    res = json.loads(path.read_text())
    cfg5 = res["studies"][next(iter(res["studies"]))]["configs"]["5"]
    fit = cfg5["arms"]["qae"]
    eps = half_width / 1.96  # match the classical interval's RMSE
    # MLAE queries scale as sqrt(a(1-a))/eps; transfer the measured d=5 constant to this a.
    a_ref = cfg5["a"]
    q_ref = math.exp(
        (math.log(eps * math.sqrt(a_ref * (1 - a_ref)) / math.sqrt(a * (1 - a))) - fit["intercept"]) / fit["slope"]
    )
    m_max = _m_for(q_ref)
    circ = res["circuits"]["5"]
    cx = circ["A"]["cx"] + m_max * circ["Q"]["cx"]
    tof = circ["A"]["toffoli"] + m_max * circ["Q"]["toffoli_excl_S0"]
    return (
        f"QAE (ideal, fault-free) to match +-{half_width:.1e}: ~{q_ref:,.0f} oracle queries, deepest circuit "
        f"Q^{m_max} A = {circ['A']['qubits']} logical qubits, {cx:,.0f} CX ({tof:,.0f} Toffoli). "
        f"Classical used {SCRAMBLES * 2**LOG2_POINTS:,} conditional samples (a ~6-step bisection of the "
        "flood rule each), seconds on a laptop."
    )


def _m_for(queries: float) -> int:
    for k in range(1, 40):
        if qae.queries(100, qae.schedule(k)) >= queries:
            return qae.schedule(k)[-1]
    return qae.schedule(39)[-1]


def exposure(year: int, scenario: str, tau: float, drain: md.Drainage) -> dict:
    """Expected fraction of road sample points (every ~30 m of public road centreline) where the
    6-inch tolerance is exceeded in a year, plus the share flooding at least every other year."""
    e = md.road_elevations_ft()
    zs = np.arange(np.floor(e.min() * 2) / 2, min(np.ceil(e.max()), 14.0) + 0.5, 0.5)
    pz = np.array([estimate(md.Model(grid_for(year, scenario, float(z), tau), drain), scrambles=4, log2_n=12)[0]
                   for z in zs])  # fmt: skip
    pe = np.interp(e, zs, pz)
    return {"road_points": len(e), "median_elev_ft": float(np.median(e)),
            "expected_fraction_flooding_per_year": float(pe.mean()),
            "fraction_flooding_at_least_every_2_yr": float((pe >= 0.5).mean()),
            "fraction_flooding_at_least_every_10_yr": float((pe >= 0.1).mean())}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2050)
    ap.add_argument("--scenario", default="intermediate", choices=list(md.SCENARIOS))
    ap.add_argument("--elevation", type=float, required=True, help="street low-point elevation, ft NAVD88")
    ap.add_argument("--tau", type=float, default=md.TAU_WP, help="tide-rain Kendall tau (ASSUMPTION; default 0.2)")
    ap.add_argument("--exposure", action="store_true", help="also estimate city road exposure (~1 min)")
    ap.add_argument("--json", action="store_true", help="print machine-readable output")
    args = ap.parse_args()
    if not -2.0 <= args.elevation <= 20.0:
        ap.error("elevation must be between -2 and 20 ft NAVD88")
    if not 0.0 <= args.tau < 1.0:
        ap.error("tau must be in [0, 1)")
    try:
        cfg = grid_for(args.year, args.scenario, args.elevation, args.tau)
    except ValueError as err:
        ap.error(str(err))

    drain = md.calibrate_drainage()
    m = md.Model(cfg, drain)
    a, hw = estimate(m)
    contrib = md.mechanisms(m)
    tau_lo = estimate(md.Model(replace(cfg, tau_wp=0.1), drain))[0]
    tau_hi = estimate(md.Model(replace(cfg, tau_wp=0.3), drain))[0]
    gev_lo, gev_hi = gev_interval(cfg, drain)
    out = {"year": args.year, "scenario": args.scenario, "elevation_ft_navd88": args.elevation,
           "p_flood": a, "ci95_halfwidth_estimator": hw, "return_period_yr": 1 / a if a > 0 else math.inf,
           "gev_bootstrap_90": [gev_lo, gev_hi], "tau_0.1_to_0.3": [tau_lo, tau_hi],
           "slr_ft_median": m.slr[0], "contributions": contrib}  # fmt: skip
    if args.exposure:
        out["exposure"] = exposure(args.year, args.scenario, args.tau, drain)
    if args.json:
        print(json.dumps(out, indent=1))
        return

    print(f"Key West street at {args.elevation:.2f} ft NAVD88, {args.year}, NOAA 2022 {args.scenario} SLR "
          f"(+{m.slr[0]:.2f} ft vs 2025)")  # fmt: skip
    print(
        f"  P(flood > 6 in, any given year) = {a:.4f} +- {hw:.1e} (95%, estimator)  ~ 1 in {1 / max(a, 1e-12):.1f} yr"
    )
    print(
        f"  model uncertainty: GEV fit 90% [{gev_lo:.4f}, {gev_hi:.4f}];  tide-rain tau 0.1..0.3 -> [{tau_lo:.4f}, {tau_hi:.4f}]"
    )
    print("  drivers: probability if this one driver is held at its median (the 3-h burst is instead")
    print("  locked to the 24-h depth's return period):")
    for name in m.random:
        v = contrib[f"{name}_frozen"]
        print(f"    {NAMES[name]:<35} {v:.4f}  ({v - a:+.4f})")
    print(f"    {'no rain (tide + groundwater only)':<35} {contrib['no_rain']:.4f}")
    if "exposure" in out:
        x = out["exposure"]
        print(f"  city exposure ({x['road_points']} road points, median {x['median_elev_ft']:.2f} ft): expected "
              f"{x['expected_fraction_flooding_per_year']:.1%} of road points flood per year; "
              f"{x['fraction_flooding_at_least_every_2_yr']:.1%} flood at least every 2 yr")  # fmt: skip
    print("  " + qae_line(a, hw))
    print("  Every model constant is sourced or flagged as an assumption: see README_multidriver.md.")


if __name__ == "__main__":
    main()
