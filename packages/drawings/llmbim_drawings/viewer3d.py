"""Presentation-grade 3D review viewer (orbit + layer transparency + studio lighting).

View-only — not drafting. Written next to model.gltf as viewer3d.html.
"""

from __future__ import annotations

import json
from pathlib import Path

_WALL_GHOST = 0.18

_VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>LLM-BIM — 3D Studio</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #070a0e;
    --panel: rgba(14, 18, 24, 0.92);
    --border: #2a3340;
    --text: #e8eef6;
    --muted: #8b97a8;
    --accent: #5eb1ff;
    --good: #3dd68c;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; overflow: hidden;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text); }
  #viewport { position: absolute; inset: 0; }
  #panel {
    position: absolute; top: 14px; left: 14px; width: 300px; max-height: calc(100% - 28px);
    overflow: auto; background: var(--panel); border: 1px solid var(--border);
    border-radius: 14px; padding: 14px 16px; z-index: 2;
    box-shadow: 0 12px 40px rgba(0,0,0,0.45); backdrop-filter: blur(12px);
  }
  #panel h1 { font-size: 1rem; margin: 0 0 4px; font-weight: 650; letter-spacing: -0.01em; }
  #panel .sub { font-size: 0.72rem; color: var(--muted); margin-bottom: 12px; line-height: 1.45; }
  #panel h2 {
    font-size: 0.68rem; margin: 14px 0 8px; color: var(--accent);
    text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600;
  }
  .row { display: flex; align-items: center; gap: 8px; margin: 7px 0; font-size: 0.82rem; }
  .row label { flex: 1; cursor: pointer; user-select: none; }
  .row input[type=checkbox] { accent-color: var(--accent); width: 15px; height: 15px; }
  .row input[type=range] { width: 88px; accent-color: var(--accent); }
  .swatch {
    width: 12px; height: 12px; border-radius: 3px; border: 1px solid #4a5564; flex-shrink: 0;
  }
  .btns { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  button {
    background: #1a222d; color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; padding: 6px 10px; font-size: 0.72rem; cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }
  button:hover { background: #243041; border-color: var(--accent); }
  button.primary { background: #1a3a5c; border-color: #3d7ab5; }
  #status { font-size: 0.72rem; color: var(--muted); margin-top: 12px; line-height: 1.4; }
  #status.err { color: #ff7b72; }
  #hint {
    position: absolute; bottom: 14px; right: 14px; z-index: 2;
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 12px; font-size: 0.7rem; color: var(--muted); max-width: 260px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.35);
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .badge {
    display: inline-block; font-size: 0.62rem; padding: 2px 6px; border-radius: 999px;
    background: #143d2a; color: var(--good); border: 1px solid #1f6b45; margin-left: 6px;
    vertical-align: middle;
  }
  code { background: #1a222d; padding: 1px 5px; border-radius: 4px; font-size: 0.85em; }
</style>
</head>
<body>
<div id="viewport"></div>
<aside id="panel">
  <h1 id="title">3D Studio <span class="badge">LLM-NATIVE</span></h1>
  <div class="sub">Presentation review of the live model. Ghost walls to see MEP/structure. Not drafting — agents author; you inspect.</div>
  <h2>Display</h2>
  <div class="row">
    <label for="ghostWalls">Ghost walls (see internals)</label>
    <input type="checkbox" id="ghostWalls" checked/>
  </div>
  <div class="row">
    <label for="edges">Crisp edges</label>
    <input type="checkbox" id="edges" checked/>
  </div>
  <div class="row">
    <label for="ground">Ground + grid</label>
    <input type="checkbox" id="ground" checked/>
  </div>
  <div class="row">
    <label for="shadows">Soft shadows</label>
    <input type="checkbox" id="shadows" checked/>
  </div>
  <div class="row">
    <label for="globalAlpha">Global opacity</label>
    <input type="range" id="globalAlpha" min="8" max="100" value="100"/>
  </div>
  <div class="row">
    <label for="exposure">Exposure</label>
    <input type="range" id="exposure" min="40" max="160" value="100"/>
  </div>
  <div class="btns">
    <button type="button" class="primary" id="btnFit">Fit</button>
    <button type="button" id="btnReset">Reset cam</button>
    <button type="button" id="btnAll">All layers</button>
    <button type="button" id="btnNone">None</button>
    <button type="button" id="btnOrtho">Persp / Ortho</button>
  </div>
  <h2>Layers</h2>
  <div id="layers"></div>
  <div id="status">Loading studio…</div>
  <p class="sub" style="margin-top:14px"><a href="index.html">← pack index</a> · <a href="model.gltf">model.gltf</a></p>
</aside>
<div id="hint">
  <strong style="color:#c9d1d9">Navigate</strong><br/>
  Left-drag orbit · right-drag pan · scroll zoom<br/>
  Double-click surface to focus
</div>
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
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const EMBEDDED = __EMBEDDED_GLTF__;
const WALL_GHOST = __WALL_GHOST__;
const statusEl = document.getElementById('status');
const layersEl = document.getElementById('layers');
const titleEl = document.getElementById('title');

const viewport = document.getElementById('viewport');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x070a0e, 1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
viewport.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x070a0e, 0.000015);

const camera = new THREE.PerspectiveCamera(42, window.innerWidth / window.innerHeight, 0.05, 1e7);
let ortho = null;
let useOrtho = false;

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.screenSpacePanning = true;
controls.minDistance = 0.5;
controls.maxDistance = 5e6;
controls.maxPolarAngle = Math.PI * 0.495;

// Environment for PBR reflections
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const hemi = new THREE.HemisphereLight(0xb8d0ff, 0x2a2a30, 0.55);
scene.add(hemi);
const key = new THREE.DirectionalLight(0xfff5e8, 1.35);
key.position.set(40, 80, 30);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.near = 0.5;
key.shadow.camera.far = 500;
key.shadow.bias = -0.00015;
key.shadow.normalBias = 0.02;
scene.add(key);
const fill = new THREE.DirectionalLight(0x88aaff, 0.35);
fill.position.set(-50, 30, -40);
scene.add(fill);
const rim = new THREE.DirectionalLight(0xffd0a0, 0.25);
rim.position.set(-20, 15, 60);
scene.add(rim);

// Model is already Y-up metres from exporter
const root = new THREE.Group();
scene.add(root);

const groundGroup = new THREE.Group();
scene.add(groundGroup);
let groundMesh = null;
let gridHelper = null;

/** @type {Map<string, { meshes: THREE.Object3D[], mats: THREE.Material[], edges: THREE.LineSegments[], visible: boolean, opacity: number }>} */
const layers = new Map();
let initialCam = null;
let modelBox = new THREE.Box3();

function setStatus(msg, err = false) {
  statusEl.textContent = msg;
  statusEl.className = err ? 'err' : '';
}

function layerNameFromObject(obj) {
  let o = obj;
  while (o) {
    if (o.name && !['Scene', 'RootNode', 'AuxScene'].includes(o.name) && !o.name.startsWith('mesh_')) {
      // prefer short material-like names
      if (o.isMesh && o.parent && o.parent.name && o.parent.name !== 'Scene') return o.parent.name;
      if (o.name) return o.name;
    }
    o = o.parent;
  }
  const m = obj.material;
  if (Array.isArray(m) && m[0]?.name) return m[0].name;
  if (m?.name) return m.name;
  return 'default';
}

function ensureLayer(name) {
  if (!layers.has(name)) {
    layers.set(name, { meshes: [], mats: [], edges: [], visible: true, opacity: 1 });
  }
  return layers.get(name);
}

function applyLayerStyle(name) {
  const L = layers.get(name);
  if (!L) return;
  const ghostWalls = document.getElementById('ghostWalls').checked;
  const showEdges = document.getElementById('edges').checked;
  const globalA = Number(document.getElementById('globalAlpha').value) / 100;
  for (const mat of L.mats) {
    let op = L.opacity * globalA;
    if (ghostWalls && (name === 'wall' || name === 'slab')) {
      op = Math.min(op, name === 'wall' ? WALL_GHOST : 0.35);
    }
    mat.transparent = op < 0.999;
    mat.opacity = Math.max(0.03, Math.min(1, op));
    mat.depthWrite = op > 0.85;
    mat.needsUpdate = true;
  }
  for (const mesh of L.meshes) {
    mesh.visible = L.visible && L.opacity > 0.01;
  }
  for (const e of L.edges) {
    e.visible = showEdges && L.visible && L.opacity > 0.05;
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
    let hex = '#888';
    if (mat0?.color) hex = '#' + mat0.color.getHexString();
    else if (mat0?.emissive) hex = '#' + mat0.emissive.getHexString();
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
      layers.get(el.getAttribute('data-layer')).visible = el.checked;
      applyLayerStyle(el.getAttribute('data-layer'));
    });
  });
  layersEl.querySelectorAll('input[type=range][data-opacity]').forEach(el => {
    el.addEventListener('input', () => {
      layers.get(el.getAttribute('data-opacity')).opacity = Number(el.value) / 100;
      applyLayerStyle(el.getAttribute('data-opacity'));
    });
  });
}

