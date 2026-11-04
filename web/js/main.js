// Floodline hero: a scroll-free "intro" that crossfades a wide Gulf-of-
// Mexico/Florida still into a close Key West still (two static images
// stitched from downloaded OpenStreetMap tiles — see CREDITS.md; this is
// pure CSS opacity/transform, no live map library and no runtime tile
// requests), then an animated canvas overlay suggests flood water rising
// across the island. Everything here is progressive enhancement: if it
// fails or is skipped, the <noscript> fallback and the reduced-motion CSS
// rule in style.css both already make the page fully readable without it.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const saveData = navigator.connection && navigator.connection.saveData;

initHeroStats();
initHeroMap();

// Hero stat cards stagger in on load (CSS transition-delay does the
// staggering; this just flips the trigger class). The hero is always above
// the fold, so this runs unconditionally on load rather than waiting on an
// IntersectionObserver that could, in theory, never fire.
function initHeroStats() {
  const group = document.querySelector(".reveal-group");
  if (group) requestAnimationFrame(() => group.classList.add("is-visible"));
}

// --- hero map crossfade + flood water canvas ---
function initHeroMap() {
  const heroMap = document.querySelector(".hero-map");
  if (!heroMap) return;

  if (saveData) {
    // Keep the wide still (already in the HTML, already requested by the
    // browser preloader) and skip everything animated.
    return;
  }

  // Trigger the region -> Key West crossfade once, shortly after first
  // paint so the wide establishing shot actually registers before it zooms.
  // Under reduced motion the CSS transition is forced to ~0ms anyway
  // (global rule in style.css), so this still lands on the right end state.
  const zoomDelay = reduceMotion ? 0 : 900;
  setTimeout(() => heroMap.classList.add("is-zoomed"), zoomDelay);

  const canvas = heroMap.querySelector(".flood-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  function resize() {
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.max(1, rect.width * dpr);
    canvas.height = Math.max(1, rect.height * dpr);
  }
  resize();
  new ResizeObserver(resize).observe(canvas);

  const restLevel = 0.34; // fraction of canvas height the water rests at
  let running = false;
  let raf = null;
  const start = performance.now();
  const riseDelay = zoomDelay + 1600; // let the zoom read before water rises
  const riseDuration = reduceMotion ? 1 : 2400;

  function easeOutCubic(x) { return 1 - Math.pow(1 - x, 3); }

  function draw(now) {
    const w = canvas.width, h = canvas.height;
    const t = (now - start) / 1000;
    const riseT = Math.min(1, Math.max(0, (now - start - riseDelay) / riseDuration));
    const level = restLevel * easeOutCubic(riseT);
    const baseY = h * (1 - level);

    ctx.clearRect(0, 0, w, h);
    drawWaveLayer(ctx, w, h, baseY, t * 0.5, 14, "rgba(45, 212, 191, 0.34)");
    drawWaveLayer(ctx, w, h, baseY + h * 0.012, -t * 0.35, 20, "rgba(94, 184, 255, 0.24)");

    if (running) raf = requestAnimationFrame(draw);
  }

  function drawWaveLayer(ctx, w, h, baseY, phase, amp, fill) {
    ctx.beginPath();
    ctx.moveTo(0, h);
    ctx.lineTo(0, baseY);
    const step = w / 48;
    for (let x = 0; x <= w; x += step) {
      const y = baseY + Math.sin(x * 0.012 + phase) * amp * (window.devicePixelRatio || 1);
      ctx.lineTo(x, y);
    }
    ctx.lineTo(w, h);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
  }

  if (reduceMotion) {
    draw(performance.now() + riseDelay + riseDuration); // single static end-state frame
    return;
  }

  const section = heroMap.closest(".section") || heroMap;
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && !running) {
          running = true;
          raf = requestAnimationFrame(draw);
        } else if (!entry.isIntersecting && running) {
          running = false;
          if (raf) cancelAnimationFrame(raf);
        }
      });
    },
    { threshold: 0.05 }
  );
  io.observe(section);
}
