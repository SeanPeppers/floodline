// Rising tide behind the sections below the Irma journey (decorative, aria-hidden).
// Fades in once the journey has scrolled away, then rises from 8vh to ~38vh by page end.
(function () {
  const tide = document.querySelector(".tide");
  const journey = document.getElementById("journey");
  if (!tide || !journey) return;
  const root = document.documentElement;
  let ticking = false;

  function update() {
    ticking = false;
    const vh = window.innerHeight;
    const start = journey.offsetTop + journey.offsetHeight - vh * 0.6;
    const end = root.scrollHeight - vh;
    const y = window.scrollY;
    const p = Math.min(1, Math.max(0, (y - start) / Math.max(1, end - start)));
    tide.style.setProperty("--tide-o", y > start ? "1" : "0");
    tide.style.setProperty("--tide-h", (8 + p * 30).toFixed(2) + "vh");
  }
  function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(update); } }
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  update();
})();
