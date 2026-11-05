// "Watch the race": a live side-by-side of plain Monte Carlo and ideal
// quantum amplitude estimation (QAE) finding the same flood probability.
//
// Both sides are real simulations run in the browser, not a video:
// - Monte Carlo throws random storms (tide x rain) at a toy flood rule and
//   counts how many flood the street.
// - QAE is simulated exactly in the textbook picture: each Grover round
//   rotates the state by 2*theta, where a = sin^2(theta) is the flood
//   probability; a shot at depth m reads "flood" with p = sin^2((2m+1)theta).
//   Depths 0,1,2,4,...,32 with 100 shots each, combined by maximum likelihood
//   (MLAE), counted as shots * (2m+1) queries, the same schedule and query
//   accounting as results.json.
// The flood rule is a stand-in shape whose flood share (~0.64) matches the
// two-driver street model; the point is how fast each method closes in.
(function () {
  const root = document.getElementById("race");
  if (!root) return;
  const mcCanvas = root.querySelector(".race__mc");
  const qCanvas = root.querySelector(".race__qae");
  const chartCanvas = root.querySelector(".race__chart");
  const btn = root.querySelector(".race__play");
  const out = (k) => root.querySelector(`[data-race="${k}"]`);
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const css = getComputedStyle(document.documentElement);
  const C = {
    text: css.getPropertyValue("--text").trim() || "#eef2f6",
    muted: css.getPropertyValue("--text-muted").trim() || "#a9b4c2",
    accent: css.getPropertyValue("--accent").trim() || "#7cc7e8",
    amber: css.getPropertyValue("--amber").trim() || "#f5b13d",
    hair: css.getPropertyValue("--hairline").trim() || "#232c3a",
    surface: css.getPropertyValue("--chart-surface").trim() || "#0f1522",
  };

  // Toy flood rule on the unit square: x = tide, y = rain. High tide needs
  // little rain to flood; low tide needs a lot. Flood share is exact.
  const K = 0.83, P = 1.3;
  const boundary = (x) => K * Math.pow(1 - x, P);
  const floods = (x, y) => y > boundary(x);
  const TRUTH = 1 - K / (P + 1);
  const THETA = Math.asin(Math.sqrt(TRUTH));

  const DEPTHS = [0, 1, 2, 4, 8, 16, 32];
  const SHOTS = 100;
  const qCum = []; // cumulative QAE queries after each depth
  DEPTHS.reduce((s, m, i) => (qCum[i] = s + SHOTS * (2 * m + 1)), 0);
  const Q_END = qCum[qCum.length - 1]; // 13,300
  const MC_END = 250000;               // ~ what plain MC needs for +/-0.001
  const Q_START = 100;
  const DURATION_MS = 26000;           // whole race, log-time
  const QAE_RMSE = [[100, 0.0477], [400, 0.0205], [900, 0.0135], [1800, 0.00464], [3500, 0.00328], [6800, 0.00126], [13300, 0.00065]];
  const TARGET = 0.001;                // "decision-grade": within +/-0.001 of the truth
  const FORECAST_CYCLE_H = 6;          // NHC issues full advisories every 6 hours
  const queriesAt = (t) => Q_START * Math.pow(MC_END / Q_START, Math.min(1, t));

  // ---------- canvas helpers ----------
  function fit(canvas) {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  }
  const fmt = (n) => Math.round(n).toLocaleString("en-US");
  const rng = Math.random;

  // ---------- state ----------
  let mc, q, history, running = false, raf = 0, t0 = 0, tNow = 0;
  function reset() {
    mc = { n: 0, hits: 0, dots: [] };
    q = { depthIdx: -1, hits: [], est: null, shotAnim: 0 };
    history = { mc: [], q: [] };
    tNow = 0;
  }

  // ---------- Monte Carlo ----------
  function mcAdvance(target) {
    const before = mc.n;
    while (mc.n < target) {
      const x = rng(), y = rng();
      const f = floods(x, y);
      mc.n++; if (f) mc.hits++;
      // Keep a bounded, evenly thinned set of dots to draw.
      if (mc.dots.length < 2600 || rng() < 2600 / mc.n) {
        if (mc.dots.length >= 2600) mc.dots[(rng() * mc.dots.length) | 0] = [x, y, f];
        else mc.dots.push([x, y, f]);
      }
    }
    if (mc.n > before) history.mc.push([mc.n, Math.abs(mc.hits / mc.n - TRUTH)]);
  }

  // ---------- QAE ----------
  function binomial(n, p) {
    let k = 0;
    for (let i = 0; i < n; i++) if (rng() < p) k++;
    return k;
  }
  function mlae(upto) {
    const ll = (th) => {
      let s = 0;
      for (let i = 0; i <= upto; i++) {
        const ang = (2 * DEPTHS[i] + 1) * th;
        const p = Math.min(1 - 1e-12, Math.max(1e-12, Math.sin(ang) ** 2));
        s += q.hits[i] * Math.log(p) + (SHOTS - q.hits[i]) * Math.log(1 - p);
      }
      return s;
    };
    const G = 30000, lo = 1e-6, hi = Math.PI / 2 - 1e-6;
    let best = lo, bestV = -Infinity;
    for (let j = 0; j <= G; j++) {
      const th = lo + ((hi - lo) * j) / G, v = ll(th);
      if (v > bestV) { bestV = v; best = th; }
    }
    const step = (hi - lo) / G;
    for (let j = -100; j <= 100; j++) {
      const th = best + (step * j) / 100, v = ll(th);
      if (v > bestV) { bestV = v; best = th; }
    }
    return Math.sin(best) ** 2;
  }
  function qAdvance(queries) {
    while (q.depthIdx + 1 < DEPTHS.length && queries >= qCum[q.depthIdx + 1]) {
      const i = ++q.depthIdx, m = DEPTHS[i];
      q.hits[i] = binomial(SHOTS, Math.sin((2 * m + 1) * THETA) ** 2);
      q.est = mlae(i);
      q.shotAnim = 1;
      history.q.push([qCum[i], Math.abs(q.est - TRUTH)]);
    }
  }

  // ---------- drawing ----------
  function drawMC() {
    const { ctx, w, h } = fit(mcCanvas);
    const pad = 26, s = Math.min(w - pad - 8, h - pad - 8), ox = pad, oy = 6;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = C.surface; ctx.fillRect(ox, oy, s, s);
    // flood region
    ctx.beginPath(); ctx.moveTo(ox, oy);
    for (let i = 0; i <= 60; i++) { const x = i / 60; ctx.lineTo(ox + x * s, oy + (1 - boundary(x)) * s); }
    ctx.lineTo(ox + s, oy); ctx.closePath();
    ctx.globalAlpha = 0.12; ctx.fillStyle = C.amber; ctx.fill(); ctx.globalAlpha = 1;
    ctx.beginPath();
    for (let i = 0; i <= 60; i++) { const x = i / 60, X = ox + x * s, Y = oy + (1 - boundary(x)) * s; i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); }
    ctx.strokeStyle = C.amber; ctx.lineWidth = 1.2; ctx.setLineDash([4, 3]); ctx.stroke(); ctx.setLineDash([]);
    // dots
    const r = mc.dots.length > 1200 ? 1.3 : 2;
    for (const [x, y, f] of mc.dots) {
      ctx.fillStyle = f ? C.amber : C.accent;
      ctx.globalAlpha = 0.8;
      ctx.fillRect(ox + x * s - r / 2, oy + (1 - y) * s - r / 2, r, r);
    }
    ctx.globalAlpha = 1;
    // labels
    ctx.fillStyle = C.muted; ctx.font = "11px 'IBM Plex Sans', system-ui, sans-serif";
    ctx.textAlign = "center"; ctx.fillText("tide →", ox + s / 2, oy + s + 16);
    ctx.save(); ctx.translate(ox - 10, oy + s / 2); ctx.rotate(-Math.PI / 2); ctx.fillText("rain →", 0, 0); ctx.restore();
    ctx.textAlign = "right"; ctx.fillStyle = C.amber; ctx.fillText("street floods", ox + s - 6, oy + 16);
    ctx.textAlign = "left"; ctx.fillStyle = C.accent; ctx.fillText("stays dry", ox + 6, oy + s - 8);
  }

  function drawQ() {
    const { ctx, w, h } = fit(qCanvas);
    ctx.clearRect(0, 0, w, h);
    const i = q.depthIdx;
    // Rotation picture: dry axis horizontal, flood axis vertical.
    const R = Math.min(h - 40, w * 0.42) / 1.05, cx = 16, cy = h - 22;
    ctx.strokeStyle = C.hair; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(cx, cy, R, -Math.PI / 2, 0); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + R + 6, cy); ctx.moveTo(cx, cy); ctx.lineTo(cx, cy - R - 6); ctx.stroke();
    ctx.font = "11px 'IBM Plex Sans', system-ui, sans-serif";
    ctx.fillStyle = C.accent; ctx.textAlign = "right"; ctx.fillText("dry", cx + R + 4, cy + 14);
    ctx.fillStyle = C.amber; ctx.textAlign = "left"; ctx.fillText("flood", cx + 6, cy - R - 2);
    // Arrow at angle (2m+1)theta, folded into the first quadrant as measured.
    const m = i >= 0 ? DEPTHS[i] : 0;
    const raw = (2 * m + 1) * THETA;
    const pFlood = Math.sin(raw) ** 2;
    const ang = Math.asin(Math.sqrt(pFlood));
    const spin = q.shotAnim > 0 ? (1 - q.shotAnim) : 1; // sweep in when a depth starts
    const a = ang * (0.15 + 0.85 * spin);
    ctx.strokeStyle = C.text; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + R * Math.cos(a), cy - R * Math.sin(a)); ctx.stroke();
    ctx.fillStyle = C.text; ctx.beginPath(); ctx.arc(cx + R * Math.cos(a), cy - R * Math.sin(a), 3.5, 0, 7); ctx.fill();
    ctx.fillStyle = C.muted; ctx.textAlign = "left";
    ctx.fillText(i >= 0 ? `Grover rounds: ${m}` : "ready", cx + 4, 14);

    // Per-depth bars: measured flood share vs what the current estimate predicts.
    const bx = cx + R + 36, bw = w - bx - 8, top = 24, bh = h - top - 22;
    if (bw < 60) return;
    const n = DEPTHS.length, gap = 4, colW = (bw - gap * (n - 1)) / n;
    ctx.strokeStyle = C.hair; ctx.beginPath(); ctx.moveTo(bx, top + bh); ctx.lineTo(bx + bw, top + bh); ctx.stroke();
    const thEst = q.est != null ? Math.asin(Math.sqrt(q.est)) : null;
    for (let k = 0; k < n; k++) {
      const x = bx + k * (colW + gap);
      if (k <= i) {
        const f = q.hits[k] / SHOTS;
        ctx.fillStyle = C.amber; ctx.globalAlpha = k === i ? 1 : 0.55;
        ctx.fillRect(x, top + bh * (1 - f), colW, bh * f);
        ctx.globalAlpha = 1;
        if (thEst != null) {
          const pred = Math.sin((2 * DEPTHS[k] + 1) * thEst) ** 2;
          ctx.strokeStyle = C.text; ctx.lineWidth = 1.5;
          ctx.beginPath(); ctx.moveTo(x - 1, top + bh * (1 - pred)); ctx.lineTo(x + colW + 1, top + bh * (1 - pred)); ctx.stroke();
        }
      } else {
        ctx.strokeStyle = C.hair; ctx.setLineDash([2, 3]); ctx.strokeRect(x + 0.5, top + 0.5, colW - 1, bh - 1); ctx.setLineDash([]);
      }
      ctx.fillStyle = C.muted; ctx.textAlign = "center"; ctx.fillText(String(DEPTHS[k]), x + colW / 2, top + bh + 14);
    }
    ctx.textAlign = "left"; ctx.fillStyle = C.muted;
    ctx.fillText("share of shots reading “flood”, per round count", bx, 14);
  }

  function drawChart() {
    const { ctx, w, h } = fit(chartCanvas);
    ctx.clearRect(0, 0, w, h);
    const L = 48, Rm = 12, T = 10, B = 30, pw = w - L - Rm, ph = h - T - B;
    const x0 = Math.log10(Q_START), x1 = Math.log10(MC_END), y0 = -4.3, y1 = -0.7;
    const X = (n) => L + ((Math.log10(n) - x0) / (x1 - x0)) * pw;
    const Y = (e) => T + (1 - (Math.log10(Math.max(e, 1e-6)) - y0) / (y1 - y0)) * ph;
    ctx.font = "11px 'IBM Plex Sans', system-ui, sans-serif";
    ctx.strokeStyle = C.hair; ctx.lineWidth = 1; ctx.fillStyle = C.muted;
    for (const n of [100, 1000, 10000, 100000]) {
      ctx.beginPath(); ctx.moveTo(X(n), T); ctx.lineTo(X(n), T + ph); ctx.stroke();
      ctx.textAlign = "center"; ctx.fillText(fmt(n), X(n), T + ph + 14);
    }
    for (const e of [1e-4, 1e-3, 1e-2, 1e-1]) {
      ctx.beginPath(); ctx.moveTo(L, Y(e)); ctx.lineTo(L + pw, Y(e)); ctx.stroke();
      ctx.textAlign = "right"; ctx.fillText(e >= 0.01 ? String(e) : e.toExponential(0), L - 6, Y(e) + 4);
    }
    ctx.textAlign = "center"; ctx.fillText("tries (queries), log scale", L + pw / 2, h - 2);
    ctx.save(); ctx.translate(11, T + ph / 2); ctx.rotate(-Math.PI / 2); ctx.fillText("how far off", 0, 0); ctx.restore();
    // target line
    ctx.strokeStyle = C.muted; ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(L, Y(1e-3)); ctx.lineTo(L + pw, Y(1e-3)); ctx.stroke(); ctx.setLineDash([]);
    ctx.textAlign = "left"; ctx.fillStyle = C.muted; ctx.fillText("target: within 0.001", L + 6, Y(1e-3) - 5);
    // expected trends (faint): MC's textbook sqrt(a(1-a)/N), and the RMSE
    // results.json measured for ideal QAE on the two-driver street (500 trials).
    ctx.lineWidth = 6; ctx.globalAlpha = 0.18;
    ctx.strokeStyle = C.accent; ctx.beginPath();
    ctx.moveTo(X(Q_START), Y(Math.sqrt(TRUTH * (1 - TRUTH) / Q_START))); ctx.lineTo(X(MC_END), Y(Math.sqrt(TRUTH * (1 - TRUTH) / MC_END))); ctx.stroke();
    ctx.strokeStyle = C.amber; ctx.beginPath();
    QAE_RMSE.forEach(([n, e], k) => (k ? ctx.lineTo(X(n), Y(e)) : ctx.moveTo(X(n), Y(e))));
    ctx.stroke();
    ctx.globalAlpha = 1; ctx.lineWidth = 2;
    // live traces
    const trace = (pts, col) => {
      if (!pts.length) return;
      ctx.strokeStyle = col; ctx.beginPath();
      pts.forEach(([n, e], k) => (k ? ctx.lineTo(X(n), Y(e)) : ctx.moveTo(X(n), Y(e))));
      ctx.stroke();
      const [n, e] = pts[pts.length - 1];
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(X(n), Y(e), 3.5, 0, 7); ctx.fill();
    };
    // Thin the MC trace for drawing.
    const step = Math.max(1, Math.floor(history.mc.length / 400));
    trace(history.mc.filter((_, k) => k % step === 0 || k === history.mc.length - 1), C.accent);
    trace(history.q, C.amber);
  }

  function updateText(queries) {
    out("mc-n").textContent = fmt(mc.n);
    out("mc-est").textContent = mc.n ? (mc.hits / mc.n).toFixed(4) : "–";
    out("mc-err").textContent = mc.n ? `±${Math.abs(mc.hits / mc.n - TRUTH).toFixed(4)}` : "–";
    const qn = q.depthIdx >= 0 ? qCum[q.depthIdx] : 0;
    out("q-n").textContent = fmt(qn);
    out("q-est").textContent = q.est != null ? q.est.toFixed(4) : "–";
    out("q-err").textContent = q.est != null ? `±${Math.abs(q.est - TRUTH).toFixed(4)}` : "–";
    out("q-state").textContent = q.depthIdx === DEPTHS.length - 1 ? "finished" : queries > Q_START ? "running" : "";
    out("mc-state").textContent = mc.n >= MC_END ? "finished" : mc.n ? "running" : "";
    out("mc-lock").innerHTML = lockText(history.mc);
    out("q-lock").innerHTML = lockText(history.q);
  }

  // Tries at which a method got within TARGET and stayed there through what it
  // has run so far (null if it isn't within TARGET right now).
  function lockedAt(pts) {
    if (!pts.length || pts[pts.length - 1][1] > TARGET) return null;
    let k = pts.length - 1;
    while (k > 0 && pts[k - 1][1] <= TARGET) k--;
    return pts[k][0];
  }
  function lockText(pts) {
    if (!pts.length) return "&nbsp;";
    const at = lockedAt(pts);
    return at != null
      ? `<span class="race__lock-yes">✓ within ±0.001</span> since ${fmt(at)} tries`
      : "still outside ±0.001";
  }

  // ---------- end-of-run verdict ----------
  const verdict = root.querySelector(".race__verdict");
  const perTry = root.querySelector(".race__per-try");
  function duration(sec) {
    if (sec < 90) return `${Math.round(sec)} seconds`;
    if (sec < 5400) return `${Math.round(sec / 60)} minutes`;
    if (sec < 72 * 3600) return `${(sec / 3600).toFixed(sec < 36000 ? 1 : 0)} hours`;
    return `${Math.round(sec / 86400)} days`;
  }
  let lastResult = null;
  function showVerdict() {
    if (!verdict) return;
    const qAt = lockedAt(history.q), mAt = lockedAt(history.mc);
    lastResult = { qAt, mAt };
    let head;
    if (qAt != null && mAt != null) {
      head = `Quantum locked in the answer (within ±0.001) after <strong>${fmt(qAt)}</strong> tries. Monte Carlo needed <strong>${fmt(mAt)}</strong>: <strong>${Math.round(mAt / qAt)}× more</strong>.`;
    } else if (qAt != null) {
      head = `Quantum locked in the answer (within ±0.001) after <strong>${fmt(qAt)}</strong> tries. Monte Carlo <strong>still wasn’t there after ${fmt(MC_END)}</strong>: more than <strong>${Math.floor(MC_END / qAt)}× more</strong>.`;
    } else {
      head = `This run, quantum finished its ${fmt(Q_END)} tries just outside ±0.001 (off by ${history.q[history.q.length - 1][1].toFixed(4)}). That happens in roughly 1 run in 8, so run it again.` +
        (mAt != null ? ` Monte Carlo got there after ${fmt(mAt)} tries.` : ` Monte Carlo wasn’t there after ${fmt(MC_END)} either.`);
    }
    out("v-head").innerHTML = head;
    updateTimes();
    verdict.hidden = false;
  }
  function updateTimes() {
    if (!lastResult) return;
    const sec = Number(perTry.value);
    const qn = lastResult.qAt ?? Q_END, mn = lastResult.mAt ?? MC_END;
    const cyc = FORECAST_CYCLE_H * 3600;
    const fits = (t) => (t <= cyc
      ? '<span class="race__lock-yes">fits in one 6-hour forecast cycle</span>'
      : "misses the 6-hour forecast cycle");
    out("v-mc-time").innerHTML = `${lastResult.mAt == null ? "more than " : ""}${duration(mn * sec)} · ${fits(mn * sec)}`;
    out("v-q-time").innerHTML = `${lastResult.qAt == null ? "about " : ""}${duration(qn * sec)} · ${fits(qn * sec)}`;
  }
  perTry?.addEventListener("change", updateTimes);

  function draw(queries) { drawMC(); drawQ(); drawChart(); updateText(queries); }

  function frame(now) {
    if (!running) return;
    tNow = (now - t0) / DURATION_MS;
    const queries = queriesAt(tNow);
    mcAdvance(Math.min(MC_END, Math.floor(queries)));
    qAdvance(queries);
    if (q.shotAnim > 0) q.shotAnim = Math.max(0, q.shotAnim - 0.05);
    draw(queries);
    if (tNow >= 1) { running = false; btn.textContent = "↻ Run again"; btn.setAttribute("aria-pressed", "false"); showVerdict(); return; }
    raf = requestAnimationFrame(frame);
  }

  function play() {
    cancelAnimationFrame(raf);
    reset();
    if (verdict) verdict.hidden = true;
    if (reduceMotion) {
      // No animation: jump straight to the finished race.
      for (let t = 0; t <= 1.0001; t += 0.004) { const n = queriesAt(t); mcAdvance(Math.min(MC_END, Math.floor(n))); qAdvance(n); }
      q.shotAnim = 0; draw(MC_END);
      btn.textContent = "↻ Run again";
      showVerdict();
      return;
    }
    running = true;
    btn.textContent = "■ Stop";
    btn.setAttribute("aria-pressed", "true");
    t0 = performance.now();
    raf = requestAnimationFrame(frame);
  }
  function stop() {
    running = false; cancelAnimationFrame(raf);
    btn.textContent = "▶ Play the race"; btn.setAttribute("aria-pressed", "false");
  }

  out("truth").textContent = TRUTH.toFixed(4);
  reset();
  draw(0);
  btn.addEventListener("click", () => (running ? stop() : play()));
  window.addEventListener("resize", () => draw(queriesAt(tNow)));

  // Start on its own the first time it's mostly on screen (the tour lands here).
  let autoplayed = false;
  new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting && !autoplayed && !running) { autoplayed = true; play(); }
    }
  }, { threshold: 0.3 }).observe(root);

  window.FloodlineRace = { play, stop }; // manual control / QA
})();
