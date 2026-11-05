// Results charts and tables, drawn from FloodlineData (data.js). One small SVG
// line-chart helper serves every chart: log axes, optional 95% CI bars, a legend, sparing end labels,
// a crosshair + tooltip on hover and keyboard focus. The tables beside each
// chart carry every value, so the tooltip only ever enhances.
(function () {
  const SVG = "http://www.w3.org/2000/svg";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Light-surface steps for the nautical paper panel
  // #faf6ec: every color >= 3:1 against it; ordinal blue stays monotone in lightness.
  const C = { qae: "#2a6fc4", mc: "#c2491b", qmc: "#13805a" };
  const EPS_RAMP = ["#5f8bc0", "#2a6fc4", "#143f70"];

  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };
  const sup = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
  const pow10 = (e) => (e === 0 ? "1" : e === 1 ? "10" : "10" + String(e).split("").map((c) => sup[c]).join(""));
  const compact = (n) => (n >= 1e6 ? +(n / 1e6).toPrecision(3) + "M" : n >= 1e3 ? +(n / 1e3).toPrecision(3) + "k" : String(+n.toPrecision(3)));

  function logTicks(lo, hi) {
    const out = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
      const v = 10 ** e;
      if (v >= lo * 0.999 && v <= hi * 1.001) out.push({ v, label: pow10(e) });
    }
    return out;
  }

  function lineChart(root, cfg) {
    if (!root) return null; // chart archived off the page
    const legend = document.createElement("ul");
    legend.className = "chart__legend";
    for (const s of cfg.series) {
      const li = document.createElement("li");
      const key = document.createElement("span");
      key.className = "chart__key";
      key.style.background = s.color;
      if (s.line === false) key.classList.add("chart__key--dot");
      li.append(key, document.createTextNode(s.name));
      legend.appendChild(li);
    }
    // A legend key for the tie line keeps its label clear of points near 1×.
    if (cfg.ref?.legend) {
      const li = document.createElement("li");
      const key = document.createElement("span");
      key.className = "chart__key chart__key--ref";
      li.append(key, document.createTextNode(cfg.ref.legend));
      legend.appendChild(li);
    }
    const plot = document.createElement("div");
    plot.className = "chart__plot";
    plot.tabIndex = 0;
    const tip = document.createElement("div");
    tip.className = "chart__tip";
    tip.hidden = true;
    root.replaceChildren(legend, plot);
    plot.appendChild(tip);

    const xs = [...new Set(cfg.series.flatMap((s) => s.points.map((p) => p.x)))].sort((a, b) => a - b);
    const ys = cfg.series.flatMap((s) => s.points.flatMap((p) => [p.y, p.lo, p.hi].filter((v) => v !== undefined))).concat(cfg.ref ? [cfg.ref.y] : []);
    // yDomain switches the y axis from log to linear over a fixed range.
    const [yLo, yHi] = cfg.yDomain || [Math.min(...ys) / 1.4, Math.max(...ys) * 1.4];
    let paths = [], svg, X, Y, idx = -1;

    function draw() {
      const W = Math.max(280, plot.clientWidth);
      const H = Math.round(Math.min(420, Math.max(260, W * 0.52)));
      const narrow = W < 520;
      const pad = { l: narrow ? 44 : 56, r: narrow ? 58 : 110, t: 14, b: 44 };
      const x0 = cfg.xLog ? Math.log10(xs[0]) : xs[0], x1 = cfg.xLog ? Math.log10(xs[xs.length - 1]) : xs[xs.length - 1];
      X = (v) => pad.l + (((cfg.xLog ? Math.log10(v) : v) - x0) / (x1 - x0)) * (W - pad.l - pad.r);
      const ty = cfg.yDomain ? (v) => v : Math.log10;
      Y = (v) => pad.t + (1 - (ty(v) - ty(yLo)) / (ty(yHi) - ty(yLo))) * (H - pad.t - pad.b);

      svg?.remove();
      svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": cfg.ariaLabel });
      plot.prepend(svg);
      const grid = el("g", { class: "chart__grid" }, svg);
      for (const t of cfg.yTicks ? cfg.yTicks.filter((v) => v >= yLo && v <= yHi).map((v) => ({ v })) : logTicks(yLo, yHi)) {
        el("line", { x1: pad.l, x2: W - pad.r, y1: Y(t.v), y2: Y(t.v) }, grid);
        el("text", { x: pad.l - 8, y: Y(t.v) + 4, "text-anchor": "end", class: "chart__tick" }, grid).textContent = cfg.yTick ? cfg.yTick(t.v) : t.label;
      }
      const xt = cfg.xLog ? logTicks(xs[0], xs[xs.length - 1]).map((t) => ({ v: t.v, label: compact(t.v) })) : xs.map((v) => ({ v, label: String(v) }));
      for (const t of xt) el("text", { x: X(t.v), y: H - pad.b + 18, "text-anchor": "middle", class: "chart__tick" }, grid).textContent = t.label;
      el("line", { x1: pad.l, x2: W - pad.r, y1: H - pad.b, y2: H - pad.b, class: "chart__axis" }, svg);
      el("text", { x: pad.l + (W - pad.l - pad.r) / 2, y: H - 6, "text-anchor": "middle", class: "chart__label" }, svg).textContent = cfg.xLabel;
      // Phones: the figure title names the y measure; a rotated label would collide with the ticks.
      if (!narrow) el("text", { x: 12, y: pad.t + (H - pad.t - pad.b) / 2, "text-anchor": "middle", class: "chart__label", transform: `rotate(-90 12 ${pad.t + (H - pad.t - pad.b) / 2})` }, svg).textContent = cfg.yLabel;

      if (cfg.band) {
        const bx0 = X(cfg.band.x0), bx1 = X(cfg.band.x1);
        el("rect", { x: bx0, y: pad.t, width: bx1 - bx0, height: H - pad.t - pad.b, class: "chart__band" }, svg);
        el("text", { x: (bx0 + bx1) / 2, y: H - pad.b - 8, "text-anchor": "middle", class: "chart__reflabel" }, svg).textContent = cfg.band.label;
      }

      if (cfg.ref) {
        el("line", { x1: pad.l, x2: W - pad.r, y1: Y(cfg.ref.y), y2: Y(cfg.ref.y), class: "chart__ref" }, svg);
        const rx = cfg.ref.left ? pad.l + 6 : W - pad.r - 4, anchor = cfg.ref.left ? "start" : "end";
        if (cfg.ref.above) el("text", { x: rx, y: Y(cfg.ref.y) - 6, "text-anchor": anchor, class: "chart__reflabel" }, svg).textContent = cfg.ref.above;
        if (cfg.ref.below) el("text", { x: rx, y: Y(cfg.ref.y) + 15, "text-anchor": anchor, class: "chart__reflabel" }, svg).textContent = cfg.ref.below;
      }

      paths = [];
      const ends = [];
      for (const s of cfg.series) {
        const g = el("g", {}, svg);
        const solid = s.points.filter((p) => !p.hollow);
        let prev = null;
        // dx nudges a series sideways so CI bars at the same x don't overlap.
        const sx = (p) => X(p.x) + (s.dx || 0);
        const d = (pts) => pts.map((p, i) => `${i ? "L" : "M"}${sx(p).toFixed(1)},${Y(p.y).toFixed(1)}`).join("");
        // curve: a dense path drawn instead of point-to-point segments (a closed-form law).
        if (s.line !== false) paths.push(el("path", { d: d(s.curve || solid), stroke: s.color, class: "chart__line" }, g));
        const firstHollow = s.points.findIndex((p) => p.hollow);
        if (firstHollow > 0) el("path", { d: d(s.points.slice(firstHollow - 1)), stroke: s.color, class: "chart__line chart__line--extrap" }, g);
        for (const p of s.dots === false ? [] : s.points) {
          if (p.lo !== undefined) {
            el("line", { x1: sx(p), x2: sx(p), y1: Y(p.lo), y2: Y(p.hi), stroke: s.color, class: "chart__ci" }, g);
            for (const v of [p.lo, p.hi]) el("line", { x1: sx(p) - 4, x2: sx(p) + 4, y1: Y(v), y2: Y(v), stroke: s.color, class: "chart__ci" }, g);
          }
          el("circle", { cx: sx(p), cy: Y(p.y), r: p.big ? 6 : 4, fill: p.hollow ? "var(--chart-surface)" : s.color, stroke: p.hollow ? s.color : "var(--chart-surface)", "stroke-width": 2, class: "chart__dot" }, g);
          // Value labels sit past the CI end so they never cover a whisker; a label that
          // would collide with its neighbour's steps one line further out.
          if (s.label) {
            const text = p.text || cfg.yFmt(p.y);
            const w = text.length * 6.8;
            const above = s.label === "above";
            const step = prev && !prev.step && Math.abs(sx(p) - prev.x) < (w + prev.w) / 2 + 3 ? 13 : 0;
            prev = { x: sx(p), w, step };
            const ly = above ? Y(p.hi ?? p.y) - 7 - step : Y(p.lo ?? p.y) + 15 + step;
            const edge = sx(p) - w / 2 < pad.l;
            const t = el("text", { x: edge ? sx(p) - 3 : sx(p), y: ly, "text-anchor": p.big ? "end" : edge ? "start" : "middle", class: p.big ? "chart__val chart__val--hero" : "chart__val" }, g);
            t.textContent = text;
          }
        }
        const last = s.points[s.points.length - 1];
        ends.push({ y: Y(last.y), x: sx(last), name: s.short || s.name });
      }
      // End labels only when they sit clear of each other; otherwise the legend carries identity.
      ends.sort((a, b) => a.y - b.y);
      if (ends.every((e, i) => i === 0 || e.y - ends[i - 1].y > 16)) {
        for (const e of ends) el("text", { x: e.x + 9, y: e.y + 4, class: "chart__end" }, svg).textContent = e.name;
      }
      el("line", { class: "chart__cross", y1: pad.t, y2: H - pad.b, x1: -10, x2: -10 }, svg);
      if (idx >= 0) show(idx);
    }

    function show(i) {
      idx = i;
      const xv = xs[i];
      const cross = svg.querySelector(".chart__cross");
      cross.setAttribute("x1", X(xv));
      cross.setAttribute("x2", X(xv));
      tip.replaceChildren();
      const head = document.createElement("div");
      head.className = "chart__tip-head";
      head.textContent = cfg.xName(xv);
      tip.appendChild(head);
      for (const s of cfg.series) {
        const p = s.points.find((q) => q.x === xv);
        if (!p) continue;
        const row = document.createElement("div");
        row.className = "chart__tip-row";
        const key = document.createElement("span");
        key.className = "chart__tip-key";
        key.style.background = s.color;
        const val = document.createElement("strong");
        val.textContent = cfg.yFmt(p.y) + (p.lo !== undefined ? ` [${cfg.yFmt(p.lo)}, ${cfg.yFmt(p.hi)}]` : "") + (p.hollow ? " (extrap.)" : "");
        const name = document.createElement("span");
        name.textContent = s.name;
        row.append(key, val, name);
        tip.appendChild(row);
      }
      tip.hidden = false;
      plot.classList.add("is-hover");
      const left = X(xv);
      tip.style.left = `${Math.min(left + 12, plot.clientWidth - tip.offsetWidth - 4)}px`;
      if (left + 12 + tip.offsetWidth > plot.clientWidth) tip.style.left = `${Math.max(4, left - tip.offsetWidth - 12)}px`;
    }
    function hide() {
      idx = -1;
      tip.hidden = true;
      plot.classList.remove("is-hover");
      svg?.querySelector(".chart__cross")?.setAttribute("x1", -10);
      svg?.querySelector(".chart__cross")?.setAttribute("x2", -10);
    }
    function nearest(clientX) {
      const px = clientX - plot.getBoundingClientRect().left;
      let best = 0;
      xs.forEach((v, i) => { if (Math.abs(X(v) - px) < Math.abs(X(xs[best]) - px)) best = i; });
      return best;
    }
    plot.addEventListener("pointermove", (e) => show(nearest(e.clientX)));
    // A touch tap fires pointerleave on lift and focuses afterwards; keep the tapped point.
    plot.addEventListener("pointerdown", (e) => show(nearest(e.clientX)));
    plot.addEventListener("pointerleave", (e) => { if (e.pointerType !== "touch") hide(); });
    plot.addEventListener("focus", () => show(idx >= 0 ? idx : xs.length - 1));
    plot.addEventListener("blur", hide);
    plot.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      show(Math.max(0, Math.min(xs.length - 1, (idx < 0 ? 0 : idx) + (e.key === "ArrowRight" ? 1 : -1))));
    });
    plot.setAttribute("aria-label", `${cfg.ariaLabel} Use left and right arrow keys to read values.`);
    plot.setAttribute("role", "group");

    let lastW = 0;
    new ResizeObserver(() => { if (plot.clientWidth !== lastW) { lastW = plot.clientWidth; draw(); } }).observe(plot);
    draw();

    return {
      replay() {
        if (reduceMotion) { window.dispatchEvent(new CustomEvent("floodline:chart-done")); return; }
        for (const p of paths) {
          const len = p.getTotalLength();
          p.style.transition = "none";
          p.style.strokeDasharray = `${len}`;
          p.style.strokeDashoffset = `${len}`;
          p.getBoundingClientRect();
          p.style.transition = "stroke-dashoffset 1.6s cubic-bezier(.3,.6,.3,1)";
          p.style.strokeDashoffset = "0";
        }
        setTimeout(() => window.dispatchEvent(new CustomEvent("floodline:chart-done")), 1650);
      },
    };
  }

  // Grouped "× fewer queries" bars on a log axis whose floor is the 1× tie line,
  // so bar length is the size of the quantum edge. Hollow bars are extrapolated.
  function barChart(root, cfg) {
    if (!root) return null;
    const nodes = [];
    if (cfg.series.length > 1) {
      const legend = document.createElement("ul");
      legend.className = "chart__legend";
      for (const s of cfg.series) {
        const li = document.createElement("li");
        const key = document.createElement("span");
        key.className = "chart__key chart__key--bar";
        key.style.background = s.color;
        li.append(key, document.createTextNode(s.name));
        legend.appendChild(li);
      }
      nodes.push(legend);
    }
    const plot = document.createElement("div");
    plot.className = "chart__plot";
    nodes.push(plot);
    root.replaceChildren(...nodes);

    const his = cfg.series.flatMap((s) => s.values.map((v) => v.hi ?? v.y));
    const yHi = Math.max(...his) * 1.6;
    let svg;
    function draw() {
      const W = Math.max(280, plot.clientWidth);
      const H = cfg.height || Math.round(Math.min(320, Math.max(220, W * 0.4)));
      const pad = { l: 44, r: 30, t: 12, b: 30 };
      const Y = (v) => pad.t + (1 - Math.log10(v) / Math.log10(yHi)) * (H - pad.t - pad.b);
      svg?.remove();
      svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": cfg.ariaLabel });
      plot.appendChild(svg);
      const grid = el("g", { class: "chart__grid" }, svg);
      for (const v of cfg.yTicks.filter((v) => v > 1 && v < yHi)) {
        el("line", { x1: pad.l, x2: W - pad.r, y1: Y(v), y2: Y(v) }, grid);
        el("text", { x: pad.l - 8, y: Y(v) + 4, "text-anchor": "end", class: "chart__tick" }, grid).textContent = `${v}×`;
      }
      const gw = (W - pad.l - pad.r) / cfg.groups.length;
      const n = cfg.series.length, gap = 2;
      const bw = Math.min(56, (gw * 0.7 - gap * (n - 1)) / n);
      cfg.groups.forEach((gName, gi) => {
        const cx = pad.l + gw * (gi + 0.5);
        el("text", { x: cx, y: H - pad.b + 18, "text-anchor": "middle", class: "chart__tick" }, svg).textContent = gName;
        cfg.series.forEach((s, si) => {
          const v = s.values[gi];
          const x = cx - (n * bw + gap * (n - 1)) / 2 + si * (bw + gap);
          const top = Y(v.y), base = Y(1), r = Math.min(4, bw / 2, base - top);
          const bar = el("path", {
            d: `M${x},${base}V${top + r}Q${x},${top} ${x + r},${top}H${x + bw - r}Q${x + bw},${top} ${x + bw},${top + r}V${base}Z`,
            fill: v.hollow ? "none" : s.color, stroke: s.color, "stroke-width": v.hollow ? 2 : 0,
            class: v.hollow ? "chart__bar chart__bar--extrap" : "chart__bar",
          }, svg);
          el("title", {}, bar).textContent = `${s.name}, ${gName}: ${v.text}${v.hollow ? " (extrapolated)" : ""}`;
          const mx = x + bw / 2;
          if (v.lo !== undefined) {
            el("line", { x1: mx, x2: mx, y1: Y(v.lo), y2: Y(v.hi), class: "chart__ci chart__ci--bar" }, svg);
            for (const e of [v.lo, v.hi]) el("line", { x1: mx - 4, x2: mx + 4, y1: Y(e), y2: Y(e), class: "chart__ci chart__ci--bar" }, svg);
          }
          el("text", { x: mx, y: Y(v.hi ?? v.y) - 7, "text-anchor": "middle", class: "chart__val" }, svg).textContent = v.text;
        });
      });
      el("line", { x1: pad.l, x2: W - pad.r, y1: Y(1), y2: Y(1), class: "chart__ref" }, svg);
      el("text", { x: pad.l - 8, y: Y(1) + 4, "text-anchor": "end", class: "chart__tick" }, svg).textContent = "1×";
      el("text", { x: W - pad.r + 4, y: Y(1) + 4, class: "chart__reflabel" }, svg).textContent = "tie";
    }
    let lastW = 0;
    new ResizeObserver(() => { if (plot.clientWidth !== lastW) { lastW = plot.clientWidth; draw(); } }).observe(plot);
    draw();
  }

  const ratio = (v) => (v >= 100 ? Math.round(v) : v >= 10 ? +v.toPrecision(3) : v >= 1 ? +v.toFixed(1) : +v.toPrecision(2)) + "×";
  const sci = (v) => v.toExponential(1).replace("e-", "e−");
  const fmtQ = (n) => compact(n);

  const say = (id, msg) => { const el = document.getElementById(id); if (el) el.textContent = msg; };

  function cells(tr, values, header) {
    values.forEach((v, i) => {
      const c = document.createElement(i === 0 && header ? "th" : "td");
      if (i === 0 && header) c.scope = "row";
      c.textContent = v;
      tr.appendChild(c);
    });
  }

  FloodlineData.results.then((d) => {
    if (!document.getElementById("convergence-chart")) return;
    const b = d.budgets;
    const series = [
      { key: "mc", name: "Plain Monte Carlo", short: "MC" },
      { key: "qmc", name: "Sobol QMC", short: "QMC" },
      { key: "qae", name: "QAE (MLAE)", short: "QAE" },
    ].map((s) => ({ ...s, color: C[s.key], points: b.map((r) => ({ x: r.queries, y: r[`rmse_${s.key}`] })) }));
    const chart = lineChart(document.getElementById("convergence-chart"), {
      series,
      xLog: true,
      xLabel: "oracle queries (log scale)",
      yLabel: "RMSE vs. true a (log)",
      xName: (x) => `${x.toLocaleString("en-US")} queries`,
      yFmt: sci,
      ariaLabel: "Line chart of estimation error against queries for plain Monte Carlo, Sobol QMC and QAE on the two-driver street model, both axes log scale. Monte Carlo falls slowest; Sobol QMC stays lowest throughout.",
    });
    window.FloodlineChart = chart;

    const alphaRows = document.getElementById("alpha-rows");
    alphaRows.replaceChildren();
    [["QAE (MLAE)", "qae", "1"], ["Plain Monte Carlo", "mc", "2"], ["Sobol QMC", "qmc", "~1, worse with dimension"]].forEach(([label, k, book]) => {
      const s = d.scaling[k];
      cells(alphaRows.insertRow(), [label, s.alpha.toFixed(2), `[${s.alpha_ci[0].toFixed(2)}, ${s.alpha_ci[1].toFixed(2)}]`, book], true);
    });
    const epsRows = document.getElementById("eps-rows");
    epsRows.replaceChildren();
    for (const e of d.matched_eps) {
      cells(epsRows.insertRow(), [
        e.eps.toExponential(0),
        fmtQ(e.qae_queries), fmtQ(e.mc_queries),
        `${e.mc_over_qae.toPrecision(3)}× [${e.mc_over_qae_ci[0].toPrecision(3)}, ${e.mc_over_qae_ci[1].toPrecision(3)}]`,
        fmtQ(e.qmc_queries),
      ], true);
    }
  }).catch(() => {
    say("convergence-chart", "Convergence data unavailable. The tables below hold the same numbers.");
  });

  // Five-driver study: every classical arm as a multiple of QAE's queries.
  FloodlineData.multi.then((m) => {
    const zs = Object.keys(m.studies);
    const study = m.studies[zs[0]];
    const ds = Object.keys(study.configs).map(Number).sort((a, b) => a - b);
    const EPS = 0.0001;
    const arms = [
      { name: "Plain Monte Carlo", short: "MC", color: C.mc, f: (r) => r.mc_over_qae },
      { name: "Sobol QMC", short: "QMC", color: C.qmc, f: (r) => r.qmc_over_qae },
      { name: "Cond. MC + Sobol, black box", short: "CMC black box", color: "#a2730c", f: (r, c) => r.cmc_qmc_over_qae * c.bisection_evals },
      { name: "Cond. MC + Sobol", short: "CMC", color: "#7d55b0", f: (r) => r.cmc_qmc_over_qae },
    ];
    const at = (c, eps) => c.matched.find((r) => r.eps === eps);
    lineChart(document.getElementById("multi-chart"), {
      series: arms.map((a) => ({ ...a, points: ds.map((d) => ({ x: d, y: a.f(at(study.configs[d], EPS), study.configs[d]) })) })),
      xLog: false,
      xLabel: "number of flood drivers d",
      yLabel: "classical ÷ QAE queries (log)",
      xName: (d) => `d = ${d} drivers`,
      yFmt: (v) => `${v.toPrecision(2)}×`,
      yTick: (v) => `${v}×`,
      ref: { y: 1, above: "QAE cheaper ↑", below: "classical cheaper ↓", left: true },
      ariaLabel: `Line chart of classical queries divided by QAE queries at error 1e-4 against the number of drivers, for the ${study.z_ft} ft street. Sobol QMC rises above 1 near 4 drivers; conditional MC plus Sobol stays below 1; its black-box version rises above 1 at 5 drivers.`,
    });
    // Win 3: Sobol QMC ÷ QAE by drivers, benchmark street; the band spans every street's and ε's crossover d*.
    const dStars = zs.flatMap((z) => Object.values(m.studies[z].crossover.qmc).map((c) => c.d_star));
    const epsList = [0.001, 0.0003, 0.0001];
    const qmcSeries = epsList.map((eps, i) => {
      const name = `ε = ${eps.toExponential(0)}`;
      const points = ds.map((d) => { const r = at(study.configs[d], eps); return { x: d, y: r.qmc_over_qae, lo: r.qmc_over_qae_ci[0], hi: r.qmc_over_qae_ci[1] }; });
      const last = points[points.length - 1];
      return { name, short: `${eps.toExponential(0)}: ${ratio(last.y)}`, color: EPS_RAMP[i], dx: (i - 1) * 5, points };
    });
    qmcSeries[2].label = "above";
    qmcSeries[2].points[ds.length - 1].big = true;
    lineChart(document.getElementById("qmc-chart"), {
      series: qmcSeries,
      xLog: false,
      xLabel: "number of flood drivers d",
      yLabel: "× fewer queries for QAE (log)",
      xName: (d) => `d = ${d} drivers`,
      yFmt: ratio,
      yTicks: [0.25, 0.5, 1, 2, 4],
      yTick: (v) => `${v}×`,
      ref: { y: 1, legend: "1× tie" },
      band: { x0: Math.min(...dStars), x1: Math.max(...dStars), label: `crossover ${Math.min(...dStars).toFixed(1)}–${Math.max(...dStars).toFixed(1)}` },
      ariaLabel: `Line chart with 95% confidence bars: Sobol QMC queries divided by QAE queries, by number of drivers, ${study.z_ft} ft street. ${qmcSeries.map((s) => `${s.name}: ${s.points.map((p) => `${ratio(p.y)} at d = ${p.x}`).join(", ")}`).join(". ")}. QAE overtakes QMC between d = ${Math.min(...dStars).toFixed(1)} and ${Math.max(...dStars).toFixed(1)}.`,
    });

    // Win 4: black-box simulator. Conditional MC must bisect each threshold, a fixed bisection_evals runs per sample, so the CI scales with it.
    const c5 = study.configs["5"];
    const bb = c5.matched.map((r) => { const k = c5.bisection_evals; return { y: r.cmc_qmc_over_qae * k, lo: r.cmc_qmc_over_qae_ci[0] * k, hi: r.cmc_qmc_over_qae_ci[1] * k }; });
    bb.forEach((v) => { v.text = ratio(v.y); });
    barChart(document.getElementById("bb-chart"), {
      groups: c5.matched.map((r) => `ε = ${r.eps.toExponential(0)}`),
      series: [{ name: "Black-box simulator runs", color: C.qae, values: bb }],
      yTicks: [2, 4],
      ariaLabel: `Bar chart with 95% confidence bars: QAE needs ${bb.map((v, i) => `${v.text} [${v.lo.toFixed(1)}, ${v.hi.toFixed(1)}] fewer simulator runs at error ${c5.matched[i].eps.toExponential(0)}`).join(", ")}, five drivers, ${study.z_ft} ft street.`,
    });

    const rows = document.getElementById("multi-rows");
    if (!rows) return;
    rows.replaceChildren();
    for (const z of zs) {
      const s = m.studies[z];
      for (const d of ds) {
        const c = s.configs[d];
        for (const r of c.matched) {
          const x = (v) => `${v.toPrecision(2)}×`;
          cells(rows.insertRow(), [`${s.z_ft} ft, d = ${d}`, r.eps.toExponential(0), x(r.qmc_over_qae), x(r.cmc_qmc_over_qae), x(r.cmc_qmc_over_qae * c.bisection_evals), x(r.mc_over_qae)], true);
        }
      }
    }
  }).catch(() => {
    for (const id of ["multi-chart", "qmc-chart", "bb-chart"]) say(id, "Five-driver data unavailable.");
  });

  // Win 2: plain Monte Carlo ÷ QAE, two-driver street vs the five-driver model (benchmark street, d = 5).
  Promise.all([FloodlineData.results, FloodlineData.multi]).then(([r, m]) => {
    // QAE's ε is extrapolated where it lies below the smallest RMSE QAE actually reached.
    const qaeFloor = Math.min(...r.budgets.map((b) => b.rmse_qae));
    const two = r.matched_eps.map((e) => ({ y: e.mc_over_qae, lo: e.mc_over_qae_ci[0], hi: e.mc_over_qae_ci[1], text: ratio(e.mc_over_qae), hollow: e.eps < qaeFloor }));
    const s5 = Object.values(m.studies)[0];
    const five = r.matched_eps.map((e) => {
      const x = s5.configs["5"].matched.find((q) => q.eps === e.eps);
      return { y: x.mc_over_qae, lo: x.mc_over_qae_ci[0], hi: x.mc_over_qae_ci[1], text: ratio(x.mc_over_qae) };
    });
    const series = [
      { name: "2 drivers (hollow: QAE extrapolated)", color: C.qae, values: two },
      { name: "5 drivers", color: C.mc, values: five },
    ];
    barChart(document.getElementById("mc-chart"), {
      groups: r.matched_eps.map((e) => `ε = ${e.eps.toExponential(0)}`),
      series,
      yTicks: [10, 100],
      height: 300,
      ariaLabel: `Bar chart with 95% confidence bars: how many times fewer queries QAE needs than plain Monte Carlo. ${series.map((s) => `${s.name}: ${s.values.map((v, i) => `${v.text}${v.hollow ? " (extrapolated)" : ""} at error ${r.matched_eps[i].eps.toExponential(0)}`).join(", ")}`).join(". ")}.`,
    });
  }).catch(() => {
    say("mc-chart", "Monte Carlo data unavailable.");
  });

  // Wins study: the best classical arm (CMC+QMC) against QAE as the model's own uncertain parameters are added.
  FloodlineData.wins.then((w) => {
    const ds = Object.keys(w.dim).map(Number).sort((a, b) => a - b);
    const series = [["0.0001", "ε = 1e-4", EPS_RAMP[1], -5], ["0.0003", "ε = 3e-4", EPS_RAMP[0], 5]].map(([eps, name, color, dx]) => ({
      name, short: name, color, dx,
      points: ds.map((d) => { const r = w.dim[d].vs_qae.cmc_qmc[eps]; return { x: d, y: r.ratio, lo: r.ci[0], hi: r.ci[1] }; }),
    }));
    series[0].label = "above";
    series[1].label = "below";
    const top = series[0].points[series[0].points.length - 1];
    Object.assign(top, { big: true, text: `${top.y.toFixed(1)}× [${top.lo.toFixed(1)}, ${top.hi.toFixed(1)}]` });
    lineChart(document.getElementById("wins-chart"), {
      series,
      xLog: false,
      xLabel: "uncertain factors d (5 drivers + model parameters)",
      yLabel: "× fewer queries for QAE (log)",
      xName: (d) => `d = ${d} factors`,
      yFmt: (v) => `${v.toPrecision(2)}×`,
      yTicks: [0.5, 1, 2, 4],
      yTick: (v) => `${v}×`,
      ref: { y: 1, legend: "1× tie" },
      ariaLabel: `Line chart with 95% confidence bars: how many times fewer queries ideal QAE needs than the best classical method, by number of uncertain factors. At error 1e-4: ${series[0].points.map((p) => `${p.y.toFixed(2)} at d = ${p.x}`).join(", ")}; the top value is ${top.y.toFixed(1)} [${top.lo.toFixed(1)}, ${top.hi.toFixed(1)}]. At error 3e-4: ${series[1].points.map((p) => `${p.y.toFixed(2)} at d = ${p.x}`).join(", ")}.`,
    });
  }).catch(() => {
    say("wins-chart", "Wins data unavailable.");
  });

  // Real ibm_fez run: P(flood qubit = 1) after Q^m A. Ideal law sin²((2m+1)θ), a = sin²θ.
  FloodlineData.hw.then((h) => {
    const theta = Math.asin(Math.sqrt(h.model.a));
    const law = (m) => Math.sin((2 * m + 1) * theta) ** 2;
    const mMax = h.ms[h.ms.length - 1];
    const curve = Array.from({ length: mMax * 20 + 1 }, (_, i) => ({ x: i / 20, y: law(i / 20) }));
    const pts = (ys) => h.ms.map((m, i) => ({ x: m, y: ys[i] }));
    const series = [
      { name: "Ideal law", short: "ideal", color: "#6b7686", curve, dots: false, points: pts(h.ideal_p_obj) },
      { name: "Noisy simulation of ibm_fez", short: "noisy sim", color: C.mc, line: false, dx: -4, points: pts(h.noisy_sim.p_obj) },
      { name: `Real ${h.backend} hardware`, short: h.backend, color: C.qae, line: false, dx: 4, points: pts(h.hardware.p_obj) },
    ];
    const f2 = (v) => v.toFixed(2);
    lineChart(document.getElementById("hw-chart"), {
      series,
      xLog: false,
      xLabel: "Grover depth m",
      yLabel: "P(flood qubit = 1)",
      xName: (m) => `m = ${m}, ${h.two_qubit_gates[h.ms.indexOf(m)]} two-qubit gates`,
      yFmt: f2,
      yDomain: [0, 1],
      yTicks: [0, 0.25, 0.5, 0.75, 1],
      yTick: (v) => String(v),
      ariaLabel: `Chart of P(flood qubit = 1) against Grover depth m from ${h.ms[0]} to ${mMax}. ${series.map((s) => `${s.name}: ${s.points.map((p) => f2(p.y)).join(", ")}`).join(". ")}.`,
    });
  }).catch(() => {
    say("hw-chart", "Hardware data unavailable.");
  });

  FloodlineData.crossover.then((x) => {
    if (!document.getElementById("crossover-chart")) return;
    const epsKeys = Object.keys(x.crossover.qae_fit).sort((a, b) => b - a);
    const ds = x.setup.ds;
    const series = epsKeys.map((eps, i) => ({
      name: `ε = ${Number(eps).toExponential(0)}`,
      color: EPS_RAMP[i],
      points: ds.map((d) => ({ x: d, y: x.crossover.qae_fit[eps].qmc_over_qae_by_d[d], hollow: x.qmc_sum[d].extrapolated[eps] })),
    }));
    lineChart(document.getElementById("crossover-chart"), {
      series,
      xLog: false,
      xLabel: "number of correlated flood drivers d",
      yLabel: "toy: QMC ÷ QAE queries (log)",
      xName: (d) => `d = ${d} driver${d > 1 ? "s" : ""}`,
      yFmt: (v) => `${v.toPrecision(2)}×`,
      yTick: (v) => `${v}×`,
      ref: { y: 1, above: "QAE cheaper ↑", below: "QMC cheaper ↓" },
      ariaLabel: (() => {
        const dStars = epsKeys.map((e) => x.crossover.qae_fit[e].d_star_median);
        const ends = series.map((s) => s.points[s.points.length - 1].y);
        return `Toy model, superseded: line chart of the ratio of Sobol QMC queries to QAE queries against the number of drivers d, one line per target error. The lines cross 1 between d = ${Math.min(...dStars).toFixed(1)} and ${Math.max(...dStars).toFixed(1)} and reach ${Math.min(...ends).toPrecision(2)} to ${Math.max(...ends).toPrecision(2)} at d = ${ds[ds.length - 1]}.`;
      })(),
    });
    const head = document.querySelector("#xo-head tr");
    head.replaceChildren();
    cells(head, ["Drivers d", ...epsKeys.map((e) => `ε = ${Number(e).toExponential(0)}`)]);
    head.querySelectorAll("td").forEach((td) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = td.textContent;
      td.replaceWith(th);
    });
    const rows = document.getElementById("xo-rows");
    rows.replaceChildren();
    for (const d of ds) {
      cells(rows.insertRow(), [String(d), ...epsKeys.map((e) => `${x.crossover.qae_fit[e].qmc_over_qae_by_d[d].toPrecision(2)}×${x.qmc_sum[d].extrapolated[e] ? " (extrap.)" : ""}`)], true);
    }
    cells(rows.insertRow(), ["Crossover d* (95% CI)", ...epsKeys.map((e) => {
      const c = x.crossover.qae_fit[e];
      return `${c.d_star_median.toFixed(1)} [${c.d_star_ci95[0].toFixed(1)}, ${c.d_star_ci95[1].toFixed(1)}]`;
    })], true);
  }).catch(() => {
    say("crossover-chart", "Crossover data unavailable.");
  });
})();
