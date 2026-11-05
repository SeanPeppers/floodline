// Rising water: past the scroll story, the .flood layer climbs from off-screen
// to MAX of the viewport by the bottom of the page. Layout is read only on
// resize/load; each scroll frame writes one CSS variable, and only on change.
(function () {
  const layer = document.querySelector(".flood");
  const start = document.getElementById("results");
  if (!layer || !start) return;
  const MAX = 0.72;
  let top = 0, span = 1, last = -1, queued = false, still = 0;

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
  // The wave laps only while the reader is scrolling, so nothing moves on its own.
  addEventListener("scroll", () => {
    if (!queued) { queued = true; requestAnimationFrame(update); }
    if (last > 0) {
      layer.classList.add("is-moving");
      clearTimeout(still);
      still = setTimeout(() => layer.classList.remove("is-moving"), 1200);
    }
  }, { passive: true });
  addEventListener("resize", measure, { passive: true });
  addEventListener("load", measure);
  measure();
})();
