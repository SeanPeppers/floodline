"""Multi-driver Key West compound flood model: up to five correlated random drivers and a
physically nonlinear drainage rule, discretized onto integer grids so the SAME model can be
sampled classically and loaded into a quantum circuit (multidriver_circuit.py).

Drivers (all stages in ft NAVD88, rain in inches):
  W    annual-max still water level (tide + surge), GEV fitted to 110 usable years of NOAA
       gauge 8724580, detrended to 2025 mean sea level (flood.py, unchanged).
  P24  24-h rain depth, Gumbel fitted to NOAA Atlas 14 annual-maximum-series depths (rainfall.py).
  P3   peak 3-h burst inside that storm, Gumbel fitted to Atlas 14 3-h AMS depths (same PFDS query).
  S    sea-level-rise offset from 2025 to the target year, NOAA 2022 (Sweet et al.) scenario
       projections for station 8724580 from the CO-OPS API, split-normal through (low, central, high).
  O    groundwater offset above the normal high tide, Uniform(0.5, 1.5) ft (City of Key West 2024
       Stormwater Master Plan, SMP, sec 2.1.2: "approximately 0.5 foot to 1.5 feet above the tide").

Flood rule for a street whose low point is at elevation z (evaluated at the critical stage
z + TOL, the 6-inch road tolerance from SMP sec 3.1):
  C = W + S                                  coastal stage (pipes back up to it; check valves assumed)
  G = MHHW + S + O                           groundwater stage
  soil storage  S_r = (1000/CN - 10) * clip((z - G) / SOIL_DEPTH, 0, 1)        SCS-CN, CN from SMP
  burst runoff  R = Q(Pa + P3) - Q(Pa),  Pa = (P24 - P3)/2,  Q = SCS-CN runoff (nonlinear in rain)
  drainage over the 3-h burst: outfalls ~ sqrt(max(z + TOL - C, 0)) (head to the sea), gravity
       wells ~ max(z + TOL - G - 1.6, 0) (SMP: wells take no water until the ponded stage is 1.6 ft
       above groundwater, linear above it, curve shifts with groundwater)
  ponding p = CATCH_RATIO * max(R - D, 0) / 12   (ft)
  flood  <=>  max(C, G, z) - z + p >= TOL
Every constant below is either sourced or marked ASSUMPTION, NOT MEASURED, with its reasoning.

Discretization (what both the classical samplers and the circuit see):
  W, S, O sit on one shared grid step DELTA (ft), so C = w + s and G = s + o are plain integer
  additions (one ripple-carry adder each in the circuit). P24 and P3 sit on their own grids.
  The rule is folded into two integer tables, R_int[p24, p3, g >> g_drop] and T_int[c, g], and
  flood <=> R_int >= T_int. Dependence: Gaussian copula, discretized the Rosenblatt way: P24 is
  drawn conditional on the top `regime_bits` bits of W, and P3 conditional on the top bits of P24
  (the same construction as copula.py, with exact copula block averages instead of midpoints).
  Drivers not in Config.drivers are frozen at their median (P3 frozen = comonotone with P24).
"""

from __future__ import annotations

import ast
import json
import re
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import requests
from scipy import stats

import flood
import rainfall

DATA_DIR = flood.DATA_DIR
FT_PER_M = 3.28084
UA = {"User-Agent": "floodline-fgcu-hackathon/0.1 (research prototype)"}

# --- Sourced constants (SMP = City of Key West 2024 Stormwater Master Plan Update) ---
TOL_FT = 0.5  # SMP sec 3.1: "up to 6 inches of flooding above the low area of the roadway ... tolerated"
CN = 91  # SMP Table 2-6: high-density residential, 60% impervious (range in table: CN 88-95)
SOIL_DEPTH_FT = 4.0  # SMP: soil layer "3 to 5 feet deep" over oolitic limestone; midpoint
WELL_START_FT = 1.6  # SMP: gravity-well flow begins ~1.6 ft above groundwater (1.4 ft + 0.2 ft friction)
GW_OFFSET_FT = (0.5, 1.5)  # SMP sec 2.1.2: groundwater 0.5-1.5 ft above the tide levels
BURST_HOURS = 3.0  # duration of the Atlas 14 short-duration depth used for P3
ANCHOR_RP = 5  # SMP LOS: "Residential streets should be passable during the 5-year storm"
SLR_REF_YEAR = flood.REF_YEAR  # W is detrended to 2025 sea level, so S is the rise after 2025

