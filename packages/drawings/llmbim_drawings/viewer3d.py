"""Local-first 3D review viewer for deliverables packs (orbit + layer transparency).

View-only — not a drafting UI. Written next to model.gltf as viewer3d.html.
"""

from __future__ import annotations

import json
from pathlib import Path

# Default ghost opacity for walls so internals (MEP/structure) read clearly
_WALL_GHOST = 0.22

_VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>LLM-BIM 3D Review</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; overflow: hidden;
    font-family: system-ui, Segoe UI, sans-serif; background: #0b0f14; color: #e6edf3; }
  #viewport { position: absolute; inset: 0; }
  #panel {
    position: absolute; top: 12px; left: 12px; width: 280px; max-height: calc(100% - 24px);
    overflow: auto; background: rgba(22,27,34,0.94); border: 1px solid #30363d;
    border-radius: 10px; padding: 12px 14px; z-index: 2; backdrop-filter: blur(6px);
  }
  #panel h1 { font-size: 0.95rem; margin: 0 0 6px; font-weight: 600; }
  #panel .sub { font-size: 0.75rem; color: #8b949e; margin-bottom: 10px; line-height: 1.35; }
  #panel h2 { font-size: 0.8rem; margin: 12px 0 6px; color: #58a6ff; text-transform: uppercase;
    letter-spacing: 0.04em; }
  .row { display: flex; align-items: center; gap: 8px; margin: 6px 0; font-size: 0.85rem; }
  .row label { flex: 1; cursor: pointer; user-select: none; }
  .row input[type=checkbox] { accent-color: #58a6ff; }
  .row input[type=range] { width: 90px; }
  .swatch { width: 12px; height: 12px; border-radius: 3px; border: 1px solid #484f58; flex-shrink: 0; }
  .btns { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  button {
    background: #21262d; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px;
    padding: 5px 8px; font-size: 0.75rem; cursor: pointer;
  }
  button:hover { background: #30363d; border-color: #58a6ff; }
  #status { font-size: 0.75rem; color: #8b949e; margin-top: 10px; }
  #status.err { color: #f85149; }
  #hint {
    position: absolute; bottom: 12px; right: 12px; z-index: 2;
    background: rgba(22,27,34,0.85); border: 1px solid #30363d; border-radius: 8px;
    padding: 8px 10px; font-size: 0.72rem; color: #8b949e; max-width: 240px;
  }
  a { color: #58a6ff; }
</style>
</head>
<body>
<div id="viewport"></div>
<aside id="panel">
  <h1 id="title">3D review</h1>
  <div class="sub">Orbit view of <code>model.gltf</code>. Walls ghosted by default so MEP/structure stay visible. View-only — not drafting.</div>
  <h2>Global</h2>
  <div class="row">
    <label for="ghostWalls">Ghost walls (see inside)</label>
    <input type="checkbox" id="ghostWalls" checked/>
  </div>
  <div class="row">
    <label for="globalAlpha">Global opacity</label>
    <input type="range" id="globalAlpha" min="5" max="100" value="100"/>
  </div>
  <div class="btns">
    <button type="button" id="btnAll">Show all</button>
    <button type="button" id="btnNone">Hide all</button>
    <button type="button" id="btnReset">Reset view</button>
    <button type="button" id="btnFit">Fit model</button>
  </div>
  <h2>Layers</h2>
  <div id="layers"></div>
  <div id="status">Loading…</div>
  <p class="sub" style="margin-top:12px"><a href="index.html">← pack index</a> · <a href="model.gltf">model.gltf</a></p>
</aside>
<div id="hint">Drag orbit · right-drag / two-finger pan · scroll zoom<br/>Double-click mesh to focus</div>
<script type="importmap">
{
  "imports": {
    "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
  }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const EMBEDDED = __EMBEDDED_GLTF__;
const WALL_GHOST = __WALL_GHOST__;
const statusEl = document.getElementById('status');
const layersEl = document.getElementById('layers');
const titleEl = document.getElementById('title');

const viewport = document.getElementById('viewport');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x0b0f14, 1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
viewport.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 5e6);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;
controls.minDistance = 10;
controls.maxDistance = 2e6;

scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const key = new THREE.DirectionalLight(0xffffff, 0.85);
key.position.set(1, 2, 1.5);
scene.add(key);
const fill = new THREE.DirectionalLight(0x88aaff, 0.25);
fill.position.set(-1.5, 0.5, -1);
scene.add(fill);
const hemi = new THREE.HemisphereLight(0xb1c5ff, 0x444444, 0.35);
scene.add(hemi);

// glTF is Y-up in three.js; our model is Z-up (mm). Rotate Z-up → Y-up.
const root = new THREE.Group();
root.rotation.x = -Math.PI / 2;
scene.add(root);

/** @type {Map<string, { meshes: THREE.Mesh[], mats: THREE.Material[], visible: boolean, opacity: number }>} */
const layers = new Map();
let boxHelper = null;
let initialCam = null;

function setStatus(msg, err = false) {
  statusEl.textContent = msg;
  statusEl.className = err ? 'err' : '';
}

function layerNameFromObject(obj) {
  // Prefer node name (per-layer export), else material name
  if (obj.name && obj.name !== 'Scene' && obj.name !== 'RootNode') return obj.name;
  const m = obj.material;
  if (Array.isArray(m) && m[0]?.name) return m[0].name;
  if (m?.name) return m.name;
  return 'default';
}

function ensureLayer(name) {
  if (!layers.has(name)) {
    layers.set(name, { meshes: [], mats: [], visible: true, opacity: 1 });
  }
  return layers.get(name);
}

function applyLayerStyle(name) {
  const L = layers.get(name);
  if (!L) return;
  const ghostWalls = document.getElementById('ghostWalls').checked;
  const globalA = Number(document.getElementById('globalAlpha').value) / 100;
  for (const mat of L.mats) {
    let op = L.opacity * globalA;
    if (ghostWalls && name === 'wall') op = Math.min(op, WALL_GHOST);
    mat.transparent = op < 0.999;
    mat.opacity = Math.max(0.02, Math.min(1, op));
    mat.depthWrite = op > 0.9;
    mat.needsUpdate = true;
  }
  for (const mesh of L.meshes) {
    mesh.visible = L.visible && L.opacity > 0.01;
  }
}

function applyAllLayers() {
  for (const name of layers.keys()) applyLayerStyle(name);
}

function rebuildPanel() {
  layersEl.innerHTML = '';
  const names = [...layers.keys()].sort((a, b) => a.localeCompare(b));
  for (const name of names) {
    const L = layers.get(name);
    const mat0 = L.mats[0];
    const c = mat0?.color;
    const hex = c ? '#' + c.getHexString() : '#888';
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `
      <span class="swatch" style="background:${hex}"></span>
      <label><input type="checkbox" data-layer="${name}" ${L.visible ? 'checked' : ''}/> ${name}</label>
      <input type="range" min="5" max="100" value="${Math.round(L.opacity * 100)}" data-opacity="${name}"/>
    `;
    layersEl.appendChild(row);
  }
  layersEl.querySelectorAll('input[type=checkbox][data-layer]').forEach(el => {
    el.addEventListener('change', () => {
      const name = el.getAttribute('data-layer');
      layers.get(name).visible = el.checked;
      applyLayerStyle(name);
    });
  });
  layersEl.querySelectorAll('input[type=range][data-opacity]').forEach(el => {
    el.addEventListener('input', () => {
      const name = el.getAttribute('data-opacity');
      layers.get(name).opacity = Number(el.value) / 100;
      applyLayerStyle(name);
    });
  });
}

function fitCamera(object) {
  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) return;
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 1);
  const dist = maxDim * 1.6;
  controls.target.copy(center);
  camera.position.set(center.x + dist * 0.7, center.y + dist * 0.55, center.z + dist * 0.7);
  camera.near = Math.max(0.1, maxDim / 1000);
  camera.far = maxDim * 50;
  camera.updateProjectionMatrix();
  controls.update();
  initialCam = {
    pos: camera.position.clone(),
    target: controls.target.clone(),
  };
  if (boxHelper) scene.remove(boxHelper);
}

function collectLayers(obj) {
  obj.traverse(child => {
    if (!child.isMesh) return;
    const name = layerNameFromObject(child);
    const L = ensureLayer(name);
    L.meshes.push(child);
    const mats = Array.isArray(child.material) ? child.material : [child.material];
    for (let i = 0; i < mats.length; i++) {
      // clone so opacity edits don't share across layers unexpectedly
      const m = mats[i].clone();
      m.side = THREE.DoubleSide;
      m.transparent = true;
      mats[i] = m;
      L.mats.push(m);
    }
    child.material = Array.isArray(child.material) ? mats : mats[0];
  });
}

function loadGltf(data) {
  return new Promise((resolve, reject) => {
    const loader = new GLTFLoader();
    loader.parse(
      typeof data === 'string' ? data : JSON.stringify(data),
      '',
      gltf => resolve(gltf),
      err => reject(err)
    );
  });
}

async function boot() {
  try {
    let gltfData = EMBEDDED;
    if (!gltfData) {
      setStatus('Fetching model.gltf…');
      const res = await fetch('model.gltf');
      if (!res.ok) throw new Error('Could not load model.gltf (HTTP ' + res.status + ')');
      gltfData = await res.json();
    }
    const title = (gltfData.scenes && gltfData.scenes[0] && gltfData.scenes[0].name) || 'LLM-BIM model';
    titleEl.textContent = title;
    setStatus('Parsing glTF…');
    const gltf = await loadGltf(gltfData);
    root.add(gltf.scene);
    collectLayers(gltf.scene);
    // Walls slightly ghost by default when checkbox on
    applyAllLayers();
    rebuildPanel();
    fitCamera(root);
    const n = [...layers.keys()].length;
    setStatus(`Loaded ${n} layer(s). Drag to orbit.`);
  } catch (e) {
    console.error(e);
    setStatus(String(e.message || e) + ' — try serving the pack folder over HTTP if file:// blocked CDN.', true);
  }
}

document.getElementById('ghostWalls').addEventListener('change', applyAllLayers);
document.getElementById('globalAlpha').addEventListener('input', applyAllLayers);
document.getElementById('btnAll').addEventListener('click', () => {
  for (const L of layers.values()) L.visible = true;
  layersEl.querySelectorAll('input[type=checkbox][data-layer]').forEach(el => { el.checked = true; });
  applyAllLayers();
});
document.getElementById('btnNone').addEventListener('click', () => {
  for (const L of layers.values()) L.visible = false;
  layersEl.querySelectorAll('input[type=checkbox][data-layer]').forEach(el => { el.checked = false; });
  applyAllLayers();
});
document.getElementById('btnReset').addEventListener('click', () => {
  if (!initialCam) return;
  camera.position.copy(initialCam.pos);
  controls.target.copy(initialCam.target);
  controls.update();
});
document.getElementById('btnFit').addEventListener('click', () => fitCamera(root));

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
renderer.domElement.addEventListener('dblclick', ev => {
  pointer.x = (ev.clientX / window.innerWidth) * 2 - 1;
  pointer.y = -(ev.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObject(root, true);
  if (hits.length) {
    controls.target.copy(hits[0].point);
    controls.update();
  }
});

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
boot();
</script>
</body>
</html>
"""


def write_viewer_3d(
    out_dir: str | Path,
    *,
    gltf_name: str = "model.gltf",
    embed: bool = True,
    wall_ghost: float = _WALL_GHOST,
) -> Path | None:
    """Write ``viewer3d.html`` into a deliverables pack directory.

    Returns path written, or None if no glTF is present.
    When ``embed`` is True, the glTF JSON is inlined so the page works from
    ``file://`` without a local server (CDN still needed for three.js).
    """
    out = Path(out_dir)
    gltf_path = out / gltf_name
    if not gltf_path.is_file():
        return None

    embedded_js = "null"
    if embed:
        try:
            data = json.loads(gltf_path.read_text(encoding="utf-8"))
            # Compact JSON for smaller HTML
            embedded_js = json.dumps(data, separators=(",", ":"))
        except Exception:  # noqa: BLE001
            embedded_js = "null"

    html = (
        _VIEWER_HTML.replace("__EMBEDDED_GLTF__", embedded_js)
        .replace("__WALL_GHOST__", str(float(wall_ghost)))
    )
    path = out / "viewer3d.html"
    path.write_text(html, encoding="utf-8")
    return path
