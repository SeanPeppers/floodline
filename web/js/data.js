// One fetch of each data file for the whole page, plus the derived figures the
// text quotes. Every number shown on the page comes from here: the static
// values in index.html are only the no-JS fallback and get overwritten.
(function () {
  const getJson = (url) => fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${url}: ${r.status}`);
    return r.json();
  });

  const results = getJson("assets/data/results.json");
  const crossover = getJson("assets/data/crossover.json");

  const round = (x, n) => Number(x.toFixed(n));
  const minMax = (xs) => [Math.min(...xs), Math.max(...xs)];

  function derive(d) {
    const p = d.problem;
    const thr = p.tide.thresholds_m_above_mhhw;
    const eps = d.matched_eps;
    const [mcLo, mcHi] = minMax(eps.map((e) => e.mc_over_qae));
    const [qLo, qHi] = minMax(eps.map((e) => 1 / e.qmc_over_qae));
    return {
      nYears: p.tide.n_years,
      yearFrom: p.tide.years[0],
      yearTo: p.tide.years[1],
      slrMm: round(p.tide.slr_m_per_yr * 1000, 2).toFixed(2),
      a: round(p.a_true, 3),
      a4: p.a_true.toFixed(4),
      aInv: Math.round(1 / p.a_true),
      tideMajorA: p.tide.a_true.toFixed(4),
      tideMajorInv: Math.round(1 / p.tide.a_true),
      minor: thr.nws_minor.toFixed(3),
      moderate: thr.nws_moderate.toFixed(3),
      major: thr.nws_major.toFixed(2),
      rainIn: p.rain.threshold_level_in.toFixed(2),
      rainYears: p.rain.threshold_years,
      tau: p.tau_assumed,
      qubits: d.width_logical_qubits,
      regimes: p.n_regimes,
      trials: d.trials,
      maxQueries: d.budgets[d.budgets.length - 1].queries.toLocaleString("en-US"),
      alphaQae: d.scaling.qae.alpha.toFixed(2),
      alphaMc: d.scaling.mc.alpha.toFixed(2),
      alphaQmc: d.scaling.qmc.alpha.toFixed(2),
      mcOverQaeLo: Math.round(mcLo),
      mcOverQaeHi: Math.round(mcHi),
      qaeOverQmcLo: qLo.toFixed(1),
      qaeOverQmcHi: qHi.toFixed(1),
      pIdeal0: d.noisy_fakefez.p_ideal[0].toFixed(3),
      pNoisy0: d.noisy_fakefez.p_noisy[0].toFixed(3),
      // thresholds the 3-D scene draws, metres above MHHW
      levels: { mhhw: 0, nws_minor: thr.nws_minor, nws_moderate: thr.nws_moderate, nws_major: thr.nws_major },
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
  }

  const derived = results.then(derive);
  derived.then(bind).catch(() => {}); // fallback text in the HTML stays
  crossover.then(deriveCrossover).then(bind).catch(() => {});

  window.FloodlineData = { results, crossover, derived };
})();