# --- ASSUMPTION, NOT MEASURED ---
# Tide-rain dependence. No Key West Kendall tau is published as a number: Wahl et al. 2015 show it
# only in a figure (axis 0-0.4); Jane et al. 2020 report tau < 0.3 for South Florida. Prior 0.1-0.3,
# centre 0.2; experiment_multi.py and the CLI report sensitivity at 0.1 and 0.3.
TAU_WP = 0.2
# 24-h vs 3-h rain inside the same storm: unsourced. The 3-h burst is nested inside the 24-h total,
# so dependence is strong; 0.8 is a judgement call. Configs without P3 use the comonotone limit (1.0).
RHO_P = 0.8
# Contributing catchment area / ponded low-area ratio: runoff from the block collects at the low
# spot. No street-level number found; 3 is a judgement call.
CATCH_RATIO = 3.0
# Drainage calibration. The SMP gives a level-of-service target, not measured street performance.
# We assume the system just meets the 5-year LOS at a street of elevation ANCHOR_Z_FT (Bahama
# Village infrastructure is "at an elevation of 4 feet NAVD 88 or less"; city mean is 4.7 ft) with
# today's tide at MHHW and groundwater at the mid offset (1.0 ft): ponding exactly TOL there. Half
# the capacity comes from outfalls and half from wells at the anchor (split unknown).
ANCHOR_Z_FT = 4.0
OUTFALL_SHARE = 0.5
# Annual maxima of water level and of rain are treated as concurrent (the same storm), coupled by
# the copula. This is the standard bivariate-annual-maxima simplification; it overstates
# co-occurrence when the true pairing is weaker (Wahl's own pairing is +-1 day).
R_FULL_IN = 10.0  # runoff scale covered by the n_k-bit integer grid (larger burst runoff saturates)

DRIVERS = ("W", "P24", "P3", "S", "O")
SCENARIOS = {"low": "Low", "intermediate-low": "Intermediate-Low", "intermediate": "Intermediate",
             "intermediate-high": "Intermediate-High", "high": "High"}  # fmt: skip
Z83 = float(stats.norm.ppf(0.83))


# ----------------------------------------------------------------------------- data


def _cached(path: Path, fetch) -> str:  # type: ignore[no-untyped-def]
    if not path.exists():
        DATA_DIR.mkdir(exist_ok=True)
        path.write_text(fetch())
    return path.read_text()


def mhhw_navd_ft() -> float:
    """MHHW above NAVD88 at 8724580 from NOAA's own datums file (both in station-datum metres)."""
    flood.load_annual_maxima()  # makes sure the datums cache exists
    d = {x["name"]: x["value"] for x in json.loads((DATA_DIR / "keywest_datums.json").read_text())["datums"]}
    return (d["MHHW"] - d["NAVD88"]) * FT_PER_M


def pfds_ams() -> dict[str, list[float]]:
    """NOAA Atlas 14 AMS depths (in) for every duration at rainfall.py's point, one PFDS query."""

    def fetch() -> str:
        params: dict[str, str | float] = {"lat": rainfall.LAT, "lon": rainfall.LON, "type": "pf", "data": "depth",
                                          "units": "english", "series": "ams"}  # fmt: skip
        r = requests.get(rainfall.PFDS_URL, params=params, timeout=60, headers=UA)
        r.raise_for_status()
        m = re.search(r"quantiles\s*=\s*(\[\[.*?\]\])", r.text)
        if not m:
            raise RuntimeError("NOAA PFDS response didn't contain a quantiles table")
        rows = ast.literal_eval(m.group(1))
        return json.dumps({d: [float(v) for v in row] for d, row in zip(rainfall.DURATIONS, rows)})

    return json.loads(_cached(DATA_DIR / "keywest_pfds_ams_all.json", fetch))


def slr_projections() -> list[dict]:
    """NOAA 2022 Sea Level Rise Technical Report projections for 8724580 (CO-OPS API, cm,
    zero at 2005). The low/high columns are the report's range; the file doesn't say which
    percentiles, we read them as the 17th-83rd 'likely' range (ASSUMPTION)."""

    def fetch() -> str:
        url = "https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi/product/slr_projections.json"
        r = requests.get(url, params={"station": flood.STATION}, timeout=60, headers=UA)
        r.raise_for_status()
        return r.text

    return json.loads(_cached(DATA_DIR / "keywest_slr_2022.json", fetch))["SlrProjections"]


