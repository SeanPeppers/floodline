// The five-driver street flood rule of multidriver.py, ported line for line
// (scs_runoff, burst_runoff, _rates, Drainage.capacity and the flood test in
// the module docstring). Constants come from assets/data/floodrule.json, which
// web_data.py writes from multidriver.py itself, so there is one source.
// check_floodrule_port.py compares this file with the Python on random cases.
// All stages ft NAVD88, rain inches.

const clip01 = (x) => Math.min(1, Math.max(0, x));

export function scsRunoff(p, sr) {
  const ia = 0.2 * sr;
  return p > ia ? (p - ia) ** 2 / Math.max(p - ia + sr, 1e-12) : 0;
}

// Runoff (in) during the 3-h burst, centred in the storm; shallow groundwater
// shrinks soil storage.
export function burstRunoff(k, p24, p3, g, z) {
  p3 = Math.min(p3, p24);
  const sr = (1000 / k.CN - 10) * clip01((z - g) / k.SOIL_DEPTH_FT);
  const pa = (p24 - p3) / 2;
  return scsRunoff(pa + p3, sr) - scsRunoff(pa, sr);
}

// Drainage over the burst (in): outfalls ~ sqrt(head to the sea), gravity
// wells linear above groundwater + 1.6 ft.
export function capacity(k, c, g, z) {
  const stage = z + k.TOL_FT;
  const out = Math.sqrt(Math.max(stage - c, 0));
  const well = Math.max(stage - g - k.WELL_START_FT, 0);
  return k.BURST_HOURS * (k.k_out * out + k.k_well * well);
}

// Water above the street's low point z minus the 6-inch tolerance (ft):
// floods when >= 0. c = coastal stage, g = groundwater stage.
export function floodMargin(k, c, g, p24, p3, z) {
  const base = Math.max(c, g, z) - z;
  const pond = (k.CATCH_RATIO * Math.max(burstRunoff(k, p24, p3, g, z) - capacity(k, c, g, z), 0)) / 12;
  return base + pond - k.TOL_FT;
}
