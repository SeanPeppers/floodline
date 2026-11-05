// Scroll story: turns native scroll position into a chapter coordinate u
// (chapter i spans [i, i+1)), derives the water level from each chapter's
// data-* attributes, and drives either the 3-D stage (scene.js,
// lazy-loaded after first paint) or a set of pre-rendered stills. Nothing
// here listens to wheel or touch, so scrolling can never get trapped.
(function () {
  const journey = document.getElementById("journey");
  if (!journey) return;
  const stage = journey.querySelector(".journey__stage");
  const canvas = stage.querySelector(".journey__canvas");
  const hud = stage.querySelector(".journey__hud");
  const chapters = [...journey.querySelectorAll(".chapter")];
  const N = chapters.length;
  const firstKeyWest = chapters.findIndex((c) => c.dataset.scene === "keywest");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const saveData = navigator.connection && navigator.connection.saveData;

  // Vertical exaggeration of the Key West terrain, quoted in the chapter text.
  const EXAGGERATION = 25;
  document.querySelectorAll('[data-bind="exaggeration"]').forEach((el) => { el.textContent = EXAGGERATION; });

  const STAGE_NAMES = { mhhw: "mean higher-high water", nws_minor: "NWS minor flood stage", nws_moderate: "NWS moderate flood stage", nws_major: "NWS major flood stage" };

  // Shared with scene.js, which reads it every frame.
  const state = { u: 0, N, firstKeyWest, level: 0, visible: true, exaggeration: EXAGGERATION, reduceMotion };
  if (/[?&]debug\b/.test(location.search)) window.floodlineState = state; // QA hook: debugU, debugCam
  // Until results.json supplies the thresholds, hold the water at MHHW rather
  // than easing toward the one level the HTML knows on its own.
  let levels = chapters.map(() => null);

  FloodlineData.derived.then((d) => {
    levels = chapters.map((c) => (c.dataset.levelM ? Number(c.dataset.levelM) : c.dataset.level ? d.levels[c.dataset.level] ?? null : null));
    update();
  }).catch((e) => console.error("Floodline: thresholds unavailable, water held at MHHW", e));

  let tops = [], heights = [];
  function measure() {
    tops = chapters.map((c) => c.getBoundingClientRect().top + window.scrollY);
    heights = chapters.map((c) => c.offsetHeight);
  }

  const smooth = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };

  // Hold each chapter's value while its text is mid-screen, ease between chapter centres.
  function easeBetween(values, u, hold = 0.22) {
    const known = values.map((v, i) => [i + 0.5, v]).filter(([, v]) => v !== null && v !== undefined);
    if (!known.length) return 0;
    if (u <= known[0][0]) return known[0][1];
    for (let k = 1; k < known.length; k++) {
      const [c0, v0] = known[k - 1], [c1, v1] = known[k];
      if (u <= c1) return v0 + (v1 - v0) * smooth(c0 + hold, c1 - hold, u);
    }
    return known[known.length - 1][1];
  }

  function chapterCoord() {
    const centre = window.scrollY + window.innerHeight * 0.5;
    let i = 0;
    while (i < N - 1 && centre >= tops[i + 1]) i++;
    return Math.max(0, Math.min(N, i + (centre - tops[i]) / heights[i]));
  }

  let activeStill = -1;
  function showStill(i) {
    if (i === activeStill) return;
    activeStill = i;
    let img = stage.querySelector(`.journey__still[data-still="${i}"]`);
    if (!img) {
      img = document.createElement("img");
      img.className = "journey__still";
      img.dataset.still = i;
      img.alt = "";
      img.decoding = "async";
      img.sizes = "100vw";
      img.srcset = [640, 1024, 1600].map((w) => `assets/stills/s${i}-${w}.webp ${w}w`).join(", ");
      img.src = `assets/stills/s${i}-1024.webp`;
      stage.insertBefore(img, canvas);
    }
    stage.querySelectorAll(".journey__still").forEach((s) => s.classList.toggle("is-active", s === img));
  }

  let hudText = "";
  function update() {
    if (!tops.length) measure();
    const u = chapterCoord();
    state.u = u;
    state.level = easeBetween(levels, u);

    const inKeyWest = u > firstKeyWest - 0.05;
    if (hud.hidden === inKeyWest) hud.hidden = !inKeyWest; // even a same-value write restyles
    if (inKeyWest) {
      const i = Math.min(N - 1, Math.floor(u));
      const c = chapters[i];
      const note = Math.abs(state.level - (levels[i] ?? NaN)) < 0.005
        ? (c.dataset.levelM ? "Irma peak at the gauge (NHC)" : STAGE_NAMES[c.dataset.level] || "")
        : "rising";
      const text = `+${state.level.toFixed(2)} m above MHHW|${note}`;
      if (text !== hudText) {
        hudText = text;
        hud.querySelector(".journey__hud-value").textContent = text.split("|")[0];
        hud.querySelector(".journey__hud-note").textContent = text.split("|")[1];
      }
    }
    if (!stage.classList.contains("is-3d")) showStill(Math.min(N - 1, Math.floor(u)));
  }

  // Cheap (cached chapter offsets, DOM writes only on change), so run it in the
  // scroll event itself rather than gating on a rAF that a busy GPU can starve.
  const onScroll = () => update();
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", () => { measure(); onScroll(); });
  new ResizeObserver(() => { measure(); onScroll(); }).observe(journey);
  new IntersectionObserver(([e]) => { state.visible = e.isIntersecting; }).observe(journey);
  measure();
  update();

  // The hero's looping scroll cue restyles the page every frame, on screen or
  // not; hold it while it is scrolled away.
  const cue = document.querySelector(".scroll-cue");
  if (cue) new IntersectionObserver(([e]) => { cue.classList.toggle("is-idle", !e.isIntersecting); }).observe(cue);

  // 3-D only with motion allowed, data not constrained, and a WebGL2 context.
  function webgl2() {
    try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; }
  }
  if (reduceMotion || saveData || !webgl2()) return;

  const start = () => import("./scene.js")
    .then((m) => m.start(canvas, state, () => {
      stage.classList.add("is-3d");
      onScroll();
    }, () => {
      stage.classList.remove("is-3d");
      activeStill = -1;
      onScroll();
    }))
    .catch(() => {}); // stills stay; the story is complete without 3-D

  const idle = (fn) => ("requestIdleCallback" in window ? requestIdleCallback(fn, { timeout: 2500 }) : setTimeout(fn, 1200));
  if (document.readyState === "complete") idle(start);
  else window.addEventListener("load", () => idle(start), { once: true });
})();