def slr_offset_ft(year: int, scenario: str) -> tuple[float, float, float]:
    """(median, sigma_below, sigma_above) of sea-level rise from 2025 to `year`, ft, split normal."""
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {list(SCENARIOS)}")
    rows = sorted((r for r in slr_projections() if r["scenario"] == SCENARIOS[scenario]),
                  key=lambda r: r["projectionYear"])  # fmt: skip
    yrs = np.array([r["projectionYear"] for r in rows], dtype=float)
    if not SLR_REF_YEAR <= year <= yrs[-1]:
        raise ValueError(f"year must be in [{SLR_REF_YEAR}, {int(yrs[-1])}]")
    cen, lo, hi = (np.array([r[k] for r in rows], dtype=float) for k in ("projectionRsl", "projectionCiLow", "projectionCiHigh"))  # fmt: skip
    c = np.interp(year, yrs, cen)
    med = (c - np.interp(SLR_REF_YEAR, yrs, cen)) / 100 * FT_PER_M
    s_lo = max(c - np.interp(year, yrs, lo), 0.0) / 100 * FT_PER_M / Z83
    s_hi = max(np.interp(year, yrs, hi) - c, 0.0) / 100 * FT_PER_M / Z83
    return float(med), float(s_lo), float(s_hi)


def split_normal_cdf(x: np.ndarray, med: float, s_lo: float, s_hi: float) -> np.ndarray:
    """CDF of the two-piece normal with mode `med`; continuous at med, 0.5 mass below only when
    s_lo == s_hi (the generic two-piece form, Wallis 2014)."""
    s_lo, s_hi = max(s_lo, 1e-9), max(s_hi, 1e-9)
    w = s_lo / (s_lo + s_hi)
    below = 2 * w * stats.norm.cdf((x - med) / s_lo)
    above = w + (1 - w) * (2 * stats.norm.cdf((x - med) / s_hi) - 1)
    return np.where(x <= med, below, above)


ROAD_BBOX = (24.540, -81.812, 24.585, -81.734)  # Key West island incl. New Town; excludes Stock Island
ROAD_TYPES = "primary|secondary|tertiary|residential|unclassified|living_street"
ROAD_STEP_M = 30.0


def road_elevations_ft() -> np.ndarray:
    """Elevation (ft NAVD88) at points every ~30 m along Key West public road centrelines.
    Roads: OpenStreetMap via Overpass (ODbL). Elevations: USGS 3DEP bare-earth DEM (1 m lidar
    here) via the public ImageServer getSamples endpoint, metres NAVD88. Two small cached
    datasets, one Overpass call and ~20 batched 3DEP calls on first use."""
    roads = json.loads(_cached(DATA_DIR / "keywest_osm_roads.json", _fetch_osm_roads))
    pts = _resample_roads(roads)

    def fetch_elev() -> str:
        url = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/getSamples"
        out: list[float | None] = []
        for i in range(0, len(pts), 400):
            geom = {"points": pts[i : i + 400].tolist(), "spatialReference": {"wkid": 4326}}
            data = {"geometry": json.dumps(geom), "geometryType": "esriGeometryMultipoint",
                    "returnFirstValueOnly": "true", "f": "json"}  # fmt: skip
            r = requests.post(url, data=data, timeout=120, headers=UA)
            r.raise_for_status()
            samples = sorted(r.json()["samples"], key=lambda s: s["locationId"])
            if len(samples) != len(geom["points"]):
                raise RuntimeError("3DEP getSamples returned a different number of points than sent")
            out += [float(s["value"]) if s["value"] not in ("NoData", None, "") else None for s in samples]
            time.sleep(1.0)  # be polite to a free public service
        return json.dumps({"lonlat": pts.tolist(), "elev_m_navd88": out})

    d = json.loads(_cached(DATA_DIR / "keywest_road_elev_3dep.json", fetch_elev))
    e = np.array([np.nan if v is None else v for v in d["elev_m_navd88"]], dtype=float) * FT_PER_M
    # Points over water (bridge decks, DEM voids) come back NoData or below -1 m; drop them.
    return e[np.isfinite(e) & (e > -3.0)]


def _fetch_osm_roads() -> str:
    s, w, n, e = ROAD_BBOX
    q = f'[out:json][timeout:90];way["highway"~"^({ROAD_TYPES})$"]({s},{w},{n},{e});out geom;'
    r = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, timeout=120, headers=UA)
    r.raise_for_status()
    return r.text


