"""Which Key West streets flood most often, and where does raising them buy the most?

Data: the 6,054 road points multidriver.py samples every ~30 m along public road centrelines
(OpenStreetMap ways, ODbL; elevations from USGS 3DEP 1 m lidar, ft NAVD88). Points are grouped
back into their OSM ways and the ways into named streets (unnamed ways keep their way id).

Probabilities: the five-driver model (multidriver.py) through conditional MC + Sobol, P(z) on a
0.25 ft elevation grid, interpolated to every point, for 2026 and 2030..2050 under the NOAA
Intermediate and High scenarios. A street "floods" in a year when its low point (10th percentile
of its samples, so one DEM pixel on a seawall does not decide it) floods by more than the 6-inch
tolerance, so the annual probability is also the expected number of flood years per year (the
model is annual-maximum: it does not count several events in one year). Streets are ranked by
expected flooded length per year in 2050 (Intermediate): the low-point probability saturates at 1.

Raising: "flood-years avoided per foot" = sum over 2026-2050 of P_y(z_low) - P_y(z_low + 1 ft)
under the Intermediate scenario, i.e. the whole street raised by one foot.

Cost: only figures read on the cited pages (README_hybrid.md): Monroe County's countywide road
adaptation plan, $9.6M per mile (Florida Specifier, 2023-03-04) and the Twin Lakes pilot, $21M
for 4,633 ft = $23.9M per mile all-in (Keys Weekly, 2024-08-22). Neither states a raise height,
so "$ per flood-year avoided" pairs them with the 1-ft raise above: an ASSUMPTION.

Sensitivity: the five-driver drainage calibration disagrees with the 2-driver drainage.py at
SMP node N3210 (a = 0.97 vs 0.640 there today). We rerun 2050 Intermediate with the five-driver
drainage capacity scaled up until N3210 matches 0.640, and report how much the ranking moves.

Run: `uv run python road_priority.py` (~8 min). Writes road_priority.csv, road_priority.json and
web/assets/data/road_priority.json.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

import floodline_cli as cli
import multidriver as md

ROOT = Path(__file__).resolve().parent
YEARS = [2026, 2030, 2035, 2040, 2045, 2050]
SCENARIOS = ("intermediate", "high")
Z_STEP = 0.25
TOP = 25
M_PER_MILE = 1609.344
COSTS: dict[str, dict[str, Any]] = {
    "monroe_plan_9.6M_per_mile": {"usd_per_mile": 9.6e6, "source": "Florida Specifier, 2023-03-04, Monroe County "
        "roads plan: '$1.6 billion, at a cost of $9.6 million/mile'",
        "url": "https://floridaspecifier.com/issues/v44n6/monroe-county-caps-roads-plan-with-1-6-billion-in-projects/"},
    "twin_lakes_23.9M_per_mile": {"usd_per_mile": 21e6 / (4633 / 5280), "source": "Keys Weekly, 2024-08-22: "
        "'$21 million resilient Twin Lakes roads pilot project' ... '4,633 linear feet of road' (all-in, incl. drainage)",
        "url": "https://keysweekly.com/?p=84561"},
}  # fmt: skip
N3210 = {"z_ft": 1.12, "year": 2025, "a_two_driver": 0.640}  # README_multidriver.md cross-check


def street_points() -> list[dict]:
    """One record per road point: lon, lat, elevation, OSM way id, street name, highway class.
    Re-runs multidriver's resampling way by way so points keep their way."""
    roads = json.loads((md.DATA_DIR / "keywest_osm_roads.json").read_text())
    elev = json.loads((md.DATA_DIR / "keywest_road_elev_3dep.json").read_text())
    pts = np.array(elev["lonlat"])
    z_m = elev["elev_m_navd88"]
    out, i = [], 0
    for el in roads["elements"]:
        if len(el.get("geometry", [])) < 2:
            continue
        n = len(md._resample_roads({"elements": [el]}))
        tags = el.get("tags", {})
        for k in range(i, i + n):
            v = z_m[k]
            if v is None or not np.isfinite(v) or v * md.FT_PER_M <= -3.0:  # md.road_elevations_ft's rule
                continue
            out.append({"lon": pts[k, 0], "lat": pts[k, 1], "z_ft": v * md.FT_PER_M, "way": el["id"],
                        "name": tags.get("name") or f"unnamed {tags.get('highway', 'road')} (OSM way {el['id']})",
                        "highway": tags.get("highway", "")})  # fmt: skip
        i += n
    if i != len(pts):
        raise RuntimeError(f"resampled {i} points but the elevation cache has {len(pts)}: caches out of sync")
    return out


