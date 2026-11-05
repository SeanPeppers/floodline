"""Real data: NOAA Atlas 14 (PFDS) precipitation-frequency estimates for the Key West grid
cell at 24.5557 N, 81.8079 W -- the same point as NOAA tide station 8724580 (flood.py), to
within about 70 m. 24-hour duration, annual maximum series (AMS). NOAA's PFDS server already
did the extreme-value fitting from the raw daily-rainfall record; it returns only the fitted
return-period depths, not the underlying series. We re-fit a three-parameter GEV to those nine
published (return period, depth) points by least squares on the quantile curve -- a standard
hydrology technique for working from a published frequency curve, not a fit to a raw series we
don't have. flood.py's tide fit, by contrast, is a fit to the raw annual-maxima series.

Why GEV and not the Gumbel an earlier build used: that two-parameter Gumbel (OLS on the reduced
variate) missed NOAA's own 2-yr depth by 42% (2.57 in vs 4.40 in) and put the nominal "10-yr"
depth at a ~8-yr exceedance. drainage.py's flood rule is decided by rain in exactly that 2-10 yr
range, so the misfit had to go. The GEV is within 0.25 in of all nine published depths.

Threshold (rectangle rule only): there's no NWS/FEMA "heavy rain flood stage" analogous to
flood.py's thresholds. RAIN_THRESHOLD_YEARS picks the 10-year 24-hour return period -- a
modeling choice, not an official threshold. The realistic rule (drainage.py) doesn't use it.
"""

import ast
import json
import re
from pathlib import Path

import numpy as np
import requests
from scipy import optimize, stats

DATA_DIR = Path(__file__).resolve().parent / "data"
LAT, LON = 24.5557, -81.8079  # NOAA tide station 8724580's own coordinates
PFDS_URL = "https://hdsc.nws.noaa.gov/cgi-bin/new/cgi_readH5.py"
DURATIONS = ["5m", "10m", "15m", "30m", "60m", "2h", "3h", "6h", "12h", "24h",
             "2d", "3d", "4d", "7d", "10d", "20d", "30d", "45d", "60d"]  # fmt: skip
AMS_RETURN_PERIODS = [2, 5, 10, 25, 50, 100, 200, 500, 1000]  # years; PFDS's AMS column order
RAIN_THRESHOLD_YEARS = 10  # modeling choice -- see module docstring

N_QUBITS = 5  # 32 bins: fine enough that drainage.py's curved boundary is a multi-step staircase
BIN_W = 1.865 / 4  # in; the 10-yr 24-hr depth (7.46 in) snaps to edge 16 of 32 exactly
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


def fit_gev(depths: np.ndarray) -> tuple[float, float, float]:
    """GEV (scipy shape convention) whose 1/T exceedance quantiles best match NOAA's nine
    published AMS depths, least squares in inches."""
    t = np.array(AMS_RETURN_PERIODS, dtype=float)
    res = optimize.least_squares(lambda p: stats.genextreme.isf(1 / t, *p) - depths, [-0.1, 4.0, 1.5])
    c, loc, scale = res.x
    return float(c), float(loc), float(scale)


def edges() -> np.ndarray:
    """Interior bin edges (in), 2**N_QUBITS - 1 of them."""
    return GRID_LO + BIN_W * np.arange(1, 2**N_QUBITS)


def discretize(c: float, loc: float, scale: float) -> np.ndarray:
    """Bin probabilities on the 2**N_QUBITS grid, tail mass folded into the end bins (same
    convention as flood.discretize)."""
    cdf = np.concatenate([[0.0], stats.genextreme.cdf(edges(), c, loc, scale), [1.0]])
    return np.diff(cdf)


def threshold_index(level: float) -> int:
    k = round((level - GRID_LO) / BIN_W)
    if not 0 < k < 2**N_QUBITS:
        raise ValueError(f"rain threshold {level:.2f} in falls outside the loaded grid")
    return int(k)


def problem() -> dict:
    """Everything the joint model needs for the rain marginal."""
    depths = _fetch_ams_24h()
    c, loc, scale = fit_gev(depths)
    probs = discretize(c, loc, scale)
    level = float(np.interp(RAIN_THRESHOLD_YEARS, AMS_RETURN_PERIODS, depths))
    t = threshold_index(level)
    fitted = stats.genextreme.isf(1 / np.array(AMS_RETURN_PERIODS, dtype=float), c, loc, scale)
    return {
        "station_latlon": [LAT, LON], "duration": "24h", "series": "ams",
        "return_periods_yr": AMS_RETURN_PERIODS, "depths_in": depths.tolist(),
        "gev": {"c": c, "loc": loc, "scale": scale}, "gev_max_abs_misfit_in": float(np.abs(fitted - depths).max()),
        "threshold_years": RAIN_THRESHOLD_YEARS, "threshold_level_in": level,
        "threshold_snapped_in": GRID_LO + BIN_W * t, "threshold_bin": t, "probs": probs,
    }  # fmt: skip


if __name__ == "__main__":
    p = problem()
    for k, v in p.items():
        print(k, v)
