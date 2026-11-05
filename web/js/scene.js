// The 3-D stage, lazy-loaded by story.js after first paint. Two scenes share
// one renderer:
//   globe   - NASA Blue Marble with the real Suomi NPP VIIRS cloud field of
//             10 Sep 2017 (Hurricane Irma) on stacked shells; the camera
//             spirals around the eye and dives toward Key West.
//   keywest - NOAA CUDEM topobathy with USGS/USDA NAIP imagery draped on it,
//             flooded "bathtub" style to the level story.js derives from the
//             model's NWS thresholds (results.json).
// Only the imagery and terrain are assets; everything else is shader code.
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.187.0/+esm";

const D2R = Math.PI / 180;
// Eye of Irma in the VIIRS frame (read off the image, ~0.05 deg).
const EYE = { lat: 25.83, lon: -81.72 };
// NOAA CO-OPS 8724580 metadata.
const GAUGE = { lat: 24.5557, lon: -81.8079 };
// The bbox both Key West rasters were exported with (scripts in CREDITS.md).
const KW_BBOX = { w: -81.82, s: 24.535, e: -81.72, n: 24.59 };
const IRMA_BBOX = { w: -96, s: 12, e: -64, n: 38 };
// MHHW - NAVD88 at the gauge, from data/keywest_datums.json (1.941 - 1.928 m).
const MHHW_NAVD88 = 0.013;
// Must match the encoder in CREDITS.md: piecewise-linear 8-bit height code.
const DEM_KNOTS_M = [-14, -1, 4, 30];
const DEM_KNOTS_CODE = [0, 20, 220, 255];

const KM_PER_DEG_LAT = 110.6;
const KW_W = (KW_BBOX.e - KW_BBOX.w) * 111.32 * Math.cos(((KW_BBOX.s + KW_BBOX.n) / 2) * D2R);
const KW_D = (KW_BBOX.n - KW_BBOX.s) * KM_PER_DEG_LAT;
const kwLocal = (lat, lon) => new THREE.Vector3(
  ((lon - KW_BBOX.w) / (KW_BBOX.e - KW_BBOX.w) - 0.5) * KW_W, 0,
  -((lat - KW_BBOX.s) / (KW_BBOX.n - KW_BBOX.s) - 0.5) * KW_D,
);

function latLon(lat, lon, r = 1) {
  const la = lat * D2R, lo = lon * D2R;
  return new THREE.Vector3(r * Math.cos(la) * Math.cos(lo), r * Math.sin(la), -r * Math.cos(la) * Math.sin(lo));
}

const smooth = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
const lerp = (a, b, t) => a + (b - a) * t;

// Keyframes at chapter coordinates; position is log-interpolated in altitude.
function sampleKeys(keys, u) {
  if (u <= keys[0].u) return keys[0];
  for (let i = 1; i < keys.length; i++) {
    const a = keys[i - 1], b = keys[i];
    if (u <= b.u) {
      const t = smooth(a.u, b.u, u);
      const o = {};
      for (const k of Object.keys(a)) o[k] = k === "alt" || k === "dist" ? Math.exp(lerp(Math.log(a[k]), Math.log(b[k]), t)) : lerp(a[k], b[k], t);
      return o;
    }
  }
  return keys[keys.length - 1];
}

const OUTPUT = /* glsl */ `
  #include <colorspace_fragment>
`;