def _resample_roads(roads: dict) -> np.ndarray:
    pts = []
    for el in roads["elements"]:
        g = np.array([[p["lon"], p["lat"]] for p in el.get("geometry", [])])
        if len(g) < 2:
            continue
        scale = np.array([111320 * np.cos(np.radians(24.56)), 110570])  # m per degree
        seg = np.linalg.norm(np.diff(g, axis=0) * scale, axis=1)
        dist = np.concatenate([[0], np.cumsum(seg)])
        at = np.arange(ROAD_STEP_M / 2, dist[-1], ROAD_STEP_M)
        pts.append(np.column_stack([np.interp(at, dist, g[:, 0]), np.interp(at, dist, g[:, 1])]))
    return np.round(np.concatenate(pts), 6)


# ----------------------------------------------------------------------------- physics


def scs_runoff(p: np.ndarray, s_r: np.ndarray) -> np.ndarray:
    """SCS curve-number runoff depth (in) for rain p (in) and potential retention s_r (in)."""
    ia = 0.2 * s_r
    return np.where(p > ia, (p - ia) ** 2 / np.maximum(p - ia + s_r, 1e-12), 0.0)


def burst_runoff(p24: np.ndarray, p3: np.ndarray, g_ft: np.ndarray, z_ft: float) -> np.ndarray:
    """Runoff (in) during the 3-h burst, centred in the storm (SCS Type II / FLMOD peaks mid-storm:
    half the non-burst rain falls first). Shallow groundwater shrinks soil storage."""
    p3 = np.minimum(p3, p24)
    s_r = (1000 / CN - 10) * np.clip((z_ft - g_ft) / SOIL_DEPTH_FT, 0, 1)
    pa = (p24 - p3) / 2
    return scs_runoff(pa + p3, s_r) - scs_runoff(pa, s_r)


def _rates(c_ft: np.ndarray, g_ft: np.ndarray, z_ft: float) -> tuple[np.ndarray, np.ndarray]:
    stage = z_ft + TOL_FT
    return np.sqrt(np.maximum(stage - c_ft, 0)), np.maximum(stage - g_ft - WELL_START_FT, 0)


@dataclass(frozen=True)
class Drainage:
    k_out: float  # in/hr per sqrt(ft) of outfall head
    k_well: float  # in/hr per ft of ponded stage above groundwater + 1.6 ft
    anchor: dict = field(default_factory=dict)

    def capacity(self, c_ft: np.ndarray, g_ft: np.ndarray, z_ft: float) -> np.ndarray:
        out, well = _rates(c_ft, g_ft, z_ft)
        return BURST_HOURS * (self.k_out * out + self.k_well * well)


def calibrate_drainage() -> Drainage:
    """Fix the two capacity constants from the 5-yr LOS anchor (see ASSUMPTIONs above)."""
    pf = pfds_ams()
    i = rainfall.AMS_RETURN_PERIODS.index(ANCHOR_RP)
    p24, p3 = pf["24h"][i], pf["3h"][i]
    mhhw = mhhw_navd_ft()
    c, g = mhhw, mhhw + float(np.mean(GW_OFFSET_FT))
    r = float(burst_runoff(np.array(p24), np.array(p3), np.array(g), ANCHOR_Z_FT))
    need = r - 12 * TOL_FT / CATCH_RATIO  # drainage that leaves exactly TOL of ponding
    out, well = (float(x) for x in _rates(np.array(c), np.array(g), ANCHOR_Z_FT))
    if need <= 0 or out <= 0 or well <= 0:
        raise RuntimeError("drainage anchor is degenerate; check the anchor constants")
    k_out = OUTFALL_SHARE * need / (BURST_HOURS * out)
    k_well = (1 - OUTFALL_SHARE) * need / (BURST_HOURS * well)
    return Drainage(k_out, k_well, {"z_ft": ANCHOR_Z_FT, "p24_in": p24, "p3_in": p3, "c_ft": c, "g_ft": g,
                                    "burst_runoff_in": r, "drainage_in_per_3h": need})  # fmt: skip


# ----------------------------------------------------------------------------- discretized model


