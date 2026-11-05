"""Realistic compound-flood rule for a low Key West street: water stage at the street's low point,
from tide plus rain the storm-drain system can't get rid of, compared to a flood depth.

Every number below comes from the City of Key West 2024 Stormwater Master Plan Update (SMP),
https://www.cityofkeywest-fl.gov/DocumentCenter/View/12555/Stormwater-Master-Plan_Final_02_2024 ,
unless marked ASSUMPTION. Elevations are ft NAVD88; flood.mhhw_above_navd88() (NOAA station
datums, 0.013 m) converts the tide axis.

The node: Patterson Avenue at 2nd/3rd Street (SMP node N3210, Study Area 1B), where "frequently
flooded intersections are at or near elevation 1.0 foot NAVD 88" (SMP sec 3.2.2). SMP Table 3-4,
existing conditions, 10-year 24-hour storm: roadway low point 1.12 ft; peak stage 2.06 ft with a
1-ft tide boundary, 2.37 ft with a 2.7-ft tide boundary.

Physics, in the order water moves:
1. Rain to runoff: SCS curve-number method, which is what the SMP's own model uses (sec 2.3.4.7),
   with CN 91 (SMP Table 2-6, high-density residential, 60% impervious), standard Ia = 0.2 S.
2. Runoff to stage: stage rises s ft per inch of runoff left in the system.
   ASSUMPTION, NOT MEASURED: s is constant (prismatic storage). Calibrated so that with no
   outflow, the SMP's 10-yr storm (7.6 in, SMP Table 2-2) lifts the stage from the low point to
   2.37 ft -- the SMP's 2.7-ft-tide stage, which is below that tide, so outfalls are backed up
   (flap gates) and nothing drains. Gravity wells don't help either: flow "does not begin until
   stormwater stages to approximately 1.6 feet NAVD 88" with groundwater at MHHW, and the
   groundwater "fluctuates with the tide" (SMP sec 2.3.4.8), i.e. only above the flood threshold
   below. This node's basin has no pressurized wells (SMP sec 2.3.4.8 lists the four that do).
3. Drainage vs tide (the tidal-backflow interaction): runoff drained during the storm, D(tide),
   falls as the tide rises because outfall head shrinks. D(1.0 ft) is calibrated from the
   0.31 ft of stage the 1-ft tide run drained relative to the 2.37 ft no-outflow run.
   ASSUMPTION, NOT MEASURED: D ~ sqrt(head) (turbulent pipe flow) with head = 2.37 ft - tide,
   independent of storm size; the SMP's rating is only in its model, not its text.
4. Tide in the street: ASSUMPTION, NOT MEASURED: tide above the low point stands in the street
   (porous limestone and unvalved drains; the SMP model has flap gates on every outfall and so
   no intrusion), and runoff stacks on top of it. Supporting evidence, not proof: NOAA's NWS
   minor flood stage for this gauge -- defined by observed street flooding -- is 1.14 ft NAVD88,
   within 0.02 ft of this node's low point.
5. Flood: stage >= low point + 0.5 ft. The SMP's road-flooding test: "a 6-inch threshold was
   selected as a reasonable depth" and "commonly used to test emergency vehicle access" (SMP
   sec 2.5.1). Cross-check: 1.62 ft NAVD88 is within 0.02 ft of NWS *moderate* stage (1.64 ft).

Also ASSUMPTION, inherited from the rectangle rule: each year's annual-max tide and annual-max
24-h rain occur together (copula.py links them with tau = 0.3). Real peaks rarely coincide, so
this overstates the compound probability; it's the same simplification for every estimator.

Discretization: each (tide bin, rain bin) cell is judged at its midpoint. The rule is separable --
stage - threshold = G_tide(tide) + G_rain(rain) -- which is what lets copula.py evaluate it with a
reversible adder. integer_tables() rescales both functions to integers and checks the integer
rule reproduces the float rule on every cell.
"""

import numpy as np

import flood
import rainfall

FT = 0.3048  # m
Z_LOW = 1.12  # ft NAVD88, N3210 roadway low point (SMP Table 3-4)
STAGE_TIDE_1FT = 2.06  # ft, existing 10-yr peak stage with 1.0-ft tide boundary (SMP Table 3-4)
STAGE_NO_OUTFLOW = 2.37  # ft, same with 2.7-ft tide boundary (SMP Table 3-4)
TIDE_REF = 1.0  # ft, the boundary for STAGE_TIDE_1FT
P10_SMP = 7.6  # in, 10-yr 24-h design storm the SMP ran (SMP Table 2-2)
CN = 91  # SMP Table 2-6, high-density residential
FLOOD_DEPTH = 0.5  # ft, SMP's 6-inch road-flooding threshold
Z_FLOOD = Z_LOW + FLOOD_DEPTH


