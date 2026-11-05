// Short-version page: the "out of 100 households" icon array.
// Chance of at least one major tidal flood in 30 years = 1 - (1 - a)^30,
// with a = the annual chance from the tide-gauge GEV fit (data.js).
(function () {
  const grid = document.getElementById("icons");
  if (!grid) return;
  const draw = (a) => {
    const p = 1 - Math.pow(1 - a, 30);
    const n = Math.round(p * 100);
    grid.innerHTML = Array.from({ length: 100 }, (_, i) => (i < n ? '<i class="on"></i>' : "<i></i>")).join("");
    const label = document.getElementById("mortgage-n");
    // Say it the way people say odds: nearest "k in 4", else a percent.
    const q = Math.round(p * 4);
    if (label) label.textContent = Math.abs(p * 4 - q) < 0.12 && q > 0 ? `${q} in 4` : `${n}%`;
    grid.setAttribute("aria-label", `100 squares, one per household; ${n} are shaded: they see a major tidal flood within 30 years`);
  };
  draw(0.0458);
  const d = window.FloodlineData && window.FloodlineData.derived;
  if (d) d.then((v) => { const a = parseFloat(v.tideMajorA); if (a > 0 && a < 1) draw(a); }).catch(() => {});
})();
