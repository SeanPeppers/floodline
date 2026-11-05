"""Build the compact data files behind the site's street layer and "Tonight in Key West" panel.

  uv run python web_data.py            # streets + flood-rule constants (seconds)
  uv run python web_data.py --planning # also the 2050 per-scenario street curves (minutes)

Writes into web/assets/data/:
  streets.json   OSM road centrelines (ODbL) split into one ~30 m piece per USGS 3DEP sample point,
                 the same 6,054 points multidriver.road_elevations_ft() and the CLI's --exposure use.
  floodrule.json the five-driver street flood rule's constants (multidriver.py), the calibrated
                 drainage capacity, and (with --planning) P(flood in a year) vs street elevation for
                 every NOAA 2022 scenario in 2050, from floodline_cli.exposure()'s own estimator.
No data is fetched: everything is read from the caches in data/.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import floodline_cli as cli
import multidriver as md

OUT = Path(__file__).resolve().parent / "web" / "assets" / "data"
# Origin and grid of the encoded coordinates: the Key West scene's raster bbox (web/js/scene.js).
ORIGIN_LON, ORIGIN_LAT = -81.82, 24.535
Q = 1e5  # 1e-5 deg, ~1 m
PLANNING_YEAR = 2050


def street_pieces() -> dict:
    """One record per OSM way: delta-encoded vertices [way start, samples..., way end] and the 3DEP
    elevation (0.01 ft NAVD88) of each sample, null where 3DEP has no valid ground value."""
    roads = json.loads((md.DATA_DIR / "keywest_osm_roads.json").read_text())
    elev = json.loads((md.DATA_DIR / "keywest_road_elev_3dep.json").read_text())
    lonlat = np.array(elev["lonlat"])
    vals = elev["elev_m_navd88"]
    if not np.array_equal(md._resample_roads(roads), lonlat):
        raise RuntimeError("3DEP cache doesn't match the resampled OSM roads; rerun multidriver.road_elevations_ft()")

    names: dict[str, int] = {}
    ways, k, n_valid = [], 0, 0
    for el in roads["elements"]:
        g = el.get("geometry", [])
        if len(g) < 2:
            continue
        n = len(md._resample_roads({"elements": [el]}))
        if n == 0:
            continue
        verts = [[g[0]["lon"], g[0]["lat"]], *lonlat[k : k + n].tolist(), [g[-1]["lon"], g[-1]["lat"]]]
        e: list[int | None] = []
        for v in vals[k : k + n]:
            ft = None if v is None else v * md.FT_PER_M
            ok = ft is not None and np.isfinite(ft) and ft > -3.0  # same filter as road_elevations_ft()
            e.append(round(ft * 100) if ok and ft is not None else None)
            n_valid += ok
        k += n
        q = np.round((np.array(verts) - [ORIGIN_LON, ORIGIN_LAT]) * Q).astype(int)
        d = np.vstack([q[:1], np.diff(q, axis=0)]).ravel().tolist()
        name = el.get("tags", {}).get("name", "")
        ways.append([names.setdefault(name, len(names)), d, e])
    if k != len(lonlat):
        raise RuntimeError(f"mapped {k} of {len(lonlat)} 3DEP samples onto OSM ways")
    if n_valid != len(md.road_elevations_ft()):
        raise RuntimeError("valid-point count differs from multidriver.road_elevations_ft()")
    return {
        "about": "Key West public road centrelines, one ~30 m piece per USGS 3DEP sample (multidriver.py)",
        "roads": "OpenStreetMap contributors, ODbL 1.0, via Overpass, " + roads["osm3s"]["timestamp_osm_base"],
        "elevation": "USGS 3DEP 1 m bare-earth DEM, getSamples, NAVD88 (public domain)",
        "origin_lonlat": [ORIGIN_LON, ORIGIN_LAT],
        "q_per_deg": Q,
        "elev_unit": "0.01 ft NAVD88",
        "encoding": "ways[i] = [name index, delta-encoded int (lon, lat) of [start, samples..., end], sample elevations]",
        "n_points": n_valid,
        # The scene's water level is m NAVD88 = this + m above MHHW (NOAA datums, 8724580).
        "mhhw_navd_m": round(md.mhhw_navd_ft() / md.FT_PER_M, 4),
        "names": list(names),
        "ways": ways,
    }


def rule_constants() -> dict:
    drain = md.calibrate_drainage()
    return {
        "source": "multidriver.py five-driver street flood rule; constants sourced to the City of Key West "
        "2024 Stormwater Master Plan (SMP) or flagged ASSUMPTION there",
        "TOL_FT": md.TOL_FT,
        "CN": md.CN,
        "SOIL_DEPTH_FT": md.SOIL_DEPTH_FT,
        "WELL_START_FT": md.WELL_START_FT,
        "GW_OFFSET_FT": list(md.GW_OFFSET_FT),
        "BURST_HOURS": md.BURST_HOURS,
        "CATCH_RATIO": md.CATCH_RATIO,
        "MHHW_NAVD_FT": md.mhhw_navd_ft(),
        "k_out": drain.k_out,
        "k_well": drain.k_well,
        "drainage_anchor": drain.anchor,
    }


def planning(drain: md.Drainage) -> dict:
    """P(flood in a year) vs street low-point elevation, per scenario: exactly the curve
    floodline_cli.exposure() interpolates road points on (same grid, estimator and budget)."""
    e = md.road_elevations_ft()
    zs = np.arange(np.floor(e.min() * 2) / 2, min(np.ceil(e.max()), 14.0) + 0.5, 0.5)
    out = {}
    for sc in md.SCENARIOS:
        pz = [cli.estimate(md.Model(cli.grid_for(PLANNING_YEAR, sc, float(z), md.TAU_WP), drain), scrambles=4,
                           log2_n=12)[0] for z in zs]  # fmt: skip
        pe = np.interp(e, zs, pz)
        out[sc] = {"p": [round(p, 5) for p in pz], "slr_ft_median": md.slr_offset_ft(PLANNING_YEAR, sc)[0],
                   "expected_fraction_flooding_per_year": float(pe.mean())}  # fmt: skip
        print(f"  {sc}: expected {pe.mean():.1%} of road points flood per year")
    return {"year": PLANNING_YEAR, "tau_wp": md.TAU_WP, "z_ft": zs.tolist(), "scenarios": out,
            "method": "floodline_cli.exposure(): conditional MC on scrambled Sobol (4 x 2^12), linear "
                      "interpolation in elevation"}  # fmt: skip


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--planning", action="store_true", help="also recompute the 2050 scenario curves (minutes)")
    args = ap.parse_args()
    streets = street_pieces()
    (OUT / "streets.json").write_text(json.dumps(streets, separators=(",", ":")))
    rule = rule_constants()
    path = OUT / "floodrule.json"
    if args.planning:
        rule["planning"] = planning(md.calibrate_drainage())
    elif path.exists() and "planning" in (old := json.loads(path.read_text())):
        rule["planning"] = old["planning"]
    path.write_text(json.dumps(rule, indent=1))

    # Share of road points under a still-water (bathtub) level at each story chapter.
    e = md.road_elevations_ft()
    thr = json.loads((Path(__file__).resolve().parent / "results.json").read_text())["problem"]["tide"]
    levels = {**thr["thresholds_m_above_mhhw"], "mhhw": 0.0, "irma_2.7ft": 2.7 / md.FT_PER_M}
    mhhw = md.mhhw_navd_ft()
    for name, m in sorted(levels.items(), key=lambda kv: kv[1]):
        lvl = mhhw + m * md.FT_PER_M
        print(f"  {name:<14} {lvl:5.2f} ft NAVD88: {(e <= lvl).mean():6.1%} of {len(e)} road points under water")


if __name__ == "__main__":
    main()