def way_lengths_m() -> dict[int, float]:
    roads = json.loads((md.DATA_DIR / "keywest_osm_roads.json").read_text())
    scale = np.array([111320 * np.cos(np.radians(24.56)), 110570])
    out = {}
    for el in roads["elements"]:
        g = np.array([[p["lon"], p["lat"]] for p in el.get("geometry", [])])
        if len(g) >= 2:
            out[el["id"]] = float(np.linalg.norm(np.diff(g, axis=0) * scale, axis=1).sum())
    return out


def p_curve(year: int, scenario: str, zs: np.ndarray, drain: md.Drainage) -> np.ndarray:
    """P(flood) at each grid elevation, CMC + Sobol (4 scrambles x 2**12, half-width ~1e-3)."""
    return np.array([cli.estimate(md.Model(cli.grid_for(year, scenario, float(z), md.TAU_WP), drain),
                                  scrambles=4, log2_n=12)[0] for z in zs])  # fmt: skip


def n3210_matched_drainage(drain: md.Drainage) -> tuple[md.Drainage, float, float]:
    """Scale both drainage constants by one factor until N3210 today gives the 2-driver a = 0.640."""
    cfg = md.Config(year=int(N3210["year"]), z_ft=N3210["z_ft"])

    def a_for(f: float) -> float:
        return md.Model(cfg, md.Drainage(drain.k_out * f, drain.k_well * f, drain.anchor)).exact()

    lo, hi = 1.0, 64.0
    a_base = a_for(1.0)
    if a_for(hi) > N3210["a_two_driver"]:
        raise RuntimeError("even 64x drainage cannot bring N3210 down to the 2-driver value")
    for _ in range(25):
        mid = math.sqrt(lo * hi)
        lo, hi = (mid, hi) if a_for(mid) > N3210["a_two_driver"] else (lo, mid)
    f = math.sqrt(lo * hi)
    return md.Drainage(drain.k_out * f, drain.k_well * f, drain.anchor), f, a_base


def aggregate(points: list[dict], lengths: dict[int, float], curves: dict, zs: np.ndarray) -> list[dict]:
    by: dict[str, list[dict]] = {}
    for p in points:
        by.setdefault(p["name"], []).append(p)

    def interp(key: tuple[int, str], z: np.ndarray | float) -> np.ndarray:
        return np.interp(z, zs, curves[key])

    rows = []
    for name, ps in by.items():
        z = np.array([p["z_ft"] for p in ps])
        # Low point = 10th percentile of the ~30 m samples, so one DEM pixel on a seawall or bridge edge
        # does not decide the street (Roosevelt Blvd has samples at -1.6 ft).
        low = float(np.percentile(z, 10))
        k = int(np.abs(z - low).argmin())
        yrs = np.arange(2026, 2051)
        p_low = np.interp(yrs, YEARS, [float(interp((y, "intermediate"), low)) for y in YEARS])
        p_raised = np.interp(yrs, YEARS, [float(interp((y, "intermediate"), low + 1.0)) for y in YEARS])
        miles = sum(lengths[w] for w in {p["way"] for p in ps}) / M_PER_MILE
        avoided = float((p_low - p_raised).sum())
        row = {"street": name, "highway": ps[0]["highway"], "osm_ways": len({p["way"] for p in ps}),
               "length_mi": round(miles, 3), "points": len(ps), "low_point_ft_navd88": round(low, 2), "min_ft_navd88": round(float(z.min()), 2),
               "median_ft_navd88": round(float(np.median(z)), 2), "low_point_lonlat": [ps[k]["lon"], ps[k]["lat"]],
               "p_2026": round(float(interp((2026, "intermediate"), low)), 4),
               "flooded_mi_per_yr_2026": round(float(interp((2026, "intermediate"), z).mean()) * miles, 4)}  # fmt: skip
        for s in SCENARIOS:
            row[f"p_2050_{s}"] = round(float(interp((2050, s), low)), 4)
            row[f"flooded_mi_per_yr_2050_{s}"] = round(float(interp((2050, s), z).mean()) * miles, 4)
            row[f"share_flooding_per_yr_2050_{s}"] = round(float(interp((2050, s), z).mean()), 4)
        row["flood_years_avoided_2026_2050_per_ft"] = round(avoided, 3)
        row["flood_years_avoided_per_ft_per_mile"] = round(avoided / miles, 3) if miles > 0 else None
        for key, c in COSTS.items():
            row[f"usd_per_flood_year_avoided_{key}"] = (
                round(c["usd_per_mile"] * miles / avoided) if avoided > 1e-6 else None
            )
        rows.append(row)
    # Rank by expected flooded road length: the low-point probability saturates at 1 for many streets.
    rows.sort(key=lambda r: (-r["flooded_mi_per_yr_2050_intermediate"], -r["p_2050_intermediate"]))
    for i, r in enumerate(rows, 1):
        r["rank_risk_2050_intermediate"] = i
    for i, r in enumerate(sorted(rows, key=lambda r: -(r["flood_years_avoided_per_ft_per_mile"] or 0)), 1):
        r["rank_value_per_mile"] = i
    return rows


