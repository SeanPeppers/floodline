// Key West's real road network as a still-water flood layer.
//   loadStreets()  one lazy fetch of assets/data/streets.json (OSM centrelines,
//                  one ~30 m piece per USGS 3DEP sample, built by web_data.py)
//   attach(api)    called by scene.js once the terrain exists: draws the pieces
//                  as ribbons on the terrain, red where the bathtub level is at
//                  or above the road, amber within 15 cm of it, and keeps a
//                  "% of road points under water" count in the HUD.
// It also writes that share into each Key West chapter card, so the number is
// there without WebGL (stills, reduced motion) and for screen readers.
const FT_PER_M = 0.3048;
const AMBER_M = 0.15;

let streetsPromise = null;
export function loadStreets() {
  streetsPromise ??= fetch("assets/data/streets.json")
    .then((r) => {
      if (!r.ok) throw new Error(`streets.json: ${r.status}`);
      return r.json();
    })
    .then(decode)
    .catch((e) => {
      streetsPromise = null; // allow a later retry
      throw e;
    });
  return streetsPromise;
}

// -> { pieces: [{ way, name, z (ft NAVD88), a, s, b: [lon, lat] }], sortedM, names, meta }
function decode(d) {
  const [lon0, lat0] = d.origin_lonlat;
  const pieces = [];
  d.ways.forEach(([nameIdx, deltas, elev], way) => {
    const v = [];
    let x = 0, y = 0;
    for (let i = 0; i < deltas.length; i += 2) {
      x += deltas[i];
      y += deltas[i + 1];
      v.push([lon0 + x / d.q_per_deg, lat0 + y / d.q_per_deg]);
    }
    // v = [start, samples..., end]; piece k runs from the midpoint before sample k to the one after.
    const mid = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
    elev.forEach((e, k) => {
      if (e === null) return;
      const s = v[k + 1];
      pieces.push({
        way, name: d.names[nameIdx], z: e / 100, s,
        a: k === 0 ? v[0] : mid(v[k], s),
        b: k === elev.length - 1 ? v[v.length - 1] : mid(s, v[k + 2]),
      });
    });
  });
  const sortedM = Float64Array.from(pieces, (p) => p.z * FT_PER_M).sort();
  return { pieces, sortedM, names: d.names, meta: d };
}

// Share of road points at or below a level (m NAVD88).
export function shareUnder(streets, levelM) {
  const a = streets.sortedM;
  let lo = 0, hi = a.length;
  while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] <= levelM) lo = m + 1; else hi = m; }
  return lo / a.length;
}
export const pct = (x) => (x < 0.001 && x > 0 ? "<0.1" : (x * 100).toFixed(1));

// ---------- chapter cards ----------
(function annotateChapters() {
  const cards = [...document.querySelectorAll('.chapter[data-scene="keywest"]')];
  if (!cards.length) return;
  const run = () => Promise.all([loadStreets(), window.FloodlineData.derived]).then(([streets, d]) => {
    const mhhwM = streets.meta.mhhw_navd_m;
    for (const c of cards) {
      const lvl = c.dataset.levelM ? Number(c.dataset.levelM) : d.levels[c.dataset.level];
      if (lvl === undefined || Number.isNaN(lvl)) continue;
      const p = c.querySelector(".chapter__roads") || c.querySelector(".chapter__card").appendChild(document.createElement("p"));
      p.className = "chapter__roads";
      p.textContent = `${pct(shareUnder(streets, mhhwM + lvl))}% of ${streets.pieces.length.toLocaleString("en-US")} road points under water at this level (bathtub fill).`;
    }
  }).catch((e) => console.error("Floodline: road layer unavailable", e));
  // Lazy: only once the reader is about a screen away from Key West.
  const io = new IntersectionObserver((es) => {
    if (es.some((e) => e.isIntersecting)) { io.disconnect(); run(); }
  }, { rootMargin: "100% 0px" });
  io.observe(cards[0]);
})();

