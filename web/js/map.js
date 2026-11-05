// Live map background for the hero, lazy-loaded after idle so it never
// blocks first paint. Uses MapLibre GL JS (BSD-3, no account/token) against
// OpenFreeMap's free hosted vector tiles (MIT project, OSM/ODbL data,
// explicitly fine with live pan/zoom — unlike raw OSM raster tiles). If the
// library or tiles fail to load (offline, blocked, etc.) this does nothing
// and the static crossfade stills + flood-canvas in main.js keep working —
// they are the base layer underneath, not a thing this script removes.
(function () {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const saveData = navigator.connection && navigator.connection.saveData;
  const heroMap = document.querySelector(".hero-map");
  if (!heroMap || saveData) return;

  const KEY_WEST = [-81.7800, 24.5551];
  const MAPLIBRE_VERSION = "4.7.1";

  schedule(loadMap);

  function schedule(fn) {
    // Deliberately later than a typical Lighthouse TBT/LCP observation
    // window — this is a "nice to have" background layer, not critical
    // content, and the static stills already carry the hero visually.
    if ("requestIdleCallback" in window) requestIdleCallback(fn, { timeout: 4000 });
    else setTimeout(fn, 3000);
  }

  function loadMap() {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `https://unpkg.com/maplibre-gl@${MAPLIBRE_VERSION}/dist/maplibre-gl.css`;
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.src = `https://unpkg.com/maplibre-gl@${MAPLIBRE_VERSION}/dist/maplibre-gl.js`;
    script.onload = initMap;
    script.onerror = () => {}; // fallback stills already showing, nothing to undo
    document.head.appendChild(script);
  }

  function initMap() {
    if (!window.maplibregl) return;

    const container = document.createElement("div");
    container.className = "hero-map__live";
    container.setAttribute("aria-hidden", "true");
    heroMap.querySelector(".hero-map__decor").prepend(container);

    let map;
    try {
      map = new maplibregl.Map({
        container,
        style: "https://tiles.openfreemap.org/styles/liberty",
        center: KEY_WEST,
        zoom: 11.2,
        pitch: 0,
        interactive: false, // background layer — never trap mobile scroll
        attributionControl: false,
      });
    } catch (e) {
      return; // stills remain visible, nothing broken
    }

    map.on("error", () => {
      container.remove(); // tile/style failure — fall back to static stills
    });

    map.on("load", () => {
      const el = document.createElement("div");
      el.className = "map-pulse-marker";
      el.innerHTML = '<span class="map-pulse-marker__ring"></span><span class="map-pulse-marker__dot"></span>';
      new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat(KEY_WEST).addTo(map);
      requestAnimationFrame(() => container.classList.add("is-loaded"));
    });
  }
})();