@dataclass(frozen=True)
class Config:
    year: int = 2050
    scenario: str = "intermediate"
    z_ft: float = 3.0  # street low-point elevation, ft NAVD88
    drivers: tuple[str, ...] = DRIVERS  # random drivers; the rest are frozen at their median
    tau_wp: float = TAU_WP
    rho_p: float = RHO_P
    delta_ft: float = 0.125  # shared grid step of W, S, O
    w_lo_ft: float = 0.3  # lowest W node, ft NAVD88 (GEV lower bound is ~0.4 ft NAVD)
    n_w: int = 6
    n_s: int = 4
    n_o: int = 3
    n_p24: int = 5
    n_p3: int = 5
    p24_max_in: float = 24.0
    p3_max_in: float = 12.0
    regime_bits: int = 3
    n_k: int = 7
    g_drop: int = 2  # the runoff table sees groundwater at 2**g_drop coarser resolution
    gev: tuple[float, float, float] | None = None  # override (c, loc, scale) m above MHHW, for bootstrap


def _fold(cdf_at_inner_edges: np.ndarray) -> np.ndarray:
    """Bin masses from CDF values at the inner edges; both tails folded into the end bins."""
    return np.diff(np.concatenate([[0.0], cdf_at_inner_edges, [1.0]]))


def _copula_conditional(
    parent_pmf: np.ndarray, regime_bits: int, child_cdf_edges: np.ndarray, rho: float
) -> np.ndarray:
    """(2**regime_bits, n_child) child-bin masses given the parent's top-bit regime under a Gaussian
    copula: average of P(V <= v | U = u) over u in the regime's parent-CDF block, 64-point
    Gauss-Legendre (robust even for regimes with tiny mass, unlike differencing a bivariate CDF)."""
    n_reg = 2**regime_bits
    block = len(parent_pmf) // n_reg
    ucdf = np.concatenate([[0.0], np.cumsum(parent_pmf)])
    xg, wg = np.polynomial.legendre.leggauss(64)
    zv = stats.norm.ppf(np.clip(child_cdf_edges, 1e-15, 1 - 1e-15))
    rows = []
    for r in range(n_reg):
        a, b = ucdf[r * block], min(ucdf[(r + 1) * block], 1.0)
        if b - a < 1e-300:
            a, b = max(a - 1e-12, 0.0), min(a + 1e-12, 1.0)
        u = np.clip(a + (b - a) * (xg + 1) / 2, 1e-15, 1 - 1e-15)
        zu = stats.norm.ppf(u)
        cond = stats.norm.cdf((zv[None, :] - rho * zu[:, None]) / np.sqrt(1 - rho**2))
        rows.append(_fold((wg[:, None] * cond).sum(0) / 2))
    return np.array(rows)