const CLOUD_GLSL = /* glsl */ `
  uniform sampler2D uCloudG;
  uniform sampler2D uCloudR;
  uniform vec4 uRegion;   // w, s, e, n in degrees
  uniform vec2 uEye;      // lon, lat in degrees
  uniform float uSpin;
  const float PI = 3.141592653589793;
  vec2 lonLatDeg(vec3 n) { return vec2(atan(-n.z, n.x), asin(clamp(n.y, -1.0, 1.0))) * (180.0 / PI); }
  float cloudiness(vec3 c) {
    float lo = min(min(c.r, c.g), c.b), hi = max(max(c.r, c.g), c.b);
    return smoothstep(0.17, 0.52, lo) * (1.0 - smoothstep(0.10, 0.30, hi - lo));
  }
  // Raw sRGB cloud colour (not linearised) and cloudiness, with the storm
  // turned cyclonically about its eye by uSpin radians (fading out by ~8 deg).
  vec4 cloudAt(vec2 ll) {
    vec2 d = ll - uEye;
    float cl = cos(radians(uEye.y));
    d.x *= cl;
    float a = -uSpin * (1.0 - smoothstep(4.0, 11.0, length(d)));
    d = mat2(cos(a), sin(a), -sin(a), cos(a)) * d;
    d.x /= cl;
    ll = uEye + d;
    vec3 g = texture2D(uCloudG, vec2((ll.x + 180.0) / 360.0, (ll.y + 90.0) / 180.0)).rgb;
    vec2 ur = (ll - uRegion.xy) / (uRegion.zw - uRegion.xy);
    float inR = smoothstep(0.0, 0.08, ur.x) * smoothstep(1.0, 0.92, ur.x) * smoothstep(0.0, 0.08, ur.y) * smoothstep(1.0, 0.92, ur.y);
    vec3 c = mix(g, texture2D(uCloudR, clamp(ur, 0.0, 1.0)).rgb, inR);
    return vec4(c, cloudiness(c));
  }
`;

const SPHERE_VERT = /* glsl */ `
  varying vec3 vN;
  varying vec3 vWorld;
  void main() {
    vN = normalize(position);
    vec4 w = modelMatrix * vec4(position, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

const EARTH_FRAG = /* glsl */ `
  uniform sampler2D uDay;
  uniform vec3 uSun;
  varying vec3 vN;
  varying vec3 vWorld;
  ${CLOUD_GLSL}
  void main() {
    vec3 n = normalize(vN);
    vec2 ll = lonLatDeg(n);
    vec3 day = texture2D(uDay, vec2((ll.x + 180.0) / 360.0, (ll.y + 90.0) / 180.0)).rgb;
    // Inside the Irma frame, clear-sky VIIRS pixels are a sharper photo of the
    // same ground than the global Blue Marble; use them where there's no cloud.
    vec2 ur = (ll - uRegion.xy) / (uRegion.zw - uRegion.xy);
    float inR = smoothstep(0.0, 0.05, ur.x) * smoothstep(1.0, 0.95, ur.x) * smoothstep(0.0, 0.05, ur.y) * smoothstep(1.0, 0.95, ur.y);
    vec3 vi = texture2D(uCloudR, clamp(ur, 0.0, 1.0)).rgb;
    day = mix(day, pow(vi, vec3(2.2)) * 1.15, inR * (1.0 - smoothstep(0.03, 0.2, cloudiness(vi))) * 0.85);
    float ndl = dot(n, uSun);
    vec3 V = normalize(cameraPosition - vWorld);
    float ocean = smoothstep(0.004, 0.03, day.b - max(day.r, day.g));
    vec3 H = normalize(uSun + V);
    float spec = pow(max(dot(n, H), 0.0), 70.0) * ocean * 0.55;
    // cloud shadow: sample the cloud field a little toward the sun
    float shade = 1.0 - 0.5 * cloudAt(ll + vec2(-0.12, -0.04)).a;
    vec3 col = day * (max(ndl, 0.0) * 1.1 + 0.015) * shade + spec * vec3(1.0, 0.92, 0.8) * shade;
    float fres = pow(max(1.0 - max(dot(n, V), 0.0), 0.0), 3.0);
    col = mix(col, vec3(0.32, 0.55, 1.0) * clamp(ndl + 0.25, 0.0, 1.0), fres * 0.65);
    gl_FragColor = vec4(col, 1.0);
    ${OUTPUT}
  }