// ---------- 3-D layer ----------
const VERT = /* glsl */ `
  attribute float aH;          // road elevation, m NAVD88
  uniform float uLevel;
  uniform float uScale;
  varying float vH;
  varying float vDist;
  float disp(float h) { return (h < 3.0 ? h : 3.0 + (h - 3.0) * 0.15) * uScale; }
  void main() {
    vH = aH;
    vec3 p = position;
    p.y = disp(max(aH, uLevel)) + 0.004;
    vec4 w = modelMatrix * vec4(p, 1.0);
    vDist = length(w.xyz - cameraPosition);
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;
const FRAG = /* glsl */ `
  uniform float uLevel;
  uniform vec2 uFog;
  varying float vH;
  varying float vDist;
  void main() {
    float under = step(vH, uLevel);
    float near = (1.0 - under) * step(vH, uLevel + ${AMBER_M.toFixed(2)});
    vec3 col = mix(vec3(0.92, 0.94, 0.96), vec3(1.0, 0.68, 0.12), near);
    col = mix(col, vec3(0.95, 0.16, 0.12), under);
    float a = mix(0.22, 0.95, max(under, near)) * (1.0 - smoothstep(uFog.x, uFog.y, vDist));
    gl_FragColor = vec4(col, a);
    #include <colorspace_fragment>
  }
`;

export function attach({ THREE, scene, uniforms, toLocal }) {
  const hud = document.querySelector(".journey__hud");
  let counter = hud && hud.querySelector(".journey__hud-roads");
  if (hud && !counter) {
    counter = document.createElement("span");
    counter.className = "journey__hud-roads";
    hud.appendChild(counter);
  }
  return loadStreets().then((streets) => {
    const W = 0.016; // ribbon width, km (16 m) in the scene's km units
    const n = streets.pieces.length * 2; // two straight sub-segments per piece
    const pos = new Float32Array(n * 4 * 3), aH = new Float32Array(n * 4), idx = new Uint32Array(n * 6);
    const pa = new THREE.Vector3(), pb = new THREE.Vector3();
    let q = 0;
    const quad = (a, b, h) => {
      pa.copy(toLocal(a[1], a[0]));
      pb.copy(toLocal(b[1], b[0]));
      const dx = pb.x - pa.x, dz = pb.z - pa.z, l = Math.hypot(dx, dz) || 1;
      const ox = (-dz / l) * W / 2, oz = (dx / l) * W / 2;
      const v = [pa.x + ox, pa.z + oz, pa.x - ox, pa.z - oz, pb.x + ox, pb.z + oz, pb.x - ox, pb.z - oz];
      for (let i = 0; i < 4; i++) {
        pos.set([v[2 * i], 0, v[2 * i + 1]], (q * 4 + i) * 3);
        aH[q * 4 + i] = h;
      }
      idx.set([0, 1, 2, 2, 1, 3].map((j) => j + q * 4), q * 6);
      q++;
    };
    for (const p of streets.pieces) {
      const h = p.z * FT_PER_M;
      quad(p.a, p.s, h);
      quad(p.s, p.b, h);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("aH", new THREE.BufferAttribute(aH, 1));
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    const mat = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, depthTest: false, side: THREE.DoubleSide,
      uniforms: { uLevel: uniforms.uLevel, uScale: uniforms.uScale, uFog: uniforms.uFog },
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.frustumCulled = false;
    mesh.renderOrder = 2;
    // The scene's own frame loop drives this: no second rAF.
    let shown = "";
    mesh.onBeforeRender = () => {
      if (!counter) return;
      const text = `${pct(shareUnder(streets, uniforms.uLevel.value))}% of road points under water`;
      if (text !== shown) counter.textContent = shown = text;
    };
    scene.add(mesh);
  }).catch((e) => console.error("Floodline: road layer unavailable", e));
}
