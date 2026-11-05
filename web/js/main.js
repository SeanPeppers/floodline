// "Replay": re-draws the two-driver convergence chart from results.json.
(function () {
  const btn = document.getElementById("simulate-btn");
  if (!btn) return;
  let running = false;

  btn.addEventListener("click", () => {
    if (running) return;
    running = true;
    btn.setAttribute("aria-busy", "true");
    const done = () => {
      running = false;
      btn.removeAttribute("aria-busy");
      window.removeEventListener("floodline:chart-done", done);
    };
    window.addEventListener("floodline:chart-done", done);
    if (window.FloodlineChart) window.FloodlineChart.replay();
    else done();
  });
})();