`;

const CLOUD_FRAG = /* glsl */ `
  uniform vec3 uSun;
  uniform float uLo;
  uniform float uHi;
  uniform float uOpacity;
  uniform float uTone;
  varying vec3 vN;
  varying vec3 vWorld;
  ${CLOUD_GLSL}
  void main() {
    vec3 n = normalize(vN);
    vec4 c = cloudAt(lonLatDeg(n));
    float a = smoothstep(uLo, uHi, c.a) * uOpacity;
    if (a < 0.004) discard;
    float ndl = dot(n, uSun);
    vec3 col = pow(c.rgb, vec3(2.2)) * uTone * (0.06 + smoothstep(-0.1, 0.5, ndl));
    gl_FragColor = vec4(col, a);
    ${OUTPUT}
  }
`;

const ATMO_FRAG = /* glsl */ `
  uniform vec3 uSun;
  varying vec3 vN;
  varying vec3 vWorld;
  void main() {
    vec3 V = normalize(cameraPosition - vWorld);
    float rim = pow(max(0.0, 1.0 - abs(dot(normalize(vN), V))), 2.2);
    float lit = clamp(dot(normalize(vN), uSun) + 0.35, 0.0, 1.0);
    gl_FragColor = vec4(vec3(0.3, 0.55, 1.0) * rim * lit * 1.4, rim * lit);
    ${OUTPUT}
  }
`;

const TERRAIN_VERT = /* glsl */ `
  attribute float aH;          // metres NAVD88
  uniform float uLevel;        // metres NAVD88
  uniform float uScale;        // exaggeration / 1000 (km per metre)
  varying vec2 vUv;
  varying vec3 vWorld;
  varying vec3 vNormal;
  float disp(float h) { return (h < 3.0 ? h : 3.0 + (h - 3.0) * 0.15) * uScale; }
  void main() {
    vUv = uv;
    vec3 p = position;
    p.y = disp(max(aH, uLevel));
    vNormal = aH < uLevel ? vec3(0.0, 1.0, 0.0) : normal;
    vec4 w = modelMatrix * vec4(p, 1.0);
    vWorld = w.xyz;
    gl_Position = projectionMatrix * viewMatrix * w;
  }
