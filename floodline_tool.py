"""Floodline with a swappable estimator engine (hybrid.estimate).

  uv run python floodline_tool.py --year 2050 --scenario intermediate --elevation 3.0                # classical
  uv run python floodline_tool.py --elevation 3.0 --backend quantum-resource --eps 1e-4
  uv run python floodline_tool.py --elevation 2.0 --backend quantum-sim       # reduced grid, ~1 min

  classical         conditional MC + Sobol on the benchmark grid: the production answer.
  quantum-sim       the hybrid circuit (classical conditioning + quantum residual mean) sampled
                    on Aer at a 20-qubit reduced grid; prints the exact answer on that grid too.
  quantum-resource  what the hybrid would cost on the benchmark grid: queries, logical qubits,
                    Toffoli/CX, the 2-qubit error the deepest circuit needs, fault-tolerant hours.
floodline_cli.py keeps the full report (driver contributions, model uncertainty, exposure).
"""

from __future__ import annotations

import argparse
import json

import floodline_cli as cli
import hybrid as hy
import multidriver as md


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2050)
    ap.add_argument("--scenario", default="intermediate", choices=list(md.SCENARIOS))
    ap.add_argument("--elevation", type=float, required=True, help="street low-point elevation, ft NAVD88")
    ap.add_argument("--tau", type=float, default=md.TAU_WP, help="tide-rain Kendall tau (ASSUMPTION; default 0.2)")
    ap.add_argument("--backend", default="classical", choices=list(hy.BACKENDS))
    ap.add_argument("--eps", type=float, default=1e-3, help="target absolute error (95%% half-width for classical)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not -2.0 <= args.elevation <= 20.0:
        ap.error("elevation must be between -2 and 20 ft NAVD88")
    if not 0.0 <= args.tau < 1.0:
        ap.error("tau must be in [0, 1)")
    if not 1e-6 <= args.eps < 0.5:
        ap.error("eps must be in [1e-6, 0.5)")
    try:
        cfg = cli.grid_for(args.year, args.scenario, args.elevation, args.tau)
    except ValueError as err:
        ap.error(str(err))

    out = hy.estimate(cfg, args.eps, args.backend)
    m = out.pop("model")
    out.update(year=args.year, scenario=args.scenario, elevation_ft_navd88=args.elevation)
    if args.json:
        print(json.dumps(out, indent=1, default=str))
        return
    print(f"Key West street at {args.elevation:.2f} ft NAVD88, {args.year}, NOAA 2022 {args.scenario} "
          f"(+{m.slr[0]:.2f} ft SLR vs 2025), backend {args.backend}")  # fmt: skip
    if args.backend == "classical":
        print(f"  P(flood > 6 in, any given year) = {out['p_flood']:.4f} +- {out['ci95_halfwidth']:.1e} (95%), "
              f"{out['samples']:,} conditional samples, {out['seconds']:.1f} s")  # fmt: skip
    elif args.backend == "quantum-sim":
        print(f"  reduced grid ({out['qubits']} qubits): hybrid estimate {out['p_flood']:.4f}, exact on the same grid "
              f"{out['exact_same_grid']:.4f}, |error| {out['abs_error']:.1e} with {out['oracle_queries']:,} oracle "
              f"queries, {out['seconds']:.0f} s")  # fmt: skip
        print(
            "  The reduced grid is a different (coarser) model than the classical answer; it shows the circuit works."
        )
    else:
        print(f"  to reach +-{args.eps:g} (RMSE) with the hybrid: {out['oracle_queries']:,.0f} oracle queries "
              f"(plain QAE up to {out['plain_qae_queries_upper']:,.0f}); CV grid {out['cv_coarse_cells']:,} cells, "
              f"{out['layers']} residual layer(s) per sign, {out['classical_reads']:,} classical table reads")  # fmt: skip
        print(f"  circuit: {out['qubits']} logical qubits, one A_h = {out['a_toffoli']:,} Toffoli / "
              f"{out['a_cx_equiv']:,} CX-equivalent; deepest Q^{out['deepest_m']} A_h = {out['deepest_cx_equiv']:,.0f} CX")  # fmt: skip
        print(f"  needs 2-qubit error <= {out['two_qubit_error_for_50pct_success']:.1e} for 50% success unencoded; "
              f"fault-tolerant at 170 us/Toffoli: {out['ft_hours_at_170us_per_toffoli']:,.1f} h "
              f"({out['total_toffoli']:,.0f} Toffoli). Classical: milliseconds.")  # fmt: skip


if __name__ == "__main__":
    main()
