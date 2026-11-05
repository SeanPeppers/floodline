// "Incident feed" panel: NOT a live sensor feed — there is no backend here.
// It's a styled, timestamped replay of this project's own real convergence
// data (results.json), one line per query budget actually benchmarked.
// Exposes window.FloodlineFeed.replay() for the Simulate button (main.js).
(function () {
  const list = document.getElementById("incident-feed-list");
  if (!list) return;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let data = null;
  fetch("assets/data/results.json")
    .then((r) => r.json())
    .then((d) => { data = d; replay(); })
    .catch(() => {
      list.innerHTML = '<li class="feed-line">feed data unavailable offline.</li>';
    });

  function fmt(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
    return String(Math.round(n));
  }
  function ts(ms) {
    const s = ms / 1000;
    return `t+${s.toFixed(1)}s`;
  }

  let token = 0;
  function replay() {
    if (!data) return;
    const myToken = ++token;
    list.innerHTML = "";
    const lines = data.budgets.map((b, i) => ({
      delay: i * (reduceMotion ? 0 : 260),
      text: `[${ts(i * 260)}] budget ${fmt(b.queries)} q — MLAE ${b.rmse_qae.toExponential(2)} · QMC ${b.rmse_qmc.toExponential(2)} · MC ${b.rmse_mc.toExponential(2)}`,
      cls: "feed-line--data",
    }));
    const eps = data.matched_eps[0];
    lines.push({
      delay: lines.length * (reduceMotion ? 0 : 260) + 300,
      text: `[ALERT] matched ε=${eps.eps}: MLAE needs ${fmt(eps.qae_queries)} q, QMC needs ${fmt(eps.qmc_queries)} q — QAE loses this race, by design of the test`,
      cls: "feed-line--alert",
    });

    lines.forEach((line) => {
      setTimeout(() => {
        if (myToken !== token) return;
        const row = document.createElement("div");
        row.className = `feed-line ${line.cls}`;
        row.textContent = line.text;
        list.appendChild(row);
        list.scrollTop = list.scrollHeight;
        while (list.children.length > 9) list.removeChild(list.firstChild);
      }, line.delay);
    });
  }

  window.FloodlineFeed = { replay };
})();