function updateGround(box) {
  groundGroup.clear();
  groundMesh = null;
  gridHelper = null;
  if (!document.getElementById('ground').checked || box.isEmpty()) return;
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const span = Math.max(size.x, size.z, 10) * 1.8;
  const y = box.min.y - 0.02;
  const geo = new THREE.PlaneGeometry(span, span);
  const mat = new THREE.MeshStandardMaterial({
    color: 0x12161c, metalness: 0.1, roughness: 0.92, transparent: true, opacity: 0.92,
  });
  groundMesh = new THREE.Mesh(geo, mat);
  groundMesh.rotation.x = -Math.PI / 2;
  groundMesh.position.set(center.x, y, center.z);
  groundMesh.receiveShadow = true;
  groundGroup.add(groundMesh);
  const div = Math.max(10, Math.round(span));
  gridHelper = new THREE.GridHelper(span, div, 0x3d4f66, 0x1e2833);
  gridHelper.position.set(center.x, y + 0.005, center.z);
  groundGroup.add(gridHelper);
}

function fitCamera(object) {
  modelBox = new THREE.Box3().setFromObject(object);
  if (modelBox.isEmpty()) return;
  const size = modelBox.getSize(new THREE.Vector3());
  const center = modelBox.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 1);
  const dist = maxDim * 1.55;
  controls.target.copy(center);
  camera.position.set(center.x + dist * 0.85, center.y + dist * 0.55, center.z + dist * 0.75);
  camera.near = Math.max(0.05, maxDim / 2000);
  camera.far = maxDim * 80;
  camera.updateProjectionMatrix();
  // shadow frustum
  const s = maxDim * 1.2;
  key.shadow.camera.left = -s;
  key.shadow.camera.right = s;
  key.shadow.camera.top = s;
  key.shadow.camera.bottom = -s;
  key.shadow.camera.updateProjectionMatrix();
  key.position.set(center.x + s * 0.6, center.y + s * 1.2, center.z + s * 0.4);
  key.target.position.copy(center);
  key.target.updateMatrixWorld();
  controls.update();
  initialCam = { pos: camera.position.clone(), target: controls.target.clone() };
  updateGround(modelBox);
  // fog scale
  scene.fog.density = 0.35 / maxDim;
}

