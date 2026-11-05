// Rising water: past the scroll story, the .flood layer climbs from off-screen
// to MAX of the viewport by the bottom of the page. Layout is read only on
// resize/load; each scroll frame writes one CSS variable, and only on change.
(function () {
  const layer = document.querySelector(".flood");
  const start = document.getElementById("results");
  if (!layer || !start) return;
  const MAX = 0.72;
  let top = 0, span = 1, last = -1, queued = false;

  function measure() {
    top = start.getBoundingClientRect().top + scrollY;
    span = Math.max(1, document.documentElement.scrollHeight - top);
    update();
  }
  function update() {
    queued = false;
    const p = Math.min(1, Math.max(0, (scrollY + innerHeight - top) / span));
    const v = Math.round(MAX * p * 1000) / 1000;
    if (v !== last) { layer.style.setProperty("--flood", v); last = v; }
  }
  addEventListener("scroll", () => { if (!queued) { queued = true; requestAnimationFrame(update); } }, { passive: true });
  addEventListener("resize", measure, { passive: true });
  addEventListener("load", measure);
  measure();
})();
