// "Tonight in Key West": live NOAA tide predictions and observations plus the
// NWS rain forecast, run through the five-driver street flood rule
// (floodrule.js, a line-for-line port of multidriver.py) for every road point,
// with a small ensemble over the inputs we can't pin down. Also a 2050
// planning view from the CLI's own per-scenario curves (floodrule.json).
// Every request goes to a public, keyless, CORS-enabled US-government API and
// carries no user data. If a source fails, the panel says so and shows nothing
// in its place.
import { floodMargin } from "./floodrule.js";
import { loadStreets } from "./streets.js";

const root = document.getElementById("tonight");

const STATION = "8724580";
const GAUGE = { lat: 24.5557, lon: -81.8079 };
const COOPS = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter";
const FT_PER_M = 3.28084;
const HOUR = 3600e3;
// Ensemble. O: the SMP's 0.5-1.5 ft groundwater range at five quantile
// midpoints of the model's uniform. Rain factor x0.5 / x1 / x2: ASSUMPTION, a
// rough spread for a point QPF, not an NWS figure. Burst: the wettest QPF block
// spread evenly, or all of it inside 3 h. Anomaly: last 24 h mean +- 1 sd.
const O_FT = [0.6, 0.8, 1.0, 1.2, 1.4];
const RAIN_FACTORS = [0.5, 1, 2];
const LIKELY = 2 / 3, POSSIBLE = 1 / 3;
const COLORS = { dry: "rgba(225,232,240,0.38)", low: "#ffe08a", mid: "#ff9f1c", high: "#ff3b30" };
const SCENARIO_LABEL = { low: "Low", "intermediate-low": "Intermediate-Low", intermediate: "Intermediate", "intermediate-high": "Intermediate-High", high: "High" };

const fmtTime = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", weekday: "short", hour: "numeric", minute: "2-digit" });
const fmtTimeShort = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });
const ft = (x) => `${x >= 0 ? "" : "−"}${Math.abs(x).toFixed(2)} ft`;
const pct = (x) => `${(x * 100).toFixed(x > 0 && x < 0.01 ? 1 : 0)}%`;

function getJSON(url, timeoutMs = 15000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  return fetch(url, { signal: ctl.signal, headers: { Accept: "application/json, application/geo+json" } })
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .finally(() => clearTimeout(t));
}

// CO-OPS: times requested in GMT so parsing needs no time-zone guessing.
const coops = (params) => getJSON(`${COOPS}?${new URLSearchParams({ station: STATION, datum: "NAVD", units: "english", time_zone: "gmt", format: "json", application: "floodline-fgcu-research-prototype", ...params })}`);
const coopsTime = (t) => Date.parse(`${t.replace(" ", "T")}:00Z`);
const ymd = (d) => d.toISOString().slice(0, 10).replace(/-/g, "");

function series(rows, key) {
  if (!Array.isArray(rows)) throw new Error("unexpected CO-OPS response");
  const m = new Map();
  for (const r of rows) if (r.v !== "" && Number.isFinite(Number(r.v))) m.set(r.t, Number(r.v));
  if (!m.size) throw new Error(`no ${key} values`);
  return m;
}

async function fetchTides(now) {
  const d = await coops({ product: "predictions", interval: "hilo", begin_date: ymd(new Date(now - 6 * HOUR)), range: "72" });
  if (!Array.isArray(d.predictions)) throw new Error(d.error?.message || "no predictions");
  const highs = d.predictions.filter((p) => p.type === "H")
    .map((p) => ({ t: coopsTime(p.t), v: Number(p.v) }))
    .filter((p) => p.t > now - HOUR && p.t < now + 48 * HOUR && Number.isFinite(p.v));
  if (!highs.length) throw new Error("no high tides in the next 48 h");
  return highs;
}

// Observed minus predicted water level over the last 24 h: the part of tonight's
// water the astronomical tide leaves out (sea-level rise since the 1983-2001
// datum epoch, the seasonal cycle, wind).
async function fetchAnomaly(now) {
  const [obs, pred] = await Promise.all([coops({ product: "water_level", date: "recent" }), coops({ product: "predictions", date: "recent" })]);
  const o = series(obs.data, "observed"), p = series(pred.predictions, "predicted");
  const diffs = [];
  let last = 0;
  for (const [t, v] of o) {
    const tt = coopsTime(t);
    if (tt >= now - 24 * HOUR && p.has(t)) { diffs.push(v - p.get(t)); last = Math.max(last, tt); }
  }
  if (diffs.length < 120 || now - last > 3 * HOUR) throw new Error("too few recent observations");
  const mean = diffs.reduce((a, b) => a + b, 0) / diffs.length;
  const sd = Math.sqrt(diffs.reduce((a, b) => a + (b - mean) ** 2, 0) / (diffs.length - 1));
  return { mean, sd, n: diffs.length, last };
}

