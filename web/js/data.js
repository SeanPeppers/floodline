// One fetch of each data file for the whole page, plus the derived figures the
// text quotes. Every number shown on the page comes from here: the static
// values in index.html are only the no-JS fallback and get overwritten.
// Re-sync the files from the repo root with `node web/sync-data.mjs`.
(function () {
  const get = (url, type = "json") => fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r[type]();
  });

  const results = get("assets/data/results.json");
  const multi = get("assets/data/results_multi.json");
  const crossover = get("assets/data/crossover.json");
  const cli = get("assets/data/cli-example.txt", "text");

  const round = (x, n) => Number(x.toFixed(n));
  const minMax = (xs) => [Math.min(...xs), Math.max(...xs)];
  const range = (xs, n) => { const [a, b] = minMax(xs); return `${a.toFixed(n)}–${b.toFixed(n)}`; };
  const sci = (x) => { const e = Math.floor(Math.log10(x)); return `${(x / 10 ** e).toFixed(1)}e${e}`; };

  // Two-driver street model (results.json, realistic drainage rule).
  function derive(d) {
    const p = d.problem;
    const thr = p.tide.thresholds_m_above_mhhw;
    const eps = d.matched_eps;
    return {
      nYears: p.tide.n_years,
      tideMajorA: p.tide.a_true.toFixed(4),
      tideMajorInv: Math.round(1 / p.tide.a_true),
      tideMinorPct: Math.round(p.tide_alone_nws_minor * 100),
      minor: thr.nws_minor.toFixed(3),
      moderate: thr.nws_moderate.toFixed(3),
      major: thr.nws_major.toFixed(2),
      a2: p.a_true.toFixed(3),
      tau: p.tau_assumed,
      trials: d.trials,
      alphaQae: d.scaling.qae.alpha.toFixed(2),
      alphaMc: d.scaling.mc.alpha.toFixed(2),
      alphaQmc: d.scaling.qmc.alpha.toFixed(2),
      mcOverQae: eps.map((e) => Math.round(e.mc_over_qae)).join(" / "),
      qmcWins: range(eps.map((e) => 1 / e.qmc_over_qae), 1),
      dAlphaQmc: (() => {
        const q = d.alpha_delta_vs_rectangle.qmc;
        const s = (x) => (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(2);
        return `${s(q.delta_alpha)} [${s(q.ci[0])}, ${s(q.ci[1])}]`;
      })(),
      czErr: d.hardware.cz_error_median,
      pIdeal0: d.noisy_fakefez.p_ideal[0].toFixed(2),
      pNoisy0: d.noisy_fakefez.p_noisy[0].toFixed(2),
      levels: { mhhw: 0, nws_minor: thr.nws_minor, nws_moderate: thr.nws_moderate, nws_major: thr.nws_major },
    };
  }

  // Five-driver model (results_multi.json). The benchmark street is the first study (3.0 ft).
  function deriveMulti(m, r) {
    const zs = Object.keys(m.studies);
    const s = m.studies[zs[0]];
    const c5 = s.configs["5"];
    const at = (c, eps) => c.matched.find((x) => x.eps === eps);
    const e4 = at(c5, 0.0001);
    const dStars = zs.flatMap((z) => Object.values(m.studies[z].crossover.qmc).map((v) => v.d_star)).filter((v) => v !== null);
    const cmcAt5 = zs.flatMap((z) => m.studies[z].configs["5"].matched.map((x) => x.cmc_qmc_over_qae));
    const cells = zs.flatMap((z) => Object.values(m.studies[z].configs).flatMap((c) => c.matched));
    const cmcAlways = cells.every((x) => x.cmc_qmc_over_qae < 1);
    // Black box: conditional MC must bisect for each rain threshold, bisection_evals runs per sample.
    const bb = c5.matched.map((x) => (x.cmc_qmc_queries * c5.bisection_evals) / x.qae_queries);
    // Gate error at which the deepest ε = 1e-4 circuit, Q^m A, succeeds half the time.
    const circ = m.circuits["5"];
    const mDeep = c5.arms.qae.m_needed["0.0001"];
    const cx = circ.A.cx + mDeep * circ.Q.cx;
    const pNeed = Math.LN2 / cx;
    return {
      dStar: range(dStars, 1),
      qmcOverQae5: e4.qmc_over_qae.toFixed(1),
      cmcAt5: range(cmcAt5, 2),
      nCells: cells.length,
      cmcAlways: cmcAlways ? "every" : "most",
      enumEvals: sci(e4.exact_enumeration_evals),
      qaeQueries4: sci(e4.qae_queries),
      aCx: sci(circ.A.cx),
      bisect: c5.bisection_evals,
      bbWin: bb.map((x) => x.toFixed(1)).join(" / "),
      mDeep,
      deepCx: sci(cx),
      qubits5: circ.A.qubits,
      pNeed: sci(pNeed),
      czErr: r.czErr.toPrecision(2),
    };
  }

  function deriveCli(t) {
    const m = (re) => (t.match(re) || [])[1];
    return {
      cliP: m(/= ([\d.]+) \+-/),
      cliYears: m(/~ 1 in ([\d.]+) yr/),
      cliExposure: m(/expected ([\d.]+%) of road points/),
      cliPoints: Number(m(/\((\d+) road points/)).toLocaleString("en-US"),
      cliEvery2: m(/; ([\d.]+%) flood at least every 2 yr/),
    };
  }

  function deriveCrossover(x) {
    const out = {};
    for (const [eps, c] of Object.entries(x.crossover.qae_fit)) out[`xo.dStar.${eps}`] = c.d_star_median.toFixed(1);
    return out;
  }

  function bind(values) {
    document.querySelectorAll("[data-bind]").forEach((el) => {
      const v = values[el.dataset.bind];
      if (v !== undefined && typeof v !== "object") el.textContent = String(v);
    });
    return values;
  }

  const derived = results.then(derive);
  const warn = (e) => console.error("Floodline: data unavailable, showing built-in fallback values", e);
  derived.then(bind).catch(warn);
  Promise.all([multi, derived]).then(([m, r]) => bind(deriveMulti(m, r))).catch(warn);
  crossover.then(deriveCrossover).then(bind).catch(warn);
  cli.then((t) => {
    bind(deriveCli(t));
    const pre = document.getElementById("cli-output");
    if (pre) pre.textContent = t.trimEnd();
  }).catch(warn);

  // Road-raising priority (road_priority.py writes the top 100, ranked by flooded miles a year in 2050).
  const roads = get("assets/data/road_priority.json");
  roads.then((d) => {
    const tbody = document.getElementById("road-rows");
    if (!tbody) return;
    const usd = (x) => `$${(x / 1e6).toFixed(1)}M`;
    tbody.replaceChildren(...d.streets.slice(0, 5).map((s, i) => {
      const tr = document.createElement("tr");
      const cells = [
        i + 1, s.street,
        `${usd(s["usd_per_flood_year_avoided_monroe_plan_9.6M_per_mile"])}–${usd(s["usd_per_flood_year_avoided_twin_lakes_23.9M_per_mile"])}`,
        s.p_2050_intermediate.toFixed(2), s.flood_years_avoided_2026_2050_per_ft.toFixed(1), s.length_mi.toFixed(1),
      ];
      cells.forEach((v, j) => {
        const td = document.createElement(j === 1 ? "th" : "td");
        if (j === 1) td.scope = "row";
        td.textContent = v;
        tr.append(td);
      });
      return tr;
    }));
  }).catch(warn);

  window.FloodlineData = { results, multi, crossover, derived, roads };
})();
