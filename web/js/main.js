// Floodline hero: a scroll-free "intro" that crossfades a wide Gulf-of-
// Mexico/Florida still into a close Key West still (two static images
// stitched from downloaded OpenStreetMap tiles — see CREDITS.md), then an
// animated canvas overlay suggests flood water rising across the island.
// map.js lazy-loads a live MapLibre layer on top of these once idle; if
// that fails for any reason, these stills are the whole picture, not a
// fallback bolted on after the fact. Everything here is progressive
// enhancement: if it fails or is skipped, the <noscript> fallback and the
// reduced-motion CSS rule in style.css both already make the page fully
// readable without it.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const saveData = navigator.connection && navigator.connection.saveData;

initHeroStats();
initHeroMap();
initSimulate();

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

  const restLevel = 0.34;
  let running = false;
  let raf = null;
  const start = performance.now();
  const riseDelay = zoomDelay + 1600;
  const riseDuration = reduceMotion ? 1 : 2400;

  function easeOutCubic(x) { return 1 - Math.pow(1 - x, 3); }

  function draw(now) {
    const w = canvas.width, h = canvas.height;
    const t = (now - start) / 1000;
    const riseT = Math.min(1, Math.max(0, (now - start - riseDelay) / riseDuration));
    const level = restLevel * easeOutCubic(riseT);
    const baseY = h * (1 - level);

    ctx.clearRect(0, 0, w, h);
    drawWaveLayer(ctx, w, h, baseY, t * 0.5, 14, "rgba(0, 245, 255, 0.28)");
    drawWaveLayer(ctx, w, h, baseY + h * 0.012, -t * 0.35, 20, "rgba(255, 183, 3, 0.16)");

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
    draw(performance.now() + riseDelay + riseDuration);
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

// --- "Simulate" toggle: replays the chart draw-in, the incident feed, and
// counts the oracle-queries badge up to its real measured value. No fake
// data is introduced — it just re-plays assets/data/results.json. ---
function initSimulate() {
  const btn = document.getElementById("simulate-btn");
  if (!btn) return;
  let running = false;

  btn.addEventListener("click", () => {
    if (running) return;
    running = true;
    btn.textContent = "Simulating…";
    btn.setAttribute("aria-busy", "true");

    if (window.FloodlineChart) window.FloodlineChart.replay();
    if (window.FloodlineFeed) window.FloodlineFeed.replay();
    tickQueryBadge();

    const done = () => {
      running = false;
      btn.textContent = "Run simulation again";
      btn.removeAttribute("aria-busy");
      window.removeEventListener("floodline:chart-done", done);
    };
    window.addEventListener("floodline:chart-done", done);
    if (reduceMotion) done(); // chart draws instantly; nothing to wait on
  });
}

function tickQueryBadge() {
  const el = document.getElementById("badge-queries-value");
  if (!el) return;
  const target = Number(el.dataset.target || 0);
  if (reduceMotion || !target) { el.textContent = target.toLocaleString(); return; }
  const duration = 1400;
  const start = performance.now();
  function step(now) {
    const f = Math.min(1, (now - start) / duration);
    el.textContent = Math.round(target * f).toLocaleString();
    if (f < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