function collectLayers(obj) {
  obj.traverse(child => {
    if (!child.isMesh) return;
    child.castShadow = true;
    child.receiveShadow = true;
    const name = layerNameFromObject(child);
    const L = ensureLayer(name);
    L.meshes.push(child);
    const mats = Array.isArray(child.material) ? child.material : [child.material];
    const cloned = mats.map(src => {
      const m = src.clone();
      m.side = THREE.DoubleSide;
      m.envMapIntensity = 0.85;
      if (m.metalness === undefined) m.metalness = 0.2;
      if (m.roughness === undefined) m.roughness = 0.6;
      return m;
    });
    child.material = Array.isArray(child.material) ? cloned : cloned[0];
    L.mats.push(...cloned);
    // crisp edges for BIM read
    try {
      const edges = new THREE.EdgesGeometry(child.geometry, 28);
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: 0x0a0c10, transparent: true, opacity: 0.35 })
      );
      line.renderOrder = 2;
      child.add(line);
      L.edges.push(line);
    } catch (_) { /* ignore non-indexed */ }
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
    titleEl.innerHTML = title + ' <span class="badge">LLM-NATIVE</span>';
    setStatus('Building presentation…');
    const gltf = await loadGltf(gltfData);
    root.add(gltf.scene);
    collectLayers(gltf.scene);
    applyAllLayers();
    rebuildPanel();
    fitCamera(root);
    setStatus(`Studio ready — ${layers.size} layers. Orbit to inspect.`);
  } catch (e) {
    console.error(e);
    setStatus(String(e.message || e) + ' — need network for Three.js CDN.', true);
  }
}

