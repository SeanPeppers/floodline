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
    hud.hidden = !inKeyWest;
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

  // Tour: one button plays the whole story once as a continuous glide, like a
  // video: the scroll never stops between chapters. It opens with a short
  // intro card, ends with a recap, then glides on to the results. It drives the same native scroll
  // position, so the stage, water level and HUD follow exactly as they do by
  // hand. Any wheel, touch, click or key press hands control back.
  const MIN_CHAPTER_MS = 6000;  // time to pass one chapter, scaled by its word count
  const MAX_CHAPTER_MS = 14000;
  const WORDS_PER_SEC = 3.5;
  const INTRO_MS = 12000;       // how long the intro card stays up before the tour moves
  const SUMMARY_MS = 14000;     // how long the recap stays up before moving on
  const chapterMs = chapters.map((c) => {
    const words = (c.querySelector(".chapter__card")?.textContent || "").trim().split(/\s+/).length;
    return Math.min(MAX_CHAPTER_MS, Math.max(MIN_CHAPTER_MS, (words / WORDS_PER_SEC) * 1000));
  });
  const U0 = 0.5, U1 = N - 0.5; // first and last chapter centres
  // Scroll position that puts chapter coordinate u mid-screen (inverse of chapterCoord).
  const yForU = (u) => {
    const i = Math.max(0, Math.min(N - 1, Math.floor(u)));
    return Math.max(0, tops[i] + (u - i) * heights[i] - window.innerHeight / 2);
  };
  const jumpTo = (u) => window.scrollTo({ top: yForU(u), behavior: "instant" });

  // Two cards: an intro before the tour ("what you're about to watch") and a
  // recap after it. Each holds for a while with a progress bar, then moves on.
  const card = (id, ms) => {
    const el = document.getElementById(id);
    return el && { el, ms, bar: el.querySelector(".tour-summary__bar span"), go: el.querySelector(".tour-summary__go") };
  };
  const intro = card("tour-intro", INTRO_MS);
  const recap = card("tour-summary", SUMMARY_MS);
  const RESULTS_URL = "simple.html";

  const tourBtn = document.createElement("button");
  tourBtn.type = "button";
  tourBtn.className = "tour-btn";
  const setLabel = (on) => {
    tourBtn.textContent = on ? "❚❚ Stop tour" : "▶ Play tour";
    tourBtn.setAttribute("aria-pressed", String(on));
  };
  setLabel(false);
  document.body.appendChild(tourBtn);

  let running = false, rafId = 0, tourU = U0, last = 0, phase = "play", cardT = 0;
  function showCard(c, on) {
    if (!c) return;
    c.el.hidden = !on;
    // Add the class a frame after unhiding so the fade-in transition runs.
    if (on) requestAnimationFrame(() => c.el.classList.add("is-on"));
    else c.el.classList.remove("is-on");
    if (c.bar) c.bar.style.width = "0%";
    // Hide the chapter cards while a tour card is up, so the two never overlap.
    document.body.classList.toggle("tour-card-open", [intro, recap].some((x) => x && !x.el.hidden));
  }
  function hideCards() { showCard(intro, false); showCard(recap, false); }
  function beginPlay() {
    showCard(intro, false);
    phase = "play";
    jumpTo(tourU);
  }
  function goToResults() {
    stopTour();
    location.href = RESULTS_URL;
  }
  function step(now) {
    if (!running) return;
    const dt = Math.min(100, now - last); // cap so a background tab doesn't leap ahead
    last = now;
    if (phase === "play") {
      tourU = Math.min(U1, tourU + dt / chapterMs[Math.min(N - 1, Math.floor(tourU))]);
      jumpTo(tourU);
      if (tourU >= U1) {
        if (!recap) return goToResults();
        phase = "recap"; cardT = 0; showCard(recap, true);
      }
    } else {
      const c = phase === "intro" ? intro : recap;
      cardT += dt;
      if (c.bar) c.bar.style.width = `${Math.min(100, (cardT / c.ms) * 100)}%`;
      if (cardT >= c.ms) {
        if (phase === "intro") beginPlay();
        else return goToResults();
      }
    }
    rafId = requestAnimationFrame(step);
  }
  function startTour(fromOpening = false) {
    measure();
    const u = chapterCoord();
    tourU = fromOpening || u >= U1 - 0.01 || u < U0 ? U0 : u;
    hideCards();
    running = true;
    setLabel(true);
    jumpTo(tourU);
    // Starting from the top: show the intro first.
    if (intro && (fromOpening || u < U0 + 0.15)) { phase = "intro"; cardT = 0; showCard(intro, true); }
    else phase = "play";
    last = performance.now();
    rafId = requestAnimationFrame(step);
  }
  function stopTour() {
    running = false;
    cancelAnimationFrame(rafId);
    hideCards();
    setLabel(false);
  }
  tourBtn.addEventListener("click", () => (running ? stopTour() : startTour()));
  intro?.go?.addEventListener("click", () => { if (running && phase === "intro") beginPlay(); });
  intro?.el.querySelector(".tour-summary__skip")?.addEventListener("click", stopTour);
  recap?.go?.addEventListener("click", goToResults);
  const inCard = (t) => [intro, recap].some((c) => c && c.el.contains(t));
  const takeOver = (e) => {
    if (running && !tourBtn.contains(e.target) && !inCard(e.target)) stopTour();
  };
  for (const ev of ["wheel", "touchstart", "pointerdown", "keydown"]) window.addEventListener(ev, takeOver, { passive: true });
  new IntersectionObserver(([e]) => { tourBtn.hidden = !e.isIntersecting && !running; }).observe(journey);

  // 3-D only with motion allowed, data not constrained, and a WebGL2 context.
  function webgl2() {
    try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; }
  }
  const can3d = !(reduceMotion || saveData || !webgl2());

  // Opening, on a fresh visit to the top of the page: deep space with the name
  // and a Start button. Start flies in to the Irma view, then the intro card,
  // then the tour. During the fly-in any click, scroll or key skips ahead.
  const OPEN_FROM = 400;        // camera altitude multiplier at the start
  const OPEN_MS = 6500;         // fly-in duration
  const OPEN_WAIT_MS = 7000;    // stop waiting for the 3-D globe after this
  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const titleEl = document.getElementById("opening-title");
  let opening = !!titleEl && window.scrollY < 40 && !location.hash && !reduceMotion;
  let phase0 = "wait", live3d = false, openT0 = 0, openRaf = 0, openTimer = 0;
  const cls = document.body.classList;
  function finishOpening() {
    if (!opening) return;
    opening = false;
    cancelAnimationFrame(openRaf);
    clearTimeout(openTimer);
    state.zoomOut = 1;
    titleEl.hidden = true;
    cls.remove("is-opening", "is-opening-wait", "is-opening-title");
    startTour(true); // shows the intro card, then plays the tour
  }
  function flyIn(now) {
    if (!opening) return;
    if (!openT0) openT0 = now;
    const t = Math.min(1, (now - openT0) / OPEN_MS);
    state.zoomOut = Math.exp(Math.log(OPEN_FROM) * (1 - easeInOut(t)));
    if (t >= 1) return finishOpening();
    openRaf = requestAnimationFrame(flyIn);
  }
  function showTitle() {
    if (!opening || phase0 !== "wait") return;
    phase0 = "title";
    clearTimeout(openTimer);
    if (live3d) cls.remove("is-opening-wait"); // stars and a far-off Earth behind the name
    cls.add("is-opening-title");
    titleEl.hidden = false;
    requestAnimationFrame(() => titleEl.classList.add("is-on"));
    titleEl.querySelector(".opening-title__go")?.focus({ preventScroll: true });
  }
  function beginFlyIn() {
    if (!opening || phase0 !== "title") return;
    phase0 = "fly";
    titleEl.classList.remove("is-on");
    cls.remove("is-opening-title");
    setTimeout(() => { titleEl.hidden = true; }, 600);
    if (live3d) { openRaf = requestAnimationFrame(flyIn); return; }
    // No 3-D: fade the still image in, then the intro card.
    cls.remove("is-opening-wait");
    openTimer = setTimeout(finishOpening, 1200);
  }
  function openingReady() {
    live3d = true;
    if (!opening) return;
    if (phase0 === "wait") showTitle();
    else if (phase0 === "title") cls.remove("is-opening-wait");
  }
  if (opening) {
    state.zoomOut = OPEN_FROM;
    cls.add("is-opening", "is-opening-wait"); // black until the globe is up
    openTimer = setTimeout(showTitle, can3d ? OPEN_WAIT_MS : 300);
    titleEl.querySelector(".opening-title__go")?.addEventListener("click", beginFlyIn);
    const skip = (e) => {
      if (!opening || tourBtn.contains(e.target)) return;
      if (phase0 === "fly") finishOpening();
      else if (phase0 === "title" && e.type === "keydown" && (e.key === "Enter" || e.key === " ") && !titleEl.contains(e.target)) beginFlyIn();
    };
    for (const ev of ["wheel", "touchstart", "pointerdown", "keydown"]) window.addEventListener(ev, skip, { passive: true });
  }

  if (!can3d) return;

  const start = () => import("./scene.js")
    .then((m) => m.start(canvas, state, () => {
      stage.classList.add("is-3d");
      onScroll();
      openingReady();
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