function isoHours(dur) {
  const m = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$/.exec(dur);
  if (!m) throw new Error(`unparsed duration ${dur}`);
  return Number(m[1] || 0) * 24 + Number(m[2] || 0) + Number(m[3] || 0) / 60;
}

async function fetchRain() {
  const pt = await getJSON(`https://api.weather.gov/points/${GAUGE.lat},${GAUGE.lon}`);
  const url = pt.properties?.forecastGridData;
  if (!url || !url.startsWith("https://api.weather.gov/gridpoints/")) throw new Error("no forecast grid");
  const g = await getJSON(url);
  const q = g.properties?.quantitativePrecipitation;
  if (!q || q.uom !== "wmoUnit:mm" || !Array.isArray(q.values)) throw new Error("unexpected QPF shape");
  const blocks = q.values.map((v) => {
    const [start, dur] = v.validTime.split("/");
    const t0 = Date.parse(start), h = isoHours(dur);
    return { t0, t1: t0 + h * HOUR, h, inch: (Number(v.value) || 0) / 25.4 };
  }).filter((b) => Number.isFinite(b.t0) && b.h > 0);
  if (!blocks.length) throw new Error("empty QPF");
  return { blocks, updated: Date.parse(g.properties.updateTime), office: url.split("/")[4] };
}

// 24-h rain centred on the high tide and the 3-h burst bounds, from QPF blocks
// (rain assumed even within a block). Undefined if QPF doesn't cover the window.
function rainFor(rain, t) {
  const w0 = t - 12 * HOUR, w1 = t + 12 * HOUR;
  if (rain.blocks[0].t0 > w0 + 6 * HOUR || rain.blocks.at(-1).t1 < w1) return undefined;
  let p24 = 0, rate = 0, block = 0;
  for (const b of rain.blocks) {
    const ov = Math.max(0, Math.min(b.t1, w1) - Math.max(b.t0, w0)) / HOUR;
    if (!ov) continue;
    p24 += (b.inch * ov) / b.h;
    rate = Math.max(rate, b.inch / b.h);
    block = Math.max(block, (b.inch * ov) / b.h);
  }
  return { p24, p3: [Math.min(p24, 3 * rate), Math.min(p24, block)] };
}

// Fraction of ensemble members in which each road point floods.
function likelihoods(k, streets, high, anomaly, rain) {
  const cs = anomaly ? [anomaly.mean - anomaly.sd, anomaly.mean, anomaly.mean + anomaly.sd].map((a) => high.v + a) : [high.v];
  const rains = rain ? RAIN_FACTORS.flatMap((f) => [...new Set(rain.p3)].map((p3) => [f * rain.p24, f * p3])) : [[0, 0]];
  const members = cs.flatMap((c) => O_FT.flatMap((o) => rains.map(([p24, p3]) => [c, k.MHHW_NAVD_FT + o, p24, p3])));
  const out = new Float32Array(streets.pieces.length);
  streets.pieces.forEach((p, i) => {
    let n = 0;
    for (const [c, g, p24, p3] of members) if (floodMargin(k, c, g, p24, p3, p.z) >= 0) n++;
    out[i] = n / members.length;
  });
  return { values: out, members: members.length };
}

function interp(x, xs, ys) {
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) if (x <= xs[i]) return ys[i - 1] + ((ys[i] - ys[i - 1]) * (x - xs[i - 1])) / (xs[i] - xs[i - 1]);
  return ys.at(-1);
}

// Per named street: highest point value and its lowest sample. Points below
// MHHW are left out of the list: a road under every high tide is a bridge deck
// or a lidar water return, not a street (they stay in the % counts, as in the CLI).
function byStreet(streets, values, cut, floorFt) {
  const m = new Map();
  streets.pieces.forEach((p, i) => {
    if (!p.name || values[i] < cut || p.z < floorFt) return;
    const s = m.get(p.name) || { name: p.name, max: 0, minZ: Infinity, n: 0 };
    s.max = Math.max(s.max, values[i]);
    s.minZ = Math.min(s.minZ, p.z);
    s.n++;
    m.set(p.name, s);
  });
  return [...m.values()].sort((a, b) => b.max - a.max || a.minZ - b.minZ);
}

