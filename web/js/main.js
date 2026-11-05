// "Replay the benchmark": re-draws the convergence chart, replays the log, and
// counts the oracle-queries badge up to its real measured value. No data is
// invented; it only re-plays assets/data/results.json.
(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const btn = document.getElementById("simulate-btn");
  if (!btn) return;
  let running = false;

  btn.addEventListener("click", () => {
    if (running) return;
    running = true;
    btn.textContent = "Replaying…";
    btn.setAttribute("aria-busy", "true");

    const done = () => {
      running = false;
      btn.textContent = "Replay again";
      btn.removeAttribute("aria-busy");
      window.removeEventListener("floodline:chart-done", done);
    };
    window.addEventListener("floodline:chart-done", done);
    if (window.FloodlineChart) window.FloodlineChart.replay();
    else done();
    if (window.FloodlineFeed) window.FloodlineFeed.replay();
    tickQueryBadge();
  });

  function tickQueryBadge() {
    const el = document.getElementById("badge-queries-value");
    FloodlineData.results.then((d) => {
      const target = d.budgets[d.budgets.length - 1].queries;
      if (reduceMotion) { el.textContent = target.toLocaleString("en-US"); return; }
      const start = performance.now();
      const step = (now) => {
        const f = Math.min(1, (now - start) / 1400);
        el.textContent = Math.round(target * f).toLocaleString("en-US");
        if (f < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }
})();
