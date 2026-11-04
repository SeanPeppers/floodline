// Floodline 3D backdrop. Three.js is loaded lazily (idle callback, after
// first paint) so it never blocks the initial render. One renderer/camera
// per scene-layer, but each pauses its own rAF loop via IntersectionObserver
// when scrolled off-screen, and nothing loads at all under
// prefers-reduced-motion or Save-Data — the page is fully readable without it.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const saveData = navigator.connection && navigator.connection.saveData;

if (!reduceMotion && !saveData) {
  onIdle(() => initScenes());
}

function onIdle(fn) {
  if ("requestIdleCallback" in window) requestIdleCallback(fn, { timeout: 2000 });
  else window.addEventListener("load", () => setTimeout(fn, 200));
}

async function initScenes() {
  const THREE = await import("three");
  const { GLTFLoader } = await import("three/addons/loaders/GLTFLoader.js");

  const loader = new GLTFLoader();
  const dpr = Math.min(window.devicePixelRatio || 1, 2); // set once; never resized adaptively

  const waterVertexShader = `
    uniform float uTime;
    varying vec2 vUv;
    varying float vWave;
    void main() {
      vUv = uv;
      vec3 pos = position;
      float wave = sin(pos.x * 1.4 + uTime * 0.6) * 0.08
                 + sin(pos.y * 2.1 - uTime * 0.4) * 0.05;
      pos.z += wave;
      vWave = wave;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    }
  `;
  const waterFragmentShader = `
    precision mediump float;
    varying vec2 vUv;
    varying float vWave;
    uniform vec3 uDeep;
    uniform vec3 uShallow;
    void main() {
      vec3 color = mix(uDeep, uShallow, smoothstep(-0.1, 0.12, vWave));
      gl_FragColor = vec4(color, 0.9);
    }
  `;

  const layers = document.querySelectorAll(".scene-layer");
  layers.forEach((layer) => setupScene(layer));

  function setupScene(layer) {
    const canvas = layer.querySelector(".scene-canvas");
    const modelName = layer.dataset.scene;
    const section = layer.closest(".section");

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(dpr);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 50);
    camera.position.set(0, 1.4, 6);
    camera.lookAt(0, 0.3, 0);

    scene.add(new THREE.AmbientLight(0x6fa7c9, 0.9));
    const sun = new THREE.DirectionalLight(0xfff2d6, 1.1);
    sun.position.set(3, 5, 4);
    scene.add(sun);

    // Water plane — hand-written shader + scene composition, not a sourced
    // asset, representing the "ocean surface" theme per the brief's own
    // allowance for procedural effects.
    const waterGeo = new THREE.PlaneGeometry(14, 10, 48, 36);
    const waterMat = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uDeep: { value: new THREE.Color(0x0a2a3a) },
        uShallow: { value: new THREE.Color(0x2dd4bf) },
      },
      vertexShader: waterVertexShader,
      fragmentShader: waterFragmentShader,
      transparent: true,
    });
    const water = new THREE.Mesh(waterGeo, waterMat);
    water.rotation.x = -Math.PI / 2.3;
    water.position.y = -0.6;
    scene.add(water);

    let model = null;
    loader.load(
      `assets/models/${modelName}/${modelName}_1k.gltf`,
      (gltf) => {
        model = gltf.scene;
        model.scale.setScalar(modelName === "ocean_buoy" ? 1.1 : 1.6);
        model.position.y = 0.1;
        scene.add(model);
      },
      undefined,
      (err) => console.warn("Floodline: model load failed for", modelName, err)
    );

    function resize() {
      const rect = canvas.getBoundingClientRect();
      const w = Math.max(1, rect.width), h = Math.max(1, rect.height);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    resize();
    new ResizeObserver(resize).observe(canvas);

    let running = false;
    let raf = null;
    const clock = new THREE.Clock();

    function frame() {
      if (!running) return;
      const t = clock.getElapsedTime();
      waterMat.uniforms.uTime.value = t;
      if (model) model.rotation.y = Math.sin(t * 0.25) * 0.3 + t * 0.08;
      renderer.render(scene, camera);
      raf = requestAnimationFrame(frame);
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && !running) {
            running = true;
            raf = requestAnimationFrame(frame);
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
}
