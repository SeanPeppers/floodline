// Results charts and tables, drawn from FloodlineData (data.js). One small SVG
// line-chart helper serves both charts: log axes, a legend, sparing end labels,
// a crosshair + tooltip on hover and keyboard focus. The tables beside each
// chart carry every value, so the tooltip only ever enhances.
(function () {
  const SVG = "http://www.w3.org/2000/svg";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // dataviz reference palette, dark steps, validated against the panel surface
  // #0f1522 (categorical: CVD dE 9.4, all >= 3:1; ordinal blue: monotone L).
  const C = { qae: "#3987e5", mc: "#d95926", qmc: "#199e70" };
  const EPS_RAMP = ["#b7d3f6", "#5598e7", "#1c5cab"];

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
    const legend = document.createElement("ul");
    legend.className = "chart__legend";
    for (const s of cfg.series) {
      const li = document.createElement("li");
      const key = document.createElement("span");
      key.className = "chart__key";
      key.style.background = s.color;
      li.append(key, document.createTextNode(s.name));
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
    const ys = cfg.series.flatMap((s) => s.points.map((p) => p.y)).concat(cfg.ref ? [cfg.ref.y] : []);
    const yLo = Math.min(...ys) / 1.4, yHi = Math.max(...ys) * 1.4;
    let paths = [], svg, X, Y, idx = -1;

    function draw() {
      const W = Math.max(280, plot.clientWidth);
      const H = Math.round(Math.min(420, Math.max(260, W * 0.52)));
      const narrow = W < 520;
      const pad = { l: narrow ? 44 : 56, r: narrow ? 58 : 110, t: 14, b: 44 };
      const x0 = cfg.xLog ? Math.log10(xs[0]) : xs[0], x1 = cfg.xLog ? Math.log10(xs[xs.length - 1]) : xs[xs.length - 1];
      X = (v) => pad.l + (((cfg.xLog ? Math.log10(v) : v) - x0) / (x1 - x0)) * (W - pad.l - pad.r);
      Y = (v) => pad.t + (1 - (Math.log10(v) - Math.log10(yLo)) / (Math.log10(yHi) - Math.log10(yLo))) * (H - pad.t - pad.b);

      svg?.remove();
      svg = el("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": cfg.ariaLabel });
      plot.prepend(svg);
      const grid = el("g", { class: "chart__grid" }, svg);
      for (const t of logTicks(yLo, yHi)) {
        el("line", { x1: pad.l, x2: W - pad.r, y1: Y(t.v), y2: Y(t.v) }, grid);
        el("text", { x: pad.l - 8, y: Y(t.v) + 4, "text-anchor": "end", class: "chart__tick" }, grid).textContent = cfg.yTick ? cfg.yTick(t.v) : t.label;
      }
      const xt = cfg.xLog ? logTicks(xs[0], xs[xs.length - 1]).map((t) => ({ v: t.v, label: compact(t.v) })) : xs.map((v) => ({ v, label: String(v) }));
      for (const t of xt) el("text", { x: X(t.v), y: H - pad.b + 18, "text-anchor": "middle", class: "chart__tick" }, grid).textContent = t.label;
      el("line", { x1: pad.l, x2: W - pad.r, y1: H - pad.b, y2: H - pad.b, class: "chart__axis" }, svg);
      el("text", { x: pad.l + (W - pad.l - pad.r) / 2, y: H - 6, "text-anchor": "middle", class: "chart__label" }, svg).textContent = cfg.xLabel;
      // Phones: the figure title names the y measure; a rotated label would collide with the ticks.
      if (!narrow) el("text", { x: 12, y: pad.t + (H - pad.t - pad.b) / 2, "text-anchor": "middle", class: "chart__label", transform: `rotate(-90 12 ${pad.t + (H - pad.t - pad.b) / 2})` }, svg).textContent = cfg.yLabel;

      if (cfg.ref) {
        el("line", { x1: pad.l, x2: W - pad.r, y1: Y(cfg.ref.y), y2: Y(cfg.ref.y), class: "chart__ref" }, svg);
        el("text", { x: W - pad.r - 4, y: Y(cfg.ref.y) - 6, "text-anchor": "end", class: "chart__reflabel" }, svg).textContent = cfg.ref.above;
        el("text", { x: W - pad.r - 4, y: Y(cfg.ref.y) + 15, "text-anchor": "end", class: "chart__reflabel" }, svg).textContent = cfg.ref.below;
      }

      paths = [];
      const ends = [];
      for (const s of cfg.series) {
        const g = el("g", {}, svg);
        const solid = s.points.filter((p) => !p.hollow);
        const d = (pts) => pts.map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("");
        paths.push(el("path", { d: d(solid), stroke: s.color, class: "chart__line" }, g));
        const firstHollow = s.points.findIndex((p) => p.hollow);
        if (firstHollow > 0) el("path", { d: d(s.points.slice(firstHollow - 1)), stroke: s.color, class: "chart__line chart__line--extrap" }, g);
        for (const p of s.points) {
          el("circle", { cx: X(p.x), cy: Y(p.y), r: 4, fill: p.hollow ? "var(--chart-surface)" : s.color, stroke: p.hollow ? s.color : "var(--chart-surface)", "stroke-width": 2, class: "chart__dot" }, g);
        }
        const last = s.points[s.points.length - 1];
        ends.push({ y: Y(last.y), x: X(last.x), name: s.short || s.name });
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
        val.textContent = cfg.yFmt(p.y) + (p.hollow ? " (extrap.)" : "");
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
    plot.addEventListener("pointerleave", hide);
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

  const sci = (v) => v.toExponential(1).replace("e-", "e−");
  const fmtQ = (n) => compact(n);

  function cells(tr, values, header) {
    values.forEach((v, i) => {
      const c = document.createElement(i === 0 && header ? "th" : "td");
      if (i === 0 && header) c.scope = "row";
      c.textContent = v;
      tr.appendChild(c);
    });
  }

  FloodlineData.results.then((d) => {
    const b = d.budgets;
    const series = [
      { key: "mc", name: "Plain Monte Carlo", short: "MC" },
      { key: "qmc", name: "Sobol QMC (classical, 2-D)", short: "QMC" },
      { key: "qae", name: "Quantum MLAE", short: "MLAE" },
    ].map((s) => ({ ...s, color: C[s.key], points: b.map((r) => ({ x: r.queries, y: r[`rmse_${s.key}`] })) }));
    const chart = lineChart(document.getElementById("convergence-chart"), {
      series,
      xLog: true,
      xLabel: "oracle queries (log scale)",
      yLabel: "RMSE vs. true a (log)",
      xName: (x) => `${x.toLocaleString("en-US")} queries`,
      yFmt: sci,
      ariaLabel: "Line chart of estimation error against queries for plain Monte Carlo, Sobol QMC and quantum MLAE, both axes log scale. Monte Carlo falls slowest, MLAE faster, Sobol QMC lowest throughout.",
    });
    window.FloodlineChart = chart;

    const alphaRows = document.getElementById("alpha-rows");
    alphaRows.replaceChildren();
    [["MLAE (quantum)", "qae", "1"], ["Plain Monte Carlo", "mc", "2"], ["Sobol QMC (classical, 2-D)", "qmc", "1 in 1-D; degrades with dimension"]].forEach(([label, k, book]) => {
      const s = d.scaling[k];
      cells(alphaRows.insertRow(), [label, s.alpha.toFixed(2), `[${s.alpha_ci[0].toFixed(2)}, ${s.alpha_ci[1].toFixed(2)}]`, book], true);
    });
    const epsRows = document.getElementById("eps-rows");
    epsRows.replaceChildren();
    for (const e of d.matched_eps) {
      cells(epsRows.insertRow(), [
        `${e.eps.toExponential(0)} (${(e.rel_eps * 100).toFixed(2)}%)`,
        fmtQ(e.qae_queries), fmtQ(e.mc_queries),
        `${e.mc_over_qae.toPrecision(3)}× [${e.mc_over_qae_ci[0].toPrecision(3)}, ${e.mc_over_qae_ci[1].toPrecision(3)}]`,
        fmtQ(e.qmc_queries),
      ], true);
    }
  }).catch(() => {
    document.getElementById("convergence-chart").textContent = "Convergence data unavailable. The tables below hold the same numbers.";
  });

  FloodlineData.crossover.then((x) => {
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
      yLabel: "QMC ÷ MLAE queries (log)",
      xName: (d) => `d = ${d} driver${d > 1 ? "s" : ""}`,
      yFmt: (v) => `${v.toPrecision(2)}×`,
      yTick: (v) => `${v}×`,
      ref: { y: 1, above: "QAE cheaper ↑", below: "QMC cheaper ↓" },
      ariaLabel: (() => {
        const dStars = epsKeys.map((e) => x.crossover.qae_fit[e].d_star_median);
        const ends = series.map((s) => s.points[s.points.length - 1].y);
        return `Line chart of the ratio of Sobol QMC queries to MLAE queries against the number of drivers d, one line per target error. The lines cross 1 between d = ${Math.min(...dStars).toFixed(1)} and ${Math.max(...dStars).toFixed(1)} and reach ${Math.min(...ends).toPrecision(2)} to ${Math.max(...ends).toPrecision(2)} at d = ${ds[ds.length - 1]}.`;
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
    document.getElementById("crossover-chart").textContent = "Crossover data unavailable.";
  });
})();
