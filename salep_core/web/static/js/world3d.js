// 3D sekme — Three.js YEREL vendor'dan tembel yüklenir (CDN yok).
// vendor/ boşken çağrıcıya hata verir; 2D sekme etkilenmez.
// Mesh şeması: sim/models/salep_meshes.json (world_arrays.v1:
// vertex/normal/uv/index düz diziler) — TEK KAYNAK.
const { profile2d } = globalThis.SalepProfile;

let three = null, controlsMod = null;

export async function init3d(canvas, meshUrl) {
  if (!three) {
    three = await import("../vendor/three/three.module.js");
    controlsMod = await import("../vendor/three/OrbitControls.js");
  }
  const renderer = new three.WebGLRenderer({ canvas, antialias: true });
  renderer.toneMapping = three.ACESFilmicToneMapping;
  renderer.outputColorSpace = three.SRGBColorSpace;
  const scene = new three.Scene();
  scene.background = new three.Color(0x0b0e11);
  const camera = new three.PerspectiveCamera(45, canvas.width / canvas.height, 0.1, 100);
  camera.position.set(2.2, 1.6, 2.6);
  const controls = new controlsMod.OrbitControls(camera, canvas);
  controls.target.set(0, 0.6, 0);

  const sun = new three.DirectionalLight(0xfff2dd, 2.2);
  sun.position.set(3, 5, 2);
  scene.add(sun);
  scene.add(new three.AmbientLight(0x33404d, 1.2));

  const mesh = await (await fetch(meshUrl)).json();
  const group = new three.Group();
  const mat = new three.MeshStandardMaterial({ color: 0x6da055, roughness: 0.8 });
  for (const [name, part] of Object.entries(mesh.parts)) {
    const g = new three.BufferGeometry();
    g.setAttribute("position", new three.Float32BufferAttribute(part.vertex, 3));
    if (part.normal) g.setAttribute("normal", new three.Float32BufferAttribute(part.normal, 3));
    if (part.uv) g.setAttribute("uv", new three.Float32BufferAttribute(part.uv, 2));
    if (part.index) g.setIndex(part.index);
    const m = new three.Mesh(g, mat.clone());
    m.name = name;
    group.add(m);
  }
  scene.add(group);

  let raf = 0;
  (function loop() {
    raf = requestAnimationFrame(loop);
    controls.update();
    renderer.render(scene, camera);
  })();

  return {
    // Aynı Frame → aynı parametreler (2D ile parite buradan gelir).
    setFrame(frame) {
      const pr = profile2d(frame);
      group.scale.setScalar(0.6 + 0.4 * (pr.stemH || 0.5));
      const stem = group.getObjectByName("stem");
      if (stem) stem.scale.y = 0.5 + pr.stemH;
    },
    dispose() { cancelAnimationFrame(raf); renderer.dispose(); },
  };
}