class Model:
    """One discretized joint model + integer flood tables for one street elevation."""

    def __init__(self, cfg: Config, drainage: Drainage | None = None):
        bad = set(cfg.drivers) - set(DRIVERS)
        if bad or "W" not in cfg.drivers or "P24" not in cfg.drivers:
            raise ValueError(f"drivers must include W and P24 and come from {DRIVERS}; got {cfg.drivers}")
        self.cfg = cfg
        self.drain = drainage or calibrate_drainage()
        self.mhhw = mhhw_navd_ft()
        d = cfg.delta_ft
        self.random = [x for x in DRIVERS if x in cfg.drivers]  # sampling order: W, P24, P3, S, O
        self.nbits = {"W": cfg.n_w, "P24": cfg.n_p24, "P3": cfg.n_p3 if "P3" in cfg.drivers else 0,
                      "S": cfg.n_s if "S" in cfg.drivers else 0, "O": cfg.n_o if "O" in cfg.drivers else 0}  # fmt: skip

        # W: nodes w_lo + d*k, masses of the surrounding half-step intervals (GEV in m above MHHW).
        if cfg.gev is None:
            _, amax, _, _ = flood.load_annual_maxima()
            self.gev = flood.fit_gev(amax)
        else:
            self.gev = cfg.gev
        nw = 2**cfg.n_w
        self.w_nodes = cfg.w_lo_ft + d * np.arange(nw)
        w_edges_m = (self.w_nodes[:-1] + d / 2 - self.mhhw) / FT_PER_M
        self.pmf_w = _fold(stats.genextreme.cdf(w_edges_m, *self.gev))

        # S: split normal, grid centred on the median.
        self.slr = slr_offset_ft(cfg.year, cfg.scenario)
        med = self.slr[0]
        if self.nbits["S"]:
            ns = 2 ** self.nbits["S"]
            self.s_lo = med - d * (ns - 1) / 2
            s_nodes = self.s_lo + d * np.arange(ns)
            self.pmf_s = _fold(split_normal_cdf(s_nodes[:-1] + d / 2, *self.slr))
        else:
            self.s_lo, self.pmf_s = med, np.ones(1)

        # O: uniform groundwater offset, grid centred on its mean.
        o_mid = float(np.mean(GW_OFFSET_FT))
        if self.nbits["O"]:
            no = 2 ** self.nbits["O"]
            self.o_lo = o_mid - d * (no - 1) / 2
            o_nodes = self.o_lo + d * np.arange(no)
            self.pmf_o = _fold(stats.uniform.cdf(o_nodes[:-1] + d / 2, GW_OFFSET_FT[0], np.ptp(GW_OFFSET_FT)))
        else:
            self.o_lo, self.pmf_o = o_mid, np.ones(1)

        # Rain marginals (Gumbel on Atlas 14 AMS), bin centres, tails folded.
        pf = pfds_ams()
        self.g24 = rainfall.fit_gumbel(np.array(pf["24h"]))
        self.g3 = rainfall.fit_gumbel(np.array(pf["3h"]))
        n24, w24 = 2**cfg.n_p24, cfg.p24_max_in / 2**cfg.n_p24
        self.p24_nodes = w24 * (np.arange(n24) + 0.5)
        e24 = stats.gumbel_r.cdf(w24 * np.arange(1, n24), *self.g24)
        rho_wp = float(np.sin(np.pi * cfg.tau_wp / 2))  # Kendall tau -> Gaussian-copula rho
        self.cond_p24 = _copula_conditional(self.pmf_w, cfg.regime_bits, e24, rho_wp)
        if self.nbits["P3"]:
            n3, w3 = 2**cfg.n_p3, cfg.p3_max_in / 2**cfg.n_p3
            self.p3_nodes = w3 * (np.arange(n3) + 0.5)
            e3 = stats.gumbel_r.cdf(w3 * np.arange(1, n3), *self.g3)
            p24_marg = self.pmf_w_regimes() @ self.cond_p24
            self.cond_p3 = _copula_conditional(p24_marg, cfg.regime_bits, e3, cfg.rho_p)
        else:  # comonotone: the 3-h depth at the same Atlas-14 quantile as the 24-h depth
            u = stats.gumbel_r.cdf(self.p24_nodes, *self.g24)
            self.p3_nodes = stats.gumbel_r.ppf(np.clip(u, 1e-12, 1 - 1e-12), *self.g3)
            self.cond_p3 = np.ones((1, 1))
        self._build_tables()

    def pmf_w_regimes(self) -> np.ndarray:
        n_reg = 2**self.cfg.regime_bits
        return self.pmf_w.reshape(n_reg, -1).sum(1)

    # ---- integer layout: c = w + s, g = s + o
    def _build_tables(self) -> None:
        cfg, d = self.cfg, self.cfg.delta_ft
        ns, no = 2 ** self.nbits["S"], 2 ** self.nbits["O"]
        self.n_c = int(2**cfg.n_w + ns - 2).bit_length()
        self.n_g = int(ns + no - 2).bit_length()
        self.n_gr = max(self.n_g - cfg.g_drop, 0)  # groundwater bits the runoff table sees
        c_idx, g_idx = np.arange(2**self.n_c), np.arange(2**self.n_g)
        self.c_ft = cfg.w_lo_ft + self.s_lo + d * c_idx
        self.g_ft = self.mhhw + self.s_lo + self.o_lo + d * g_idx
        z, kmax = cfg.z_ft, 2**cfg.n_k - 1
        self.delta_r = R_FULL_IN / (kmax - 1)

        cc, gg = np.meshgrid(self.c_ft, self.g_ft, indexing="ij")
        base = np.maximum(np.maximum(cc, gg), z) - z
        t_phys = self.drain.capacity(cc, gg, z) + 12 * (TOL_FT - base) / CATCH_RATIO
        t_int = np.minimum(np.ceil(t_phys / self.delta_r - 1e-9), kmax)
        self.T = np.where(base >= TOL_FT, 0, t_int).astype(np.int64)  # [c, g]

        drop = self.n_g - self.n_gr
        g_coarse = self.mhhw + self.s_lo + self.o_lo + d * ((np.arange(2**self.n_gr) << drop) + (2**drop - 1) / 2)
        n24, n3 = len(self.p24_nodes), (len(self.p3_nodes) if self.nbits["P3"] else 1)
        p24 = self.p24_nodes[:, None, None]
        p3 = self.p3_nodes[None, :, None] if self.nbits["P3"] else self.p3_nodes[:, None, None]
        r = burst_runoff(p24, p3, g_coarse[None, None, :], z)
        self.R = np.minimum(np.floor(r / self.delta_r + 1e-9), kmax - 1).astype(np.int64)  # [p24, p3, g>>drop]
        assert self.R.shape == (n24, n3, 2**self.n_gr)
        self.g_shift = drop

    # ---- sampling: Rosenblatt chain W -> P24 | regime(W) -> P3 | regime(P24); S, O independent
    def _regime(self, b: np.ndarray, nbits: int) -> np.ndarray:
        return b >> (nbits - self.cfg.regime_bits)

    def bins_from_u(self, u: np.ndarray) -> dict[str, np.ndarray]:
        """u: (N, len(self.random)) in [0,1). Inverse-CDF each driver through its (conditional) pmf."""
        col = {name: u[:, i] for i, name in enumerate(self.random)}
        b: dict[str, np.ndarray] = {}
        b["W"] = _inv(np.cumsum(self.pmf_w), col["W"])
        b["P24"] = _inv_rows(np.cumsum(self.cond_p24, 1), self._regime(b["W"], self.cfg.n_w), col["P24"])
        if self.nbits["P3"]:
            b["P3"] = _inv_rows(np.cumsum(self.cond_p3, 1), self._regime(b["P24"], self.cfg.n_p24), col["P3"])
        for name, pmf in (("S", self.pmf_s), ("O", self.pmf_o)):
            b[name] = _inv(np.cumsum(pmf), col[name]) if self.nbits[name] else np.zeros(len(u), np.int64)
        return b

    def indicator(self, b: dict[str, np.ndarray]) -> np.ndarray:
        c = b["W"] + b["S"]
        g = b["S"] + b["O"]
        p3 = b["P3"] if self.nbits["P3"] else np.zeros_like(c)
        return self.R[b["P24"], p3, g >> self.g_shift] >= self.T[c, g]

    # ---- conditional MC: integrate the leaf of the rain chain exactly given everything else
    @property
    def leaf(self) -> str:
        return "P3" if self.nbits["P3"] else "P24"

    def leaf_rows(self, b: dict[str, np.ndarray]) -> np.ndarray:
        if self.leaf == "P3":
            return self.cond_p3[self._regime(b["P24"], self.cfg.n_p24)]
        return self.cond_p24[self._regime(b["W"], self.cfg.n_w)]

    def cond_prob(self, b: dict[str, np.ndarray]) -> np.ndarray:
        """P(flood | all drivers except the leaf). The rule is monotone in the leaf bin, so the
        threshold bin is found by bisection: n_leaf indicator evaluations per sample."""
        rows = self.leaf_rows(b)
        n = rows.shape[1]
        lo, hi = np.zeros(len(rows), np.int64), np.full(len(rows), n, np.int64)  # first flooding bin in [lo, hi]
        while np.any(lo < hi):
            mid = (lo + hi) // 2
            bb = dict(b)
            bb[self.leaf] = np.minimum(mid, n - 1)
            hit = self.indicator(bb)
            active = lo < hi
            hi = np.where(active & hit, mid, hi)
            lo = np.where(active & ~hit, mid + 1, lo)
        cdf = np.concatenate([np.zeros((len(rows), 1)), np.cumsum(rows, 1)], 1)
        return 1 - cdf[np.arange(len(rows)), lo]

    def nonleaf(self) -> list[str]:
        return [x for x in self.random if x != self.leaf]

    def bins_from_u_nonleaf(self, u: np.ndarray) -> dict[str, np.ndarray]:
        full = np.zeros((len(u), len(self.random)))
        for i, name in enumerate(self.nonleaf()):
            full[:, self.random.index(name)] = u[:, i]
        return self.bins_from_u(full)  # the leaf column is ignored by cond_prob

    # ---- exact answer on the discretized model (enumerate non-leaf grid, leaf tail exact)
    def exact(self, chunk: int = 1 << 18) -> float:
        names = self.nonleaf()
        sizes = [2 ** self.nbits[x] for x in names]
        total, acc = int(np.prod(sizes)), 0.0
        for start in range(0, total, chunk):
            idx = np.arange(start, min(start + chunk, total))
            b, w = {}, np.ones(len(idx))
            for name, size in zip(reversed(names), reversed(sizes)):
                b[name], idx = idx % size, idx // size
            for name in ("S", "O"):
                b.setdefault(name, np.zeros(len(w), np.int64))
            w *= self.pmf_w[b["W"]] * self.pmf_s[b["S"]] * self.pmf_o[b["O"]]
            if self.leaf == "P3":
                w *= self.cond_p24[self._regime(b["W"], self.cfg.n_w), b["P24"]]
            acc += float((w * self.cond_prob(b)).sum())
        return acc

    def grid_size(self) -> int:
        """Number of cells in the full discretized joint (2**data qubits)."""
        return int(2 ** sum(self.nbits.values()))

    def summary(self) -> dict:
        return {"drivers": self.random, "d": len(self.random), "nbits": self.nbits, "n_c": self.n_c,
                "n_g": self.n_g, "n_gr": self.n_gr, "n_k": self.cfg.n_k, "delta_ft": self.cfg.delta_ft,
                "delta_r_in": self.delta_r, "z_ft": self.cfg.z_ft, "year": self.cfg.year,
                "scenario": self.cfg.scenario, "slr_ft_median_sig_lo_sig_hi": list(self.slr),
                "tau_wp": self.cfg.tau_wp, "rho_p": self.cfg.rho_p, "gev_m": list(self.gev),
                "gumbel_24h_in": list(self.g24), "gumbel_3h_in": list(self.g3), "mhhw_navd_ft": self.mhhw,
                "drainage": {"k_out": self.drain.k_out, "k_well": self.drain.k_well, **self.drain.anchor}}  # fmt: skip