def main() -> None:
    drain = md.calibrate_drainage()
    points = street_points()
    lengths = way_lengths_m()
    z_all = np.array([p["z_ft"] for p in points])
    zs = np.arange(math.floor(z_all.min() * 4) / 4, min(math.ceil(z_all.max()), 14.0) + 1.0 + Z_STEP, Z_STEP)
    curves = {(y, s): p_curve(y, s, zs, drain) for s in SCENARIOS for y in YEARS}
    rows = aggregate(points, lengths, curves, zs)

    alt_drain, factor, a_base = n3210_matched_drainage(drain)
    alt = dict(curves)
    alt[(2050, "intermediate")] = p_curve(2050, "intermediate", zs, alt_drain)
    alt_rows = {r["street"]: r for r in aggregate(points, lengths, alt, zs)}
    top = [r["street"] for r in rows[:TOP]]
    alt_top = sorted(alt_rows.values(), key=lambda r: r["rank_risk_2050_intermediate"])[:TOP]
    by_len = [r["flooded_mi_per_yr_2050_intermediate"] for r in rows]
    by_len_alt = [alt_rows[r["street"]]["flooded_mi_per_yr_2050_intermediate"] for r in rows]
    sens = {"n3210_a_five_driver_today": a_base, "n3210_a_two_driver_today": N3210["a_two_driver"],
            "drainage_scale_to_match": factor,
            "top25_overlap_flooded_mi_rank": len(set(top) & {r["street"] for r in alt_top}),
            "spearman_flooded_mi_2050_int": float(stats.spearmanr(by_len, by_len_alt).statistic),
            "city_expected_flooded_share_2050_int": float(np.mean(np.interp(z_all, zs, curves[(2050, "intermediate")]))),
            "city_expected_flooded_share_2050_int_n3210_matched": float(np.mean(np.interp(z_all, zs, alt[(2050, "intermediate")]))),
            "top10_alt_rank": {s: alt_rows[s]["rank_risk_2050_intermediate"] for s in top[:10]},
            "top10_alt_flooded_mi_2050_int": {s: alt_rows[s]["flooded_mi_per_yr_2050_intermediate"] for s in top[:10]}}  # fmt: skip

    meta = {"model": "five-driver multidriver.py (LOS-anchored drainage), CMC + Sobol, 4 x 2**12 points per elevation",
            "event": "a road point exceeds the SMP 6-inch tolerance in a year (annual maximum); p_* columns are the "
                     "street's low point (10th percentile of its samples), flooded_mi_* the expected flooded length; ranked by flooded_mi 2050 intermediate",
            "years": YEARS, "scenarios": list(SCENARIOS), "points": len(points), "streets": len(rows),
            "costs": COSTS, "sensitivity_drainage": sens,
            "caveat": "Probabilities rest on flagged, unmeasured assumptions (README_multidriver.md); a ranking tool, "
                      "not a forecast. Centreline lidar sits above gutters, so low points are understated."}  # fmt: skip
    (ROOT / "road_priority.json").write_text(json.dumps({"meta": meta, "streets": rows}, indent=1))
    web = ROOT / "web" / "assets" / "data" / "road_priority.json"
    web.write_text(json.dumps({"meta": meta, "streets": rows[:100]}, separators=(",", ":")))
    cols = [k for k in rows[0] if k != "low_point_lonlat"]
    with open(ROOT / "road_priority.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
    print(json.dumps(sens, indent=1))
    hdr = f"{'#':>2} {'street':28s} {'mi':>5} {'low ft':>6} {'P2026':>6} {'P2050i':>6} {'P2050h':>6} {'mi/yr':>6} {'FYa/ft':>6} {'$/FYa (9.6M/mi)':>16}"
    print(hdr)
    for r in rows[:10]:
        usd = r["usd_per_flood_year_avoided_monroe_plan_9.6M_per_mile"]
        print(f"{r['rank_risk_2050_intermediate']:>2} {r['street'][:28]:28s} {r['length_mi']:5.2f} {r['low_point_ft_navd88']:6.2f} "
              f"{r['p_2026']:6.3f} {r['p_2050_intermediate']:6.3f} {r['p_2050_high']:6.3f} {r['flooded_mi_per_yr_2050_intermediate']:6.3f} "
              f"{r['flood_years_avoided_2026_2050_per_ft']:6.2f} {'-' if usd is None else f'{usd:,.0f}':>16}")  # fmt: skip


if __name__ == "__main__":
    main()