// ---------- map ----------
const CROP = { w: -81.8155, e: -81.729, s: 24.537, n: 24.5885 };
const ORTHO = { w: -81.82, e: -81.72, s: 24.535, n: 24.59 }; // the scene's NAIP bbox
const COS = Math.cos((24.5625 * Math.PI) / 180);
const ASPECT = ((CROP.e - CROP.w) * COS) / (CROP.n - CROP.s);

function drawMap(canvas, img, streets, values, classify) {
  const cssW = canvas.clientWidth, cssH = canvas.clientHeight || cssW / ASPECT;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#0b1420";
  ctx.fillRect(0, 0, cssW, cssH);
  if (img) {
    const sx = ((CROP.w - ORTHO.w) / (ORTHO.e - ORTHO.w)) * img.naturalWidth, sw = ((CROP.e - CROP.w) / (ORTHO.e - ORTHO.w)) * img.naturalWidth;
    const sy = ((ORTHO.n - CROP.n) / (ORTHO.n - ORTHO.s)) * img.naturalHeight, sh = ((CROP.n - CROP.s) / (ORTHO.n - ORTHO.s)) * img.naturalHeight;
    ctx.globalAlpha = 0.55;
    ctx.drawImage(img, sx, sy, sw, sh, 0, 0, cssW, cssH);
    ctx.globalAlpha = 1;
  }
  const X = (lon) => ((lon - CROP.w) / (CROP.e - CROP.w)) * cssW, Y = (lat) => ((CROP.n - lat) / (CROP.n - CROP.s)) * cssH;
  const lw = cssW < 500 ? 1.3 : 2;
  ctx.lineCap = "round";
  for (const cls of ["dry", "low", "mid", "high"]) {
    ctx.beginPath();
    streets.pieces.forEach((p, i) => {
      if (classify(values ? values[i] : 0) !== cls) return;
      ctx.moveTo(X(p.a[0]), Y(p.a[1]));
      ctx.lineTo(X(p.s[0]), Y(p.s[1]));
      ctx.lineTo(X(p.b[0]), Y(p.b[1]));
    });
    ctx.strokeStyle = COLORS[cls];
    ctx.lineWidth = cls === "dry" ? lw * 0.6 : lw * 1.7;
    ctx.stroke();
  }
}