`;

const TERRAIN_FRAG = /* glsl */ `
  uniform sampler2D uOrtho;
  uniform sampler2D uDem;
  uniform sampler2D uNormals;
  uniform float uLevel;
  uniform float uMhhw;
  uniform float uTime;
  uniform vec3 uSun;
  uniform vec3 uSeaColor;
  uniform vec3 uFogColor;
  uniform vec3 uSkyColor;
  uniform vec2 uFog;
  uniform vec3 uGauge;
  uniform float uOuter;        // 1 on the open-sea plane outside the tile
  uniform float uGloom;        // storm overcast, 0..1 (follows the rain)
  uniform vec3 uDeepColor;
  varying vec2 vUv;
  varying vec3 vWorld;
  varying vec3 vNormal;

  float decode(float c) {
    if (c < 20.0) return mix(-14.0, -1.0, c / 20.0);
    if (c < 220.0) return mix(-1.0, 4.0, (c - 20.0) / 200.0);
    return mix(4.0, 30.0, (c - 220.0) / 35.0);
  }

  void main() {
    float inTile = (1.0 - uOuter) * smoothstep(0.0, 0.07, vUv.x) * smoothstep(1.0, 0.93, vUv.x) * smoothstep(0.0, 0.1, vUv.y) * smoothstep(1.0, 0.9, vUv.y);
    float h = uOuter > 0.5 ? -10.0 : decode(texture2D(uDem, vUv).r * 255.0);
    // Outside the data tile: sea stays sea, land fades to a neutral "no data" tone.
    // Open sea deepens away from the tile (the reef line and the Straits lie south).
    float off = length(max(abs(vWorld.xz) - vec2(5.0, 3.0), 0.0));
    vec3 sea = mix(uSeaColor, uDeepColor, smoothstep(0.5, 9.0, off));
    vec3 outside = mix(sea, vec3(0.05, 0.055, 0.06), step(uMhhw, h) * (1.0 - uOuter));
    vec3 base = mix(outside, texture2D(uOrtho, vUv).rgb, inTile);
    float lam = 0.62 + 0.5 * max(dot(normalize(vNormal), uSun), 0.0);
    vec3 col = base * lam;

    float depth = uLevel - h;
    float wet = smoothstep(-0.004, 0.006, depth);
    float newWater = wet * smoothstep(uMhhw - 0.01, uMhhw + 0.03, h);   // dry at MHHW, flooded now

    vec2 q = vWorld.xz;
    vec3 n1 = texture2D(uNormals, q * 0.9 + uTime * vec2(0.021, 0.013)).rgb * 2.0 - 1.0;
    vec3 n2 = texture2D(uNormals, q * 1.7 - uTime * vec2(0.017, -0.009)).rgb * 2.0 - 1.0;
    vec3 wn = normalize(vec3(n1.x + n2.x, 4.0, n1.y + n2.y));
    vec3 V = normalize(cameraPosition - vWorld);
    float fres = 0.02 + 0.98 * pow(max(1.0 - max(dot(wn, V), 0.0), 0.0), 5.0);
    float spec = pow(max(dot(reflect(-uSun, wn), V), 0.0), 90.0);

    // Newly flooded land: murky floodwater over the photo, deeper = darker.
    vec3 flood = mix(base * 0.35 + vec3(0.04, 0.16, 0.22), vec3(0.05, 0.22, 0.32), smoothstep(0.0, 0.3, depth));
    col = mix(col, flood, newWater * 0.92);
    float edge = newWater * (1.0 - smoothstep(0.0, 0.035, depth)) * (0.6 + 0.4 * n1.x);
    col += edge * vec3(0.55, 0.62, 0.62);
    col = mix(col, uSkyColor, wet * fres * 0.55);
    col += wet * spec * vec3(0.9, 0.95, 1.0) * 0.6;

    // Tide gauge 8724580: a slow amber ring, the place the data comes from.
    float gd = length(vWorld.xz - uGauge.xz);
    float ph = fract(uTime * 0.35);
    float ring = (1.0 - smoothstep(0.0, 0.018, abs(gd - (0.05 + ph * 0.5)))) * (1.0 - ph);
    col = mix(col, vec3(1.0, 0.72, 0.1), clamp(ring * 0.9 + (1.0 - smoothstep(0.02, 0.035, gd)), 0.0, 1.0));

    col = mix(col, vec3(dot(col, vec3(0.3, 0.55, 0.15))), uGloom * 0.35) * (1.0 - uGloom * 0.3);
    float f = smoothstep(uFog.x, uFog.y, length(vWorld - cameraPosition));
    col = mix(col, uFogColor, f);
    gl_FragColor = vec4(col, 1.0);
    ${OUTPUT}
  }
`;

const SKY_FRAG = /* glsl */ `
  uniform vec3 uTop;
  uniform vec3 uHorizon;
  varying vec3 vN;
  varying vec3 vWorld;
  void main() {
    float y = normalize(vN).y;
    gl_FragColor = vec4(mix(uHorizon, uTop, smoothstep(-0.02, 0.45, y)), 1.0);
    ${OUTPUT}
  }
`;

const RAIN_VERT = /* glsl */ `
  attribute vec3 aSeed;     // x, z in [0,1), phase
  attribute float aEnd;     // 0 = streak head, 1 = tail
  uniform float uTime;
  uniform vec3 uCentre;
  uniform vec3 uBox;
  varying float vA;
  void main() {
    vec3 wind = vec3(0.35, -1.0, 0.12);
    float y = fract(aSeed.z - uTime * 0.55) * uBox.y;
    vec3 p = uCentre + vec3((aSeed.x - 0.5) * uBox.x, y - uBox.y * 0.5, (aSeed.y - 0.5) * uBox.z);
    p -= wind * aEnd * 0.035 * uBox.y;
    vA = 1.0 - aEnd;
    gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
  }
`;
const RAIN_FRAG = /* glsl */ `
  uniform float uRain;
  varying float vA;
  void main() {
    gl_FragColor = vec4(vec3(0.78, 0.84, 0.9), (0.18 + 0.2 * vA) * uRain);
    ${OUTPUT}
  }
