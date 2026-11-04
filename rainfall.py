"""Real data: NOAA Atlas 14 (PFDS) precipitation-frequency estimates for the Key West grid
cell at 24.5557 N, 81.8079 W -- the same point as NOAA tide station 8724580 (flood.py), to
within about 70 m. 24-hour duration, annual maximum series (AMS). NOAA's PFDS server already
did the extreme-value fitting from the raw daily-rainfall record; it returns only the fitted
return-period depths, not the underlying series. We re-fit a two-parameter Gumbel to those nine
published (return period, depth) points -- a standard hydrology technique for working from a
published frequency curve, not a fit to a raw series we don't have. flood.py's tide fit, by
contrast, is a fit to the raw 110-year annual-maxima series. That's a real difference in how
"real data" enters each marginal; see README.

Threshold: there's no NWS/FEMA "heavy rain flood stage" analogous to flood.py's nws_major.
RAIN_THRESHOLD_YEARS picks the 10-year 24-hour return period as a stand-in for "rain heavy
enough to plausibly contribute to inland flooding" in flat, poorly-drained terrain like Key
West -- a modeling choice, not a measured or official threshold.
"""

import ast
import json
import re
from pathlib import Path

import numpy as np
import requests
from scipy import stats

DATA_DIR = Path(__file__).resolve().parent / "data"
LAT, LON = 24.5557, -81.8079  # NOAA tide station 8724580's own coordinates
PFDS_URL = "https://hdsc.nws.noaa.gov/cgi-bin/new/cgi_readH5.py"
DURATIONS = ["5m", "10m", "15m", "30m", "60m", "2h", "3h", "6h", "12h", "24h",
             "2d", "3d", "4d", "7d", "10d", "20d", "30d", "45d", "60d"]  # fmt: skip
AMS_RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]  # years; PFDS's AMS column order
RAIN_THRESHOLD_YEARS = 10  # modeling choice -- see module docstring

N_QUBITS = 3
BIN_W = 1.865  # in; tuned so the 10-yr 24-hr depth (7.46 in) snaps to bin 4 of 8 exactly
GRID_LO = 0.0


def _fetch_ams_24h() -> np.ndarray:
    cache = DATA_DIR / "keywest_pfds_ams_24h.json"
    if not cache.exists():
        DATA_DIR.mkdir(exist_ok=True)
        params: dict[str, str | float] = {
            "lat": LAT, "lon": LON, "type": "pf", "data": "depth", "units": "english", "series": "ams",
        }  # fmt: skip
        r = requests.get(PFDS_URL, params=params, timeout=60, allow_redirects=True)
        r.raise_for_status()
        m = re.search(r"quantiles\s*=\s*(\[\[.*?\]\])", r.text)
        if not m:
            raise RuntimeError("NOAA PFDS response didn't contain a quantiles table")
        rows = ast.literal_eval(m.group(1))  # single-quoted JS literal, not valid JSON
        cache.write_text(json.dumps(rows[DURATIONS.index("24h")]))
    return np.array(json.loads(cache.read_text()), dtype=float)


def fit_gumbel(depths: np.ndarray) -> tuple[float, float]:
    """Gumbel fit (x_T = loc + scale*y_T) to NOAA's own published return-period depths, where
    y_T = -ln(-ln(1 - 1/T)) is the Gumbel reduced variate for an annual-maximum series. OLS on
    the 9 points NOAA already computed from the raw series."""
    t = np.array(AMS_RETURN_PERIODS, dtype=float)
    y = -np.log(-np.log(1 - 1 / t))
    scale, loc = np.polyfit(y, depths, 1)
    return float(loc), float(scale)


def discretize(loc: float, scale: float) -> np.ndarray:
    """Bin probabilities on the 2**N_QUBITS grid, tail mass folded into the end bins (same
    convention as flood.discretize)."""
    n = 2**N_QUBITS
    edges = GRID_LO + BIN_W * np.arange(1, n)
    cdf = np.concatenate([[0.0], stats.gumbel_r.cdf(edges, loc, scale), [1.0]])
    return np.diff(cdf)


def threshold_index(level: float) -> int:
    k = round((level - GRID_LO) / BIN_W)
    if not 0 < k < 2**N_QUBITS:
        raise ValueError(f"rain threshold {level:.2f} in falls outside the loaded grid")
    return int(k)


def problem() -> dict:
    """Everything the joint model needs for the rain marginal."""
    depths = _fetch_ams_24h()
    loc, scale = fit_gumbel(depths)
    probs = discretize(loc, scale)
    level = float(np.interp(RAIN_THRESHOLD_YEARS, AMS_RETURN_PERIODS, depths))
    t = threshold_index(level)
    return {
        "station_latlon": [LAT, LON], "duration": "24h", "series": "ams",
        "return_periods_yr": AMS_RETURN_PERIODS, "depths_in": depths.tolist(),
        "gumbel": {"loc": loc, "scale": scale}, "threshold_years": RAIN_THRESHOLD_YEARS,
        "threshold_level_in": level, "threshold_snapped_in": GRID_LO + BIN_W * t,
        "threshold_bin": t, "probs": probs,
    }  # fmt: skip


if __name__ == "__main__":
    p = problem()
    for k, v in p.items():
        print(k, v)