def _inv(cdf: np.ndarray, u: np.ndarray) -> np.ndarray:
    return np.minimum(np.searchsorted(cdf, u, side="right"), len(cdf) - 1)


def _inv_rows(cdf_rows: np.ndarray, row: np.ndarray, u: np.ndarray) -> np.ndarray:
    """Per-sample inverse CDF with a per-sample row of a small table (vectorized bisection)."""
    c = cdf_rows[row]
    return np.minimum((c < u[:, None]).sum(1), cdf_rows.shape[1] - 1)


def mechanisms(model: Model) -> dict[str, float]:
    """Driver contributions on the exact discretized model: the probability with each random
    driver frozen at its median (one at a time; W frozen means "a typical year's peak water level",
    P3 frozen means the comonotone 3-h burst), plus the zero-rain (tide + groundwater only) pathway."""
    out = {}
    for name in model.random:
        if name in ("W", "P24"):
            out[f"{name}_frozen"] = _frozen_major(model, name)
        else:
            cfg = replace(model.cfg, drivers=tuple(x for x in model.random if x != name))
            out[f"{name}_frozen"] = Model(cfg, model.drain).exact()
    out["no_rain"] = _tide_only(model)
    return out


def _frozen_major(model: Model, name: str) -> float:
    """Freeze W or P24 at its median bin: rebuild with that driver's pmf collapsed to one node."""
    m = Model(model.cfg, model.drain)
    if name == "W":
        k = int(np.searchsorted(np.cumsum(m.pmf_w), 0.5))
        m.pmf_w = np.eye(len(m.pmf_w))[k]
    else:
        marg = m.pmf_w_regimes() @ m.cond_p24
        k = int(np.searchsorted(np.cumsum(marg), 0.5))
        m.cond_p24 = np.tile(np.eye(m.cond_p24.shape[1])[k], (m.cond_p24.shape[0], 1))
    return m.exact()


def _tide_only(m: Model) -> float:
    """P(flood with zero rain) = P(max(C, G, z) - z >= TOL), exact."""
    w = np.arange(2**m.cfg.n_w)[:, None, None]
    s = np.arange(len(m.pmf_s))[None, :, None]
    o = np.arange(len(m.pmf_o))[None, None, :]
    hit = m.T[w + s, s + o] == 0
    p = m.pmf_w[:, None, None] * m.pmf_s[None, :, None] * m.pmf_o[None, None, :]
    return float((p * hit).sum())


if __name__ == "__main__":
    m = Model(Config())
    print(json.dumps(m.summary(), indent=1))
    print("exact a =", m.exact(), " grid cells =", m.grid_size())
    rng = np.random.default_rng(0)
    u = rng.random((200000, len(m.random)))
    print("MC a    =", m.indicator(m.bins_from_u(u)).mean())