document.getElementById('ghostWalls').addEventListener('change', applyAllLayers);
document.getElementById('globalAlpha').addEventListener('input', applyAllLayers);
document.getElementById('edges').addEventListener('change', applyAllLayers);
document.getElementById('ground').addEventListener('change', () => updateGround(modelBox));
document.getElementById('shadows').addEventListener('change', () => {
  renderer.shadowMap.enabled = document.getElementById('shadows').checked;
  key.castShadow = renderer.shadowMap.enabled;
});
document.getElementById('exposure').addEventListener('input', () => {
  renderer.toneMappingExposure = Number(document.getElementById('exposure').value) / 100;
});
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
document.getElementById('btnOrtho').addEventListener('click', () => {
  useOrtho = !useOrtho;
  const aspect = window.innerWidth / window.innerHeight;
  if (useOrtho) {
    const dist = camera.position.distanceTo(controls.target);
    const h = dist * Math.tan(THREE.MathUtils.degToRad(camera.fov * 0.5));
    ortho = new THREE.OrthographicCamera(-h * aspect, h * aspect, h, -h, camera.near, camera.far);
    ortho.position.copy(camera.position);
    ortho.quaternion.copy(camera.quaternion);
    // swap for render
    window.__cam = ortho;
  } else {
    window.__cam = camera;
  }
});
window.__cam = camera;

window.addEventListener('resize', () => {
  const cam = window.__cam || camera;
  if (cam.isPerspectiveCamera) {
    cam.aspect = window.innerWidth / window.innerHeight;
  } else if (cam.isOrthographicCamera) {
    const aspect = window.innerWidth / window.innerHeight;
    const h = (cam.top - cam.bottom) / 2;
    cam.left = -h * aspect;
    cam.right = h * aspect;
  }
  cam.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
renderer.domElement.addEventListener('dblclick', ev => {
  pointer.x = (ev.clientX / window.innerWidth) * 2 - 1;
  pointer.y = -(ev.clientY / window.innerHeight) * 2 + 1;
  raycaster.setFromCamera(pointer, window.__cam || camera);
  const hits = raycaster.intersectObject(root, true);
  if (hits.length) {
    controls.target.copy(hits[0].point);
    controls.update();
  }
});

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  // keep ortho in sync with orbit if active
  if (useOrtho && ortho) {
    ortho.position.copy(camera.position);
    ortho.quaternion.copy(camera.quaternion);
    ortho.lookAt(controls.target);
  }
  renderer.render(scene, window.__cam || camera);
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
    """Write ``viewer3d.html`` into a deliverables pack directory."""
    out = Path(out_dir)
    gltf_path = out / gltf_name
    if not gltf_path.is_file():
        return None

    embedded_js = "null"
    if embed:
        try:
            data = json.loads(gltf_path.read_text(encoding="utf-8"))
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