def runoff_in(p_in: np.ndarray) -> np.ndarray:
    """SCS curve-number runoff depth (in) from 24-h rain depth (in)."""
    s_ret = 1000 / CN - 10
    ia = 0.2 * s_ret
    p = np.asarray(p_in, dtype=float)
    return np.where(p > ia, (p - ia) ** 2 / (p + 0.8 * s_ret), 0.0)


STAGE_PER_IN = (STAGE_NO_OUTFLOW - Z_LOW) / float(runoff_in(np.array(P10_SMP)))  # ft per in runoff
D_REF = (STAGE_NO_OUTFLOW - STAGE_TIDE_1FT) / STAGE_PER_IN  # in of runoff drained at TIDE_REF


def drained_in(tide_ft: np.ndarray) -> np.ndarray:
    head = np.clip(STAGE_NO_OUTFLOW - np.asarray(tide_ft, dtype=float), 0, None)
    return D_REF * np.sqrt(head / (STAGE_NO_OUTFLOW - TIDE_REF))


def tide_ft_navd(tide_m_mhhw: np.ndarray) -> np.ndarray:
    return (np.asarray(tide_m_mhhw) + flood.mhhw_above_navd88()) / FT


def bin_midpoints() -> tuple[np.ndarray, np.ndarray]:
    """(tide ft NAVD88, rain in) at each bin's midpoint."""
    tide_m = flood.GRID_LO + flood.BIN_W * (np.arange(2**flood.N_QUBITS) + 0.5)
    rain_in = rainfall.GRID_LO + rainfall.BIN_W * (np.arange(2**rainfall.N_QUBITS) + 0.5)
    return tide_ft_navd(tide_m), rain_in


def stage_ft(tide_ft: np.ndarray, rain_in: np.ndarray) -> np.ndarray:
    """Peak water stage (ft NAVD88) at the low point, broadcast over tide x rain."""
    t = np.asarray(tide_ft)[:, None]
    rain_stage = np.maximum(t, Z_LOW) + STAGE_PER_IN * (runoff_in(rain_in)[None, :] - drained_in(t))
    return np.maximum(rain_stage, t)


def separable_terms() -> tuple[np.ndarray, np.ndarray]:
    """G_tide (ft, per tide bin) and G_rain (ft, per rain bin) with flood <=> G_tide + G_rain >= 0.
    G_rain >= 0, so a tide bin already at flood depth gets G_tide floored at 0 (that is the
    max(rain_stage, tide) in stage_ft)."""
    t, r = bin_midpoints()
    g_t = np.maximum(t, Z_LOW) - STAGE_PER_IN * drained_in(t) - Z_FLOOD
    g_t = np.where(t >= Z_FLOOD, np.maximum(g_t, 0.0), g_t)
    return g_t, STAGE_PER_IN * runoff_in(r)


def float_mask() -> np.ndarray:
    t, r = bin_midpoints()
    return stage_ft(t, r) >= Z_FLOOD


def integer_tables(max_steps: int = 400) -> dict:
    """Smallest integer scale (unit = FLOOD_DEPTH / k ft) at which a_i + b_j >= 0 reproduces
    float_mask() on every cell. Values that can't change any cell's outcome are clipped so the
    adder register stays small."""
    g_t, g_r = separable_terms()
    target = float_mask()
    for k in range(1, max_steps + 1):
        unit = FLOOD_DEPTH / k
        a = np.round(g_t / unit).astype(int)
        b = np.round(g_r / unit).astype(int)
        if np.array_equal(a[:, None] + b[None, :] >= 0, target):
            break
    else:
        raise RuntimeError("no integer scale reproduces the float flood rule")
    a = np.minimum(a, 0)
    b = np.minimum(b, -a.min())
    a = np.maximum(a, -b.max() - 1)
    assert np.array_equal(a[:, None] + b[None, :] >= 0, target)
    return {"a": a, "b": b, "unit_ft": unit}


if __name__ == "__main__":
    t, r = bin_midpoints()
    tab = integer_tables()
    print(
        f"stage per in runoff {STAGE_PER_IN:.4f} ft, drained at 1-ft tide {D_REF:.3f} in, unit {tab['unit_ft']:.4f} ft"
    )
    print("a:", tab["a"].tolist())
    print("b:", tab["b"].tolist())
    for i, row in enumerate(float_mask()):
        print(f"{i:2d} {t[i]:5.2f} ft", "".join("#" if h else "." for h in row))