`;

function loadTexture(loader, url, { srgb = true, repeat = false } = {}) {
  return loader.loadAsync(url).then((t) => {
    t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
    t.anisotropy = 4;
    if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
    return t;
  });
}

function imagePixels(img) {
  const c = document.createElement("canvas");
  c.width = img.width;
  c.height = img.height;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(img, 0, 0);
  return ctx.getImageData(0, 0, img.width, img.height);
}

const decodeHeight = (code) => {
  for (let i = 1; i < DEM_KNOTS_CODE.length; i++) {
    if (code <= DEM_KNOTS_CODE[i]) {
      const t = (code - DEM_KNOTS_CODE[i - 1]) / (DEM_KNOTS_CODE[i] - DEM_KNOTS_CODE[i - 1]);
      return lerp(DEM_KNOTS_M[i - 1], DEM_KNOTS_M[i], t);
    }
  }
  return DEM_KNOTS_M[DEM_KNOTS_M.length - 1];
};

export function start(canvas, state, onReady, onUnavailable) {
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: !coarse, powerPreference: "high-performance" });
  // Fixed for the session: adaptive DPR resizes the buffer and flashes black.
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, coarse ? 1.5 : 1.75));
  renderer.setClearColor(0x04070d);
  const loader = new THREE.TextureLoader();
  const t0 = performance.now();
  const sunGlobe = latLon(4.9, -103.5).normalize(); // subsolar point near 19 UTC, 10 Sep 2017

  // ---------- globe ----------
  const globe = new THREE.Scene();
  const camG = new THREE.PerspectiveCamera(38, 1, 0.0005, 20);
  const cloudUniforms = {
    uCloudG: { value: null }, uCloudR: { value: null },
    uRegion: { value: new THREE.Vector4(IRMA_BBOX.w, IRMA_BBOX.s, IRMA_BBOX.e, IRMA_BBOX.n) },
    uEye: { value: new THREE.Vector2(EYE.lon, EYE.lat) },
    uSpin: { value: 0 },
    uSun: { value: sunGlobe },
  };
  const earthMat = new THREE.ShaderMaterial({ vertexShader: SPHERE_VERT, fragmentShader: EARTH_FRAG, uniforms: { ...cloudUniforms, uDay: { value: null } } });
  globe.add(new THREE.Mesh(new THREE.SphereGeometry(1, 160, 96), earthMat));
  // Base shell carries the image; two thin upper shells only where the cloud is
  // dense, darker, so cloud tops get depth at grazing angles without ghosting.
  const shells = [[1.006, 0.0, 0.6, 0.95, 1.0], [1.0078, 0.55, 0.9, 0.4, 0.92], [1.0094, 0.75, 1.0, 0.3, 0.86]].map(([r, lo, hi, op, tone]) => {
    const m = new THREE.ShaderMaterial({
      vertexShader: SPHERE_VERT, fragmentShader: CLOUD_FRAG, transparent: true, depthWrite: false,
      uniforms: { ...cloudUniforms, uLo: { value: lo }, uHi: { value: hi }, uOpacity: { value: op }, uTone: { value: tone } },
    });
    const mesh = new THREE.Mesh(new THREE.SphereGeometry(r, 160, 96), m);
    globe.add(mesh);
    return mesh;
  });
  globe.add(new THREE.Mesh(new THREE.SphereGeometry(1.028, 96, 64), new THREE.ShaderMaterial({
    vertexShader: SPHERE_VERT, fragmentShader: ATMO_FRAG, uniforms: { uSun: { value: sunGlobe } },
    side: THREE.BackSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
  })));

  const eyeN = latLon(EYE.lat, EYE.lon).normalize();
  const kwN = latLon(GAUGE.lat, GAUGE.lon).normalize();
  const G = state.firstKeyWest;
  // u: chapter coordinate, as fractions of the globe chapters so adding one
  // re-spaces the flight. az in degrees (the spiral), tilt from vertical.
  const globeKeys = [
    { u: 0, alt: 2.5, tilt: 10, az: -30 },
    { u: 0.18 * G, alt: 2.15, tilt: 14, az: -10 },
    { u: 0.5 * G, alt: 0.4, tilt: 50, az: 130 },
    { u: 0.833 * G, alt: 0.3, tilt: 38, az: 260 },
    { u: 0.933 * G, alt: 0.06, tilt: 24, az: 330 },
    { u: G, alt: 0.0075, tilt: 10, az: 360 },
  ];
  const tmpN = new THREE.Vector3(), tmpE = new THREE.Vector3(), tmpNorth = new THREE.Vector3(), tmpP = new THREE.Vector3();
  function placeGlobeCamera(u) {
    const k = sampleKeys(globeKeys, u);
    tmpN.copy(eyeN).lerp(kwN, smooth(0.57 * G, G - 0.15, u)).normalize();
    tmpE.set(tmpN.z, 0, -tmpN.x).normalize(); // east at this point
    tmpNorth.crossVectors(tmpN, tmpE).normalize();
    const az = k.az * D2R, tilt = k.tilt * D2R;
    tmpP.copy(tmpN).multiplyScalar(Math.cos(tilt))
      .addScaledVector(tmpNorth, -Math.cos(az) * Math.sin(tilt))
      .addScaledVector(tmpE, Math.sin(az) * Math.sin(tilt))
      .multiplyScalar(k.alt).add(tmpN);
    camG.position.copy(tmpP);
    camG.up.copy(tmpN);
    camG.lookAt(tmpN);
    camG.near = Math.max(0.0004, (k.alt - 0.02) * 0.4);
    camG.updateProjectionMatrix();
  }

  // ---------- Key West ----------
  const kw = new THREE.Scene();
  const camK = new THREE.PerspectiveCamera(40, 1, 0.02, 80);
  const skyTop = new THREE.Color(0x2b3644), skyHorizon = new THREE.Color(0x8a96a2);
  const sunKw = new THREE.Vector3(-0.35, 0.82, 0.45).normalize();
  const terrainUniforms = {
    uOrtho: { value: null }, uDem: { value: null }, uNormals: { value: null },
    uLevel: { value: MHHW_NAVD88 }, uMhhw: { value: MHHW_NAVD88 }, uTime: { value: 0 },
    uScale: { value: state.exaggeration / 1000 }, uSun: { value: sunKw },
    uSeaColor: { value: new THREE.Color(0x3aaea8) },
    uFogColor: { value: skyHorizon.clone() },
    uSkyColor: { value: new THREE.Color(0xb6c2cc) },
    uFog: { value: new THREE.Vector2(7, 32) },
    uGauge: { value: kwLocal(GAUGE.lat, GAUGE.lon) },
    uOuter: { value: 0 },
    uGloom: { value: 0 },
    uDeepColor: { value: new THREE.Color(0x1d5f78) },
  };
  kw.add(new THREE.Mesh(new THREE.SphereGeometry(60, 32, 16), new THREE.ShaderMaterial({
    vertexShader: SPHERE_VERT, fragmentShader: SKY_FRAG, side: THREE.BackSide, depthWrite: false,
    uniforms: { uTop: { value: skyTop.clone() }, uHorizon: { value: skyHorizon.clone() } },
  })));
  const rainCount = coarse ? 1400 : 3500;
  const rainGeo = new THREE.BufferGeometry();
  const seeds = new Float32Array(rainCount * 6), ends = new Float32Array(rainCount * 2);
  for (let i = 0; i < rainCount; i++) {
    const s = [Math.random(), Math.random(), Math.random()];
    seeds.set(s, i * 6);
    seeds.set(s, i * 6 + 3);
    ends[i * 2 + 1] = 1;
  }
  rainGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(rainCount * 6), 3));
  rainGeo.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 3));
  rainGeo.setAttribute("aEnd", new THREE.BufferAttribute(ends, 1));
  const rainMat = new THREE.ShaderMaterial({
    vertexShader: RAIN_VERT, fragmentShader: RAIN_FRAG, transparent: true, depthWrite: false,
    uniforms: { uTime: { value: 0 }, uRain: { value: 0 }, uCentre: { value: new THREE.Vector3() }, uBox: { value: new THREE.Vector3(5, 3, 5) } },
  });
  const rain = new THREE.LineSegments(rainGeo, rainMat);
  rain.frustumCulled = false;
  kw.add(rain);

  const kwTarget = kwLocal(24.5565, -81.789);
  const kwKeys = [
    { u: G, dist: 10, tilt: 6, az: 0 },
    { u: G + 0.5, dist: 7.2, tilt: 50, az: -22 },
    { u: G + 1.5, dist: 5.6, tilt: 58, az: -6 },
    { u: G + 2.5, dist: 5.2, tilt: 61, az: 10 },
    { u: G + 3.5, dist: 5.0, tilt: 63, az: 24 },
    { u: G + 4.5, dist: 5.6, tilt: 60, az: 38 },
    { u: state.N, dist: 6.0, tilt: 59, az: 42 },
  ];
  function placeKwCamera(u) {
    const k = state.debugCam ?? sampleKeys(kwKeys, u);
    const az = k.az * D2R, tilt = k.tilt * D2R;
    camK.position.set(Math.sin(az) * Math.sin(tilt), Math.cos(tilt), Math.cos(az) * Math.sin(tilt)).multiplyScalar(k.dist).add(kwTarget);
    camK.up.set(0, 1, 0);
    camK.lookAt(kwTarget);
  }

  let kwReady = false;
  function buildKeyWest([ortho, dem, normals]) {
    const narrow = Math.min(window.innerWidth, window.innerHeight) < 700;
    const segX = narrow ? 300 : 480, segY = Math.round(segX * KW_D / KW_W);
    const geo = new THREE.PlaneGeometry(KW_W, KW_D, segX, segY);
    geo.rotateX(-Math.PI / 2);
    const px = imagePixels(dem.image);
    const pos = geo.attributes.position, uv = geo.attributes.uv;
    const aH = new Float32Array(pos.count);
    for (let i = 0; i < pos.count; i++) {
      const x = Math.min(px.width - 1, Math.round(uv.getX(i) * (px.width - 1)));
      const y = Math.min(px.height - 1, Math.round((1 - uv.getY(i)) * (px.height - 1)));
      aH[i] = decodeHeight(px.data[(y * px.width + x) * 4]);
      const hm = Math.max(aH[i], MHHW_NAVD88);
      pos.setY(i, (hm < 3 ? hm : 3 + (hm - 3) * 0.15) * state.exaggeration / 1000);
    }
    geo.setAttribute("aH", new THREE.BufferAttribute(aH, 1));
    geo.computeVertexNormals();
    dem.minFilter = THREE.LinearFilter;
    dem.generateMipmaps = false;
    Object.assign(terrainUniforms, { uOrtho: { value: ortho }, uDem: { value: dem }, uNormals: { value: normals } });
    const terrainMat = new THREE.ShaderMaterial({ vertexShader: TERRAIN_VERT, fragmentShader: TERRAIN_FRAG, uniforms: terrainUniforms });
    kw.add(new THREE.Mesh(geo, terrainMat));

    // Open sea around the tile, same water shading, flat at the level.
    const sea = new THREE.PlaneGeometry(160, 160, 1, 1);
    sea.rotateX(-Math.PI / 2);
    const seaH = new Float32Array(sea.attributes.position.count).fill(-10);
    sea.setAttribute("aH", new THREE.BufferAttribute(seaH, 1));
    const seaMesh = new THREE.Mesh(sea, new THREE.ShaderMaterial({
      vertexShader: TERRAIN_VERT, fragmentShader: TERRAIN_FRAG, uniforms: { ...terrainUniforms, uOuter: { value: 1 } },
      polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 2,
    }));
    seaMesh.position.y = -0.0005;
    kw.add(seaMesh);
    kwReady = true;
  }

  // ---------- sizing, framing ----------
  let W = 0, H = 0, shiftX = 0, shiftY = 0;
  function resize() {
    const r = canvas.getBoundingClientRect();
    if (r.width === W && r.height === H) return;
    W = r.width; H = r.height;
    renderer.setSize(W, H, false);
    const aspect = W / H;
    // Wide screens: cards sit left, so push the subject right. Phones: cards
    // sit low, so lift it.
    shiftX = aspect > 1.2 && W > 900 ? 0.17 : 0;
    shiftY = aspect < 0.9 ? 0.12 : 0;
    for (const cam of [camG, camK]) {
      cam.aspect = aspect;
      const hfov = 62;
      cam.fov = aspect < 1 ? Math.min(78, 2 * Math.atan(Math.tan((hfov * D2R) / 2) / aspect) / D2R) : cam === camG ? 38 : 42;
      cam.setViewOffset(W, H, -shiftX * W, shiftY * H, W, H);
      cam.updateProjectionMatrix();
    }
  }

  let frames = 0, running = true, live = false, raf = 0;
  const setLive = (v) => { if (v !== live) { live = v; (v ? onReady : onUnavailable)(); } };
  const whiteout = canvas.parentElement.querySelector(".journey__whiteout");
  let lastWhite = -1;

  function frame() {
    raf = requestAnimationFrame(frame);
    if (!state.visible || document.hidden) return;
    resize();
    const t = (performance.now() - t0) / 1000;
    const u = state.debugU ?? state.u;
    const G0 = G;
    const inKw = u >= G0 && kwReady;
    // Key West still loading: let the stills carry the story meanwhile.
    if (frames >= 3) setLive(kwReady || u < G0);
    const w = Math.round(Math.max(0, 1 - Math.abs(u - G0) / 0.32) * 100) / 100;
    if (w !== lastWhite) { whiteout.style.opacity = String(w); lastWhite = w; }

    if (inKw) {
      placeKwCamera(u);
      terrainUniforms.uTime.value = t;
      terrainUniforms.uLevel.value = MHHW_NAVD88 + state.level;
      terrainUniforms.uGloom.value = state.rain;
      rainMat.uniforms.uTime.value = t;
      rainMat.uniforms.uRain.value = state.rain;
      rain.visible = state.rain > 0.01;
      rainMat.uniforms.uCentre.value.copy(camK.position).lerp(kwTarget, 0.35);
      renderer.render(kw, camK);
    } else {
      placeGlobeCamera(Math.min(u, G0));
      // The storm turns with scroll and, slowly, with time (bounded so the
      // differential twist never smears the image).
      cloudUniforms.uSpin.value = 0.3 * smooth(0, G0, u) + 0.12 * (1 - Math.exp(-t / 50));
      const near = smooth(0.25, 0.02, camG.position.length() - 1);
      shells[2].material.uniforms.uOpacity.value = 0.3 * (1 - near * 0.6);
      renderer.render(globe, camG);
    }
    frames++;
  }

  canvas.addEventListener("webglcontextlost", (e) => {
    e.preventDefault();
    running = false;
    cancelAnimationFrame(raf);
    setLive(false);
  });

  return Promise.all([
    loadTexture(loader, "assets/globe/earth-bmng-2048.webp"),
    loadTexture(loader, "assets/globe/clouds-20170910-2048.webp", { srgb: false }),
    loadTexture(loader, "assets/globe/irma-20170910-2048.webp", { srgb: false }),
  ]).then(([day, cg, cr]) => {
    earthMat.uniforms.uDay.value = day;
    cloudUniforms.uCloudG.value = cg;
    cloudUniforms.uCloudR.value = cr;
    for (const s of shells) {
      s.material.uniforms.uCloudG.value = cg;
      s.material.uniforms.uCloudR.value = cr;
    }
    if (running) frame();
    return Promise.all([
      loadTexture(loader, "assets/keywest/ortho-naip-2048.webp"),
      loadTexture(loader, "assets/keywest/dem-cudem-navd88.png", { srgb: false }),
      loadTexture(loader, "assets/keywest/waternormals-512.jpg", { srgb: false, repeat: true }),
    ]).then(buildKeyWest);
  });
}