// ---------- UI ----------
function init() {
  const $ = (sel) => root.querySelector(sel);
  const status = $("#tonight-status"), summary = $("#tonight-summary"), canvas = $("#tonight-map");
  const tidesBox = $("#tonight-tides"), scenarioBox = $("#tonight-scenario-wrap"), scenarioSel = $("#tonight-scenario");
  const rows = $("#tonight-rows"), inputs = $("#tonight-inputs"), legend = $("#tonight-legend"), head = $("#tonight-col");
  let ctx = null; // everything loaded: { k, streets, img, live, nws, highs, ... }
  let mode = "live", tideIdx = 0;

  const setStatus = (text, kind = "") => { status.textContent = text; status.dataset.kind = kind; };
  const loadImg = () => new Promise((res) => {
    const img = new Image();
    img.onload = () => res(img);
    img.onerror = () => res(null);
    img.src = "assets/keywest/ortho-naip-2048.webp";
  });

  function row(cells) {
    const tr = document.createElement("tr");
    cells.forEach((c, i) => { const td = document.createElement(i ? "td" : "th"); if (!i) td.scope = "row"; td.textContent = c; tr.appendChild(td); });
    return tr;
  }
  function setRows(list, fmt) {
    rows.replaceChildren(...(list.length ? list.slice(0, 10).map((s) => row([s.name, ft(s.minZ), fmt(s.max), String(s.n)])) : [row(["None in this view", "", "", ""])]));
  }
  function setLegend(items) {
    legend.replaceChildren(...items.map(([cls, text]) => {
      const li = document.createElement("li");
      const key = document.createElement("span");
      key.className = "tonight__key";
      key.style.background = COLORS[cls];
      li.append(key, text);
      return li;
    }));
  }
  function setInputs(pairs) {
    inputs.replaceChildren(...pairs.flatMap(([dt, dd]) => {
      const a = document.createElement("dt"), b = document.createElement("dd");
      a.textContent = dt;
      b.textContent = dd;
      return [a, b];
    }));
  }

  function renderLive() {
    const { k, streets, img, tides, anomaly, rain, levels } = ctx;
    if (!tides.ok) {
      drawMap(canvas, img, streets, null, () => "dry");
      summary.textContent = "No flood estimate: without NOAA's tide predictions there is nothing to run the model on.";
      canvas.setAttribute("aria-label", "Key West road map, no live estimate available.");
      setRows([], pct);
      return;
    }
    const high = tides.value[tideIdx];
    const an = anomaly.ok ? anomaly.value : null;
    const r = rain.ok ? rainFor(rain.value, high.t) : undefined;
    const { values, members } = likelihoods(k, streets, high, an, r);
    const cls = (v) => (v >= LIKELY ? "high" : v >= POSSIBLE ? "mid" : v > 0 ? "low" : "dry");
    drawMap(canvas, img, streets, values, cls);
    const when = fmtTimeShort.format(high.t);
    const likely = byStreet(streets, values, LIKELY, k.MHHW_NAVD_FT), possible = byStreet(streets, values, POSSIBLE, k.MHHW_NAVD_FT);
    const shareLikely = values.filter((v) => v >= LIKELY).length / values.length;
    const list = (xs) => xs.slice(0, 5).map((s) => `${s.name} (low spot ${ft(s.minZ)})`).join(", ");
    let text;
    if (likely.length) text = `Low-lying streets likely to flood around the ${when} high tide: ${list(likely)}. Consider moving cars off them.`;
    else if (possible.length) text = `No street floods in most model runs around the ${when} high tide. Possible: ${list(possible)}.`;
    else text = `No road point reaches the 6-inch flood test in any of the ${members} model runs around the ${when} high tide.`;
    if (!an || !r) text += ` Incomplete inputs (${[!an && "no observed anomaly", !r && "no rain forecast"].filter(Boolean).join(", ")}): this likely understates the water.`;
    summary.textContent = text;
    canvas.setAttribute("aria-label", `Key West road map. ${pct(shareLikely)} of road points likely to flood around ${when}. ${likely.length} named streets likely, ${possible.length} possible.`);
    head.textContent = "Flood likelihood";
    setRows(possible, pct);
    setLegend([["high", "Likely: floods in 2/3 or more of runs"], ["mid", "Possible: 1/3 to 2/3"], ["low", "Some runs"], ["dry", "Dry in every run"]]);
    const c = high.v + (an ? an.mean : 0);
    const minor = (k.MHHW_NAVD_FT / FT_PER_M + levels.nws_minor) * FT_PER_M;
    setInputs([
      ["High tide", `${fmtTime.format(high.t)} ET, predicted ${ft(high.v)} NAVD88 (NOAA CO-OPS ${STATION})`],
      ["Observed anomaly", an ? `${an.mean >= 0 ? "+" : "−"}${Math.abs(an.mean).toFixed(2)} ± ${an.sd.toFixed(2)} ft, mean ± sd of observed − predicted over the last 24 h (${an.n} six-minute readings, latest ${fmtTimeShort.format(an.last)} ET)` : `unavailable (${anomaly.error})`],
      ["Expected water level", `${ft(c)} NAVD88; NWS minor flood stage at this gauge is ${ft(minor)}`],
      ["Rain, 24 h around the tide", r ? `${r.p24.toFixed(2)} in (NWS ${rain.value.office} gridded QPF, issued ${fmtTime.format(rain.value.updated)} ET); 3-h burst ${r.p3[0].toFixed(2)}–${r.p3[1].toFixed(2)} in` : `unavailable (${rain.ok ? "forecast does not cover this tide" : rain.error})`],
      ["Ensemble", `${members} runs: water level ±1 sd, groundwater 0.6–1.4 ft above MHHW, rain ×0.5 / ×1 / ×2, burst spread or concentrated`],
      ["Road points", `${streets.pieces.length.toLocaleString("en-US")}; ${pct(shareLikely)} likely to flood. The ${streets.pieces.filter((p) => p.z < k.MHHW_NAVD_FT).length} below normal high tide (bridge decks or lidar water returns) are left out of the street list`],
    ]);
  }

  function renderPlan() {
    const { k, streets, img } = ctx;
    const plan = k.planning;
    const sc = scenarioSel.value;
    const s = plan.scenarios[sc];
    const values = Float32Array.from(streets.pieces, (p) => interp(p.z, plan.z_ft, s.p));
    const cls = (v) => (v >= 0.5 ? "high" : v >= 0.1 ? "mid" : "dry");
    drawMap(canvas, img, streets, values, cls);
    const every2 = values.filter((v) => v >= 0.5).length / values.length;
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const top = byStreet(streets, values, 0.5, k.MHHW_NAVD_FT).sort((a, b) => b.n - a.n); // most exposed road length first
    summary.textContent = `${plan.year}, NOAA 2022 ${SCENARIO_LABEL[sc]} scenario (+${s.slr_ft_median.toFixed(2)} ft of sea-level rise after 2025): in an average year ${pct(mean)} of road points flood past 6 inches; ${pct(every2)} flood at least every other year. This is a yearly chance from the five-driver model, not a forecast for any night.`;
    canvas.setAttribute("aria-label", `Key West road map for ${plan.year}, ${SCENARIO_LABEL[sc]} scenario. ${pct(every2)} of road points flood at least every other year.`);
    head.textContent = `Yearly flood chance, ${plan.year}`;
    setRows(top, pct);
    setLegend([["high", "Floods at least every other year"], ["mid", "1 year in 2 to 1 in 10"], ["dry", "Less often"]]);
    setInputs([
      ["Model", "multidriver.py five drivers: peak water level, 24-h rain, 3-h burst, sea-level rise, groundwater"],
      ["Estimator", `${plan.method}; tide–rain τ = ${plan.tau_wp}`],
      ["Sea-level rise", `NOAA 2022 Technical Report projections for gauge ${STATION}, ${SCENARIO_LABEL[sc]}: +${s.slr_ft_median.toFixed(2)} ft median, 2025 to ${plan.year}`],
    ]);
  }

  function render() {
    if (!ctx) return;
    tidesBox.hidden = mode !== "live" || !ctx.tides.ok;
    scenarioBox.hidden = mode !== "plan";
    (mode === "live" ? renderLive : renderPlan)();
  }

  function buildTideChoices(highs) {
    tidesBox.querySelector(".tonight__choices").replaceChildren(...highs.map((h, i) => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "tonight-tide";
      input.value = String(i);
      input.checked = i === tideIdx;
      input.addEventListener("change", () => { tideIdx = i; render(); });
      label.append(input, ` ${fmtTime.format(h.t)}`);
      return label;
    }));
  }

  root.querySelectorAll('input[name="tonight-mode"]').forEach((el) => el.addEventListener("change", () => { mode = el.value; render(); }));
  scenarioSel.addEventListener("change", render);
  let lastW = 0;
  new ResizeObserver(() => { if (canvas.clientWidth !== lastW) { lastW = canvas.clientWidth; render(); } }).observe(canvas);

  async function load() {
    setStatus("Loading live NOAA tide and NWS rain data…");
    const now = Date.now();
    const settle = (p) => p.then((value) => ({ ok: true, value }), (e) => ({ ok: false, error: e.name === "AbortError" ? "timed out" : e.message }));
    const [k, streets, img, levels, tides, anomaly, rain] = await Promise.all([
      getJSON("assets/data/floodrule.json"), loadStreets(), loadImg(), window.FloodlineData.derived.then((d) => d.levels),
      settle(fetchTides(now)), settle(fetchAnomaly(now)), settle(fetchRain()),
    ]);
    ctx = { k, streets, img, levels, tides, anomaly, rain };
    const failed = [!tides.ok && `NOAA tide predictions (${tides.error})`, !anomaly.ok && `NOAA observed water level (${anomaly.error})`, !rain.ok && `NWS rain forecast (${rain.error})`].filter(Boolean);
    if (tides.ok) buildTideChoices(tides.value);
    setStatus(failed.length ? `Live data unavailable: ${failed.join("; ")}. Nothing is filled in for missing inputs. The 2050 planning view still works.` : `Live data loaded ${fmtTime.format(now)} ET.`, failed.length ? "warn" : "ok");
    render();
  }

  const io = new IntersectionObserver((es) => {
    if (!es.some((e) => e.isIntersecting)) return;
    io.disconnect();
    load().catch((e) => {
      console.error("Floodline: tonight panel failed", e);
      setStatus(`Could not load the road data or model constants, so no estimate is shown (${e.name}: ${e.message}).`, "warn");
    });
  }, { rootMargin: "50% 0px" });
  io.observe(root);
}

if (root) init();
