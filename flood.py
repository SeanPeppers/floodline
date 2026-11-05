"""Real data: NOAA CO-OPS Key West (station 8724580) monthly highest water levels,
1913-present, relative to MHHW. Reduced to annual maxima, sea-level-rise detrended
to the present, fitted with a GEV, and discretized onto 2**N_QUBITS bins for loading
into a quantum register.

The rare event is "annual peak water level reaches NWS major-flood stage", using the
NWS major threshold NOAA publishes for this station (floodlevels endpoint).
"""

import io
import json
from pathlib import Path

import numpy as np
import requests
from scipy import stats

STATION = "8724580"  # Key West, FL -- one of the longest tide-gauge records in the US
API = "https://api.tidesandcurrents.noaa.gov"
DATA_DIR = Path(__file__).resolve().parent / "data"
REF_YEAR = 2025  # detrend annual maxima to this year's mean sea level

N_QUBITS = 5
BIN_W = 0.04  # m per bin
GRID_LO = -0.12  # m above MHHW; bin edges are GRID_LO + k*BIN_W


def _get(url: str, params: dict[str, str], cache: Path) -> str:
    if not cache.exists():
        DATA_DIR.mkdir(exist_ok=True)
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        cache.write_text(r.text)
    return cache.read_text()


def load_annual_maxima() -> tuple[np.ndarray, np.ndarray, float, dict[str, float]]:
    """Returns (years, detrended annual max m above MHHW, SLR trend m/yr, thresholds m above MHHW)."""
    params = {"product": "monthly_mean", "station": STATION, "begin_date": "19130101", "end_date": "20251231",
              "datum": "MHHW", "units": "metric", "time_zone": "gmt", "format": "csv",
              "application": "fgcu_hackathon"}  # fmt: skip
    csv = _get(f"{API}/api/prod/datagetter", params, DATA_DIR / "keywest_monthly.csv")
    meta = f"{API}/mdapi/prod/webapi/stations/{STATION}"
    metric = {"units": "metric"}
    datums = json.loads(_get(f"{meta}/datums.json", metric, DATA_DIR / "keywest_datums.json"))
    floods = json.loads(_get(f"{meta}/floodlevels.json", metric, DATA_DIR / "keywest_floodlevels.json"))
    mhhw_stnd = next(d["value"] for d in datums["datums"] if d["name"] == "MHHW")
    thresholds = {k: v - mhhw_stnd for k, v in floods.items() if k.startswith("nws_") and v is not None}

    raw = np.genfromtxt(io.StringIO(csv), delimiter=",", names=True, dtype=float, encoding=None)
    year, high, msl = raw["Year"], raw["Highest"], raw["MSL"]
    ok = np.isfinite(high) & np.isfinite(msl)
    year, high, msl = year[ok], high[ok], msl[ok]
    yrs = np.unique(year)
    months = np.array([(year == y).sum() for y in yrs])
    yrs = yrs[months >= 10]  # drop years with big gaps: a missed hurricane month would bias the max low
    amax = np.array([high[year == y].max() for y in yrs])
    annual_msl = np.array([msl[year == y].mean() for y in yrs])
    slope = float(np.polyfit(yrs, annual_msl, 1)[0])
    return yrs.astype(int), amax + slope * (REF_YEAR - yrs), slope, thresholds


def mhhw_above_navd88() -> float:
    """MHHW minus NAVD88 (m) at this station, from NOAA's own published datums (0.013 m), so
    drainage.py can put the City's NAVD88 street and stormwater elevations on this module's
    MHHW-relative tide axis."""
    meta = f"{API}/mdapi/prod/webapi/stations/{STATION}/datums.json"
    datums = json.loads(_get(meta, {"units": "metric"}, DATA_DIR / "keywest_datums.json"))
    val = {d["name"]: d["value"] for d in datums["datums"]}
    return float(val["MHHW"] - val["NAVD88"])


def fit_gev(amax: np.ndarray) -> tuple[float, float, float]:
    c, loc, scale = stats.genextreme.fit(amax)
    return float(c), float(loc), float(scale)


def discretize(c: float, loc: float, scale: float) -> np.ndarray:
    """Bin probabilities on the 2**N_QUBITS grid; tail mass is folded into the end bins,
    so P(bin >= k) equals the GEV survival function at edge k exactly."""
    n = 2**N_QUBITS
    edges = GRID_LO + BIN_W * np.arange(1, n)
    cdf = np.concatenate([[0.0], stats.genextreme.cdf(edges, c, loc, scale), [1.0]])
    return np.diff(cdf)


def threshold_index(level: float) -> int:
    k = round((level - GRID_LO) / BIN_W)
    if not 0 < k < 2**N_QUBITS:
        raise ValueError(f"threshold {level:.3f} m falls outside the loaded grid")
    return int(k)


def problem() -> dict:
    """Everything the experiment needs: the loaded distribution, threshold bin, true tail prob."""
    yrs, amax, slope, thr = load_annual_maxima()
    c, loc, scale = fit_gev(amax)
    probs = discretize(c, loc, scale)
    level = thr["nws_major"]
    t = threshold_index(level)
    snapped = GRID_LO + BIN_W * t
    return {
        "years": [int(yrs[0]), int(yrs[-1])], "n_years": len(yrs), "slr_m_per_yr": slope,
        "gev": {"c": c, "loc": loc, "scale": scale}, "thresholds_m_above_mhhw": thr,
        "threshold_level": level, "threshold_snapped": snapped, "threshold_bin": t,
        "a_true": float(probs[t:].sum()), "a_gev_unsnapped": float(stats.genextreme.sf(level, c, loc, scale)),
        "empirical_exceed": int((amax >= level).sum()), "probs": probs, "amax": amax, "yrs": yrs,
    }  # fmt: skip


if __name__ == "__main__":
    p = problem()
    for k, v in p.items():
        if k not in ("probs", "amax", "yrs"):
            print(k, v)
    print("top annual maxima:", sorted(zip(p["amax"].round(3), p["yrs"]))[-6:])
