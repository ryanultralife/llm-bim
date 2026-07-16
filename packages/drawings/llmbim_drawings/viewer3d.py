"""Presentation-grade 3D review viewer — three visual step-changes:

1. Interactive section clipping (true cutaway)
2. Cinematic presentation (bloom, ACES, studio polish)
3. Imagine-generated studio sky + concrete floor materials
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

_WALL_GHOST = 0.18
_ASSETS = Path(__file__).resolve().parent / "assets"


def _b64_data_uri(path: Path, mime: str = "image/jpeg") -> str:
    if not path.is_file():
        return ""
    raw = path.read_bytes()
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


_VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>LLM-BIM — 3D Studio</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #05080c;
    --panel: rgba(12, 16, 22, 0.94);
    --border: #2a3340;
    --text: #e8eef6;
    --muted: #8b97a8;
    --accent: #5eb1ff;
    --good: #3dd68c;
    --warn: #e3b341;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; overflow: hidden;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    background: var(--bg); color: var(--text); }
  #viewport { position: absolute; inset: 0; }
  #panel {
    position: absolute; top: 14px; left: 14px; width: 312px; max-height: calc(100% - 28px);
    overflow: auto; background: var(--panel); border: 1px solid var(--border);
    border-radius: 14px; padding: 14px 16px; z-index: 2;
    box-shadow: 0 16px 48px rgba(0,0,0,0.55); backdrop-filter: blur(14px);
  }
  #brand { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  #brand img { width: 36px; height: 36px; border-radius: 8px; object-fit: cover;
    border: 1px solid var(--border); }
  #panel h1 { font-size: 1rem; margin: 0; font-weight: 650; letter-spacing: -0.01em; }
  #panel .sub { font-size: 0.72rem; color: var(--muted); margin-bottom: 10px; line-height: 1.45; }
  #panel h2 {
    font-size: 0.68rem; margin: 14px 0 8px; color: var(--accent);
    text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600;
  }
  .row { display: flex; align-items: center; gap: 8px; margin: 7px 0; font-size: 0.82rem; }
  .row label { flex: 1; cursor: pointer; user-select: none; }
  .row input[type=checkbox] { accent-color: var(--accent); width: 15px; height: 15px; }
  .row input[type=range] { width: 100px; accent-color: var(--accent); }
  .row select {
    background: #1a222d; color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; padding: 3px 6px; font-size: 0.75rem;
  }
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
  button.active { background: #3a2a12; border-color: var(--warn); color: #f0d78c; }
  #status { font-size: 0.72rem; color: var(--muted); margin-top: 12px; line-height: 1.4; }
  #status.err { color: #ff7b72; }
  #hint {
    position: absolute; bottom: 14px; right: 14px; z-index: 2;
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 12px; font-size: 0.7rem; color: var(--muted); max-width: 270px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .badge {
    display: inline-block; font-size: 0.58rem; padding: 2px 7px; border-radius: 999px;
    background: #143d2a; color: var(--good); border: 1px solid #1f6b45; margin-left: 4px;
    vertical-align: middle; letter-spacing: 0.04em;
  }
  .step-tag {
    display: inline-block; font-size: 0.58rem; color: var(--warn); border: 1px solid #5c4a1e;
    background: #2a220e; border-radius: 4px; padding: 1px 5px; margin-right: 6px;
  }
  code { background: #1a222d; padding: 1px 5px; border-radius: 4px; font-size: 0.85em; }
  #clipViz {
    position: absolute; top: 14px; right: 14px; z-index: 2; display: none;
    background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
    padding: 8px 12px; font-size: 0.75rem; color: var(--warn);
  }
</style>
</head>
<body>
<div id="viewport"></div>
<div id="clipViz">SECTION ACTIVE</div>
<aside id="panel">
  <div id="brand">
    <img id="brandImg" alt="" width="36" height="36"/>
    <div>
      <h1 id="title">3D Studio</h1>
      <span class="badge">LLM-NATIVE</span>
    </div>
  </div>
  <div class="sub">Solid materials + round pipes by default. Toggle <strong>ghost walls</strong> only when you need see-through MEP review. Section cut · bloom · Imagine studio.</div>

  <h2><span class="step-tag">1</span>Section cut</h2>
  <div class="row">
    <label for="clipOn">Enable cutaway plane</label>
    <input type="checkbox" id="clipOn"/>
  </div>
  <div class="row">
    <label for="clipAxis">Axis</label>
    <select id="clipAxis">
      <option value="x">X (east–west)</option>
      <option value="y" selected>Y (height)</option>
      <option value="z">Z (north–south)</option>
    </select>
  </div>
  <div class="row">
    <label for="clipPos">Cut position</label>
    <input type="range" id="clipPos" min="0" max="1000" value="500"/>
  </div>
  <div class="row">
    <label for="clipFlip">Flip side</label>
    <input type="checkbox" id="clipFlip"/>
  </div>
  <div class="btns">
    <button type="button" id="btnClipMid">Cut mid</button>
    <button type="button" id="btnClipOff">Clear cut</button>
  </div>

  <h2><span class="step-tag">2</span>Cinematic</h2>
  <div class="row">
    <label for="bloom">Bloom (glow)</label>
    <input type="checkbox" id="bloom" checked/>
  </div>
  <div class="row">
    <label for="edges">Crisp edges</label>
    <input type="checkbox" id="edges" checked/>
  </div>
  <div class="row">
    <label for="shadows">Soft shadows</label>
    <input type="checkbox" id="shadows" checked/>
  </div>
  <div class="row">
    <label for="ghostWalls">Ghost walls (see-through)</label>
    <input type="checkbox" id="ghostWalls"/>
  </div>
  <div class="row">
    <label for="exposure">Exposure</label>
    <input type="range" id="exposure" min="40" max="180" value="105"/>
  </div>
  <div class="row">
    <label for="globalAlpha">Global opacity</label>
    <input type="range" id="globalAlpha" min="8" max="100" value="100"/>
  </div>
  <div class="btns">
    <button type="button" class="primary" id="btnFit">Fit</button>
    <button type="button" id="btnReset">Reset cam</button>
    <button type="button" id="btnAll">All layers</button>
    <button type="button" id="btnNone">None</button>
  </div>

  <h2><span class="step-tag">3</span>Studio env</h2>
  <div class="row">
    <label for="studioSky">Imagine sky dome</label>
    <input type="checkbox" id="studioSky" checked/>
  </div>
  <div class="row">
    <label for="ground">Concrete floor</label>
    <input type="checkbox" id="ground" checked/>
  </div>

  <h2>Layers</h2>
  <div id="layers"></div>
  <div id="status">Loading studio…</div>
  <p class="sub" style="margin-top:14px"><a href="index.html">← pack index</a> · <a href="model.gltf">model.gltf</a></p>
</aside>
<div id="hint">
  <strong style="color:#c9d1d9">Navigate</strong><br/>
  Left-drag orbit · right-drag pan · scroll zoom<br/>
  Double-click to focus · Section cut = step 1
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
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

const EMBEDDED = __EMBEDDED_GLTF__;
const WALL_GHOST = __WALL_GHOST__;
const SKY_URI = __SKY_URI__;
const FLOOR_URI = __FLOOR_URI__;
const BRAND_URI = __BRAND_URI__;

const statusEl = document.getElementById('status');
const layersEl = document.getElementById('layers');
const titleEl = document.getElementById('title');
const clipViz = document.getElementById('clipViz');
const brandImg = document.getElementById('brandImg');
if (BRAND_URI) brandImg.src = BRAND_URI;

const viewport = document.getElementById('viewport');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x05080c, 1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.localClippingEnabled = true;
viewport.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x05080c, 0.000012);

const camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 0.05, 1e7);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.055;
controls.screenSpacePanning = true;
controls.minDistance = 0.5;
controls.maxDistance = 5e6;
controls.maxPolarAngle = Math.PI * 0.495;

// --- Step 2: cinematic post ---
const composer = new EffectComposer(renderer);
const renderPass = new RenderPass(scene, camera);
composer.addPass(renderPass);
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.28, 0.55, 0.82
);
composer.addPass(bloomPass);

const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

const hemi = new THREE.HemisphereLight(0xc0d8ff, 0x1a1a22, 0.5);
scene.add(hemi);
const key = new THREE.DirectionalLight(0xfff4e6, 1.4);
key.position.set(40, 80, 30);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.bias = -0.00012;
key.shadow.normalBias = 0.025;
scene.add(key);
scene.add(key.target);
const fill = new THREE.DirectionalLight(0x88aaff, 0.32);
fill.position.set(-50, 30, -40);
scene.add(fill);
const rim = new THREE.DirectionalLight(0xffc890, 0.22);
rim.position.set(-20, 18, 55);
scene.add(rim);

const root = new THREE.Group();
scene.add(root);
const groundGroup = new THREE.Group();
scene.add(groundGroup);
const skyGroup = new THREE.Group();
scene.add(skyGroup);

// --- Step 1: clipping ---
const clipPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), 0);
let clipEnabled = false;
const clipHelper = new THREE.PlaneHelper(clipPlane, 10, 0xe3b341);
clipHelper.visible = false;
scene.add(clipHelper);

/** @type {Map<string, any>} */
const layers = new Map();
let initialCam = null;
let modelBox = new THREE.Box3();
let floorTex = null;
let skyMesh = null;

function setStatus(msg, err = false) {
  statusEl.textContent = msg;
  statusEl.className = err ? 'err' : '';
}

function layerNameFromObject(obj) {
  let o = obj;
  while (o) {
    if (o.name && !['Scene', 'RootNode', 'AuxScene'].includes(o.name)) {
      if (o.isMesh && o.parent?.name && o.parent.name !== 'Scene') return o.parent.name;
      return o.name;
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
  const isGlass = name === 'window';
  for (const mat of L.mats) {
    let op = L.opacity * globalA;
    if (ghostWalls && (name === 'wall' || name === 'slab')) {
      op = Math.min(op, name === 'wall' ? WALL_GHOST : 0.32);
    }
    // Preserve PBR from glTF; only adjust transparency when user ghosts / slides opacity
    const opaque = op >= 0.995 && !isGlass;
    mat.transparent = !opaque;
    mat.opacity = isGlass ? Math.min(op, 0.55) : Math.max(0.03, Math.min(1, op));
    // Solid layers must depth-write so meshes occlude correctly
    mat.depthWrite = opaque || (op > 0.9 && !isGlass);
    mat.depthTest = true;
    mat.side = (mat.transparent || isGlass) ? THREE.DoubleSide : THREE.FrontSide;
    // Metal layers pick up studio env
    if (mat.envMapIntensity !== undefined) {
      const metal = mat.metalness ?? 0;
      mat.envMapIntensity = metal > 0.5 ? 1.35 : 0.85;
    }
    mat.clippingPlanes = clipEnabled ? [clipPlane] : [];
    mat.clipShadows = clipEnabled;
    mat.needsUpdate = true;
  }
  for (const mesh of L.meshes) {
    mesh.visible = L.visible && L.opacity > 0.01;
    // Openings sit slightly proud of host wall to avoid z-fight
    if (name === 'door' || name === 'window') {
      mesh.renderOrder = 1;
      if (mesh.material && !Array.isArray(mesh.material)) {
        mesh.material.polygonOffset = true;
        mesh.material.polygonOffsetFactor = -1;
        mesh.material.polygonOffsetUnits = -1;
      }
    }
  }
  for (const e of L.edges) {
    e.visible = showEdges && L.visible && L.opacity > 0.05;
    if (e.material) {
      e.material.depthWrite = false;
      e.material.clippingPlanes = clipEnabled ? [clipPlane] : [];
      e.material.needsUpdate = true;
    }
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

function updateClipFromUI() {
  clipEnabled = document.getElementById('clipOn').checked;
  clipViz.style.display = clipEnabled ? 'block' : 'none';
  if (!clipEnabled || modelBox.isEmpty()) {
    clipHelper.visible = false;
    applyAllLayers();
    return;
  }
  const axis = document.getElementById('clipAxis').value;
  const t = Number(document.getElementById('clipPos').value) / 1000;
  const flip = document.getElementById('clipFlip').checked ? -1 : 1;
  const min = modelBox.min;
  const max = modelBox.max;
  const size = modelBox.getSize(new THREE.Vector3());
  let n = new THREE.Vector3(0, -1, 0);
  let pos = 0;
  if (axis === 'x') {
    n.set(flip, 0, 0);
    pos = min.x + size.x * t;
    clipPlane.setFromNormalAndCoplanarPoint(n, new THREE.Vector3(pos, 0, 0));
  } else if (axis === 'z') {
    n.set(0, 0, flip);
    pos = min.z + size.z * t;
    clipPlane.setFromNormalAndCoplanarPoint(n, new THREE.Vector3(0, 0, pos));
  } else {
    n.set(0, flip, 0);
    pos = min.y + size.y * t;
    clipPlane.setFromNormalAndCoplanarPoint(n, new THREE.Vector3(0, pos, 0));
  }
  const span = Math.max(size.x, size.y, size.z, 1) * 1.1;
  clipHelper.size = span;
  clipHelper.visible = true;
  clipHelper.updateMatrixWorld(true);
  applyAllLayers();
}

function updateGround() {
  groundGroup.clear();
  if (!document.getElementById('ground').checked || modelBox.isEmpty()) return;
  const size = modelBox.getSize(new THREE.Vector3());
  const center = modelBox.getCenter(new THREE.Vector3());
  const span = Math.max(size.x, size.z, 10) * 2.2;
  const y = modelBox.min.y - 0.03;
  const geo = new THREE.PlaneGeometry(span, span);
  const mat = new THREE.MeshStandardMaterial({
    color: 0x888888,
    metalness: 0.08,
    roughness: 0.9,
    map: floorTex || null,
  });
  if (floorTex) {
    floorTex.wrapS = floorTex.wrapT = THREE.RepeatWrapping;
    floorTex.repeat.set(Math.max(4, span / 4), Math.max(4, span / 4));
    mat.map = floorTex;
  } else {
    mat.color.setHex(0x12161c);
  }
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(center.x, y, center.z);
  mesh.receiveShadow = true;
  groundGroup.add(mesh);
  const grid = new THREE.GridHelper(span, Math.max(12, Math.round(span)), 0x3d4f66, 0x1a222c);
  grid.position.set(center.x, y + 0.008, center.z);
  groundGroup.add(grid);
}

function updateSky() {
  skyGroup.clear();
  skyMesh = null;
  if (!document.getElementById('studioSky').checked || !SKY_URI) return;
  const loader = new THREE.TextureLoader();
  loader.load(SKY_URI, tex => {
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.mapping = THREE.EquirectangularReflectionMapping;
    // soft backdrop sphere
    const r = modelBox.isEmpty() ? 200 : Math.max(...modelBox.getSize(new THREE.Vector3()).toArray()) * 4;
    const geo = new THREE.SphereGeometry(Math.max(r, 80), 48, 32);
    const mat = new THREE.MeshBasicMaterial({ map: tex, side: THREE.BackSide, depthWrite: false });
    skyMesh = new THREE.Mesh(geo, mat);
    if (!modelBox.isEmpty()) {
      const c = modelBox.getCenter(new THREE.Vector3());
      skyMesh.position.copy(c);
    }
    skyGroup.add(skyMesh);
    // also feed a soft environment from the texture
    try {
      const envRT = pmrem.fromEquirectangular(tex);
      scene.environment = envRT.texture;
    } catch (_) { /* RoomEnvironment already set */ }
  });
}

function fitCamera(object) {
  modelBox = new THREE.Box3().setFromObject(object);
  if (modelBox.isEmpty()) return;
  const size = modelBox.getSize(new THREE.Vector3());
  const center = modelBox.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 1);
  const dist = maxDim * 1.5;
  controls.target.copy(center);
  camera.position.set(center.x + dist * 0.9, center.y + dist * 0.52, center.z + dist * 0.72);
  camera.near = Math.max(0.05, maxDim / 2000);
  camera.far = maxDim * 100;
  camera.updateProjectionMatrix();
  const s = maxDim * 1.3;
  key.shadow.camera.left = -s;
  key.shadow.camera.right = s;
  key.shadow.camera.top = s;
  key.shadow.camera.bottom = -s;
  key.shadow.camera.far = s * 4;
  key.shadow.camera.updateProjectionMatrix();
  key.position.set(center.x + s * 0.55, center.y + s * 1.15, center.z + s * 0.35);
  if (key.target) {
    key.target.position.copy(center);
    key.target.updateMatrixWorld();
  }
  controls.update();
  initialCam = { pos: camera.position.clone(), target: controls.target.clone() };
  scene.fog.density = 0.28 / maxDim;
  updateGround();
  updateSky();
  updateClipFromUI();
}

function collectLayers(obj) {
  obj.traverse(child => {
    if (!child.isMesh) return;
    child.castShadow = true;
    child.receiveShadow = true;
    // Smooth groups already in normals; keep geometry as exported
    if (child.geometry && !child.geometry.attributes.normal) {
      child.geometry.computeVertexNormals();
    }
    const name = layerNameFromObject(child);
    const L = ensureLayer(name);
    L.meshes.push(child);
    const mats = Array.isArray(child.material) ? child.material : [child.material];
    const cloned = mats.map(src => {
      const m = src.clone();
      // Keep FrontSide for opaque PBR so walls don't double-draw / show-through
      const isGlass = name === 'window' || (m.opacity !== undefined && m.opacity < 0.99);
      m.side = isGlass ? THREE.DoubleSide : THREE.FrontSide;
      m.envMapIntensity = (m.metalness ?? 0) > 0.5 ? 1.35 : 0.9;
      // Ensure metalness/roughness from glTF survive
      if (m.metalness === undefined) m.metalness = 0.2;
      if (m.roughness === undefined) m.roughness = 0.6;
      return m;
    });
    child.material = Array.isArray(child.material) ? cloned : cloned[0];
    L.mats.push(...cloned);
    try {
      // Higher threshold → fewer facet edges on round pipes (cleaner silhouette)
      const edges = new THREE.EdgesGeometry(child.geometry, name.startsWith('pipe') || name === 'conduit' ? 40 : 22);
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: 0x0a0c10, transparent: true, opacity: 0.22, depthWrite: false })
      );
      line.renderOrder = 2;
      child.add(line);
      L.edges.push(line);
    } catch (_) {}
  });
}

function loadGltf(data) {
  return new Promise((resolve, reject) => {
    new GLTFLoader().parse(
      typeof data === 'string' ? data : JSON.stringify(data),
      '',
      gltf => resolve(gltf),
      err => reject(err)
    );
  });
}

async function boot() {
  try {
    if (FLOOR_URI) {
      floorTex = await new Promise((res, rej) => {
        new THREE.TextureLoader().load(FLOOR_URI, t => {
          t.colorSpace = THREE.SRGBColorSpace;
          t.anisotropy = 8;
          res(t);
        }, undefined, rej);
      });
    }
    let gltfData = EMBEDDED;
    if (!gltfData) {
      setStatus('Fetching model.gltf…');
      const r = await fetch('model.gltf');
      if (!r.ok) throw new Error('Could not load model.gltf');
      gltfData = await r.json();
    }
    const title = (gltfData.scenes?.[0]?.name) || 'LLM-BIM model';
    titleEl.textContent = title;
    setStatus('Building presentation…');
    const gltf = await loadGltf(gltfData);
    root.add(gltf.scene);
    collectLayers(gltf.scene);
    applyAllLayers();
    rebuildPanel();
    fitCamera(root);
    setStatus(`Studio ready — ${layers.size} layers · section cut · cinematic · Imagine env`);
  } catch (e) {
    console.error(e);
    setStatus(String(e.message || e) + ' — need network for Three.js CDN.', true);
  }
}

// UI wiring
['ghostWalls', 'globalAlpha', 'edges'].forEach(id => {
  document.getElementById(id).addEventListener(id === 'globalAlpha' ? 'input' : 'change', applyAllLayers);
});
document.getElementById('bloom').addEventListener('change', () => {
  bloomPass.enabled = document.getElementById('bloom').checked;
});
document.getElementById('shadows').addEventListener('change', () => {
  renderer.shadowMap.enabled = document.getElementById('shadows').checked;
  key.castShadow = renderer.shadowMap.enabled;
});
document.getElementById('exposure').addEventListener('input', () => {
  renderer.toneMappingExposure = Number(document.getElementById('exposure').value) / 100;
});
document.getElementById('ground').addEventListener('change', updateGround);
document.getElementById('studioSky').addEventListener('change', updateSky);
['clipOn', 'clipAxis', 'clipFlip'].forEach(id => {
  document.getElementById(id).addEventListener('change', updateClipFromUI);
});
document.getElementById('clipPos').addEventListener('input', updateClipFromUI);
document.getElementById('btnClipMid').addEventListener('click', () => {
  document.getElementById('clipOn').checked = true;
  document.getElementById('clipPos').value = 500;
  updateClipFromUI();
});
document.getElementById('btnClipOff').addEventListener('click', () => {
  document.getElementById('clipOn').checked = false;
  updateClipFromUI();
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

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
  bloomPass.setSize(window.innerWidth, window.innerHeight);
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
  if (document.getElementById('bloom').checked) {
    composer.render();
  } else {
    renderer.render(scene, camera);
  }
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
    """Write ``viewer3d.html`` with section cut, cinematic bloom, Imagine studio assets."""
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

    sky = _b64_data_uri(_ASSETS / "studio_sky.jpg")
    floor = _b64_data_uri(_ASSETS / "floor_concrete.jpg")
    brand = _b64_data_uri(_ASSETS / "brand_mark.jpg")

    # Also copy assets into pack for inspection / external tools
    try:
        pack_assets = out / "assets"
        pack_assets.mkdir(exist_ok=True)
        for name in ("studio_sky.jpg", "floor_concrete.jpg", "brand_mark.jpg"):
            src = _ASSETS / name
            if src.is_file():
                dest = pack_assets / name
                if not dest.is_file() or dest.stat().st_size != src.stat().st_size:
                    dest.write_bytes(src.read_bytes())
    except Exception:  # noqa: BLE001
        pass

    html = (
        _VIEWER_HTML.replace("__EMBEDDED_GLTF__", embedded_js)
        .replace("__WALL_GHOST__", str(float(wall_ghost)))
        .replace("__SKY_URI__", json.dumps(sky))
        .replace("__FLOOR_URI__", json.dumps(floor))
        .replace("__BRAND_URI__", json.dumps(brand))
    )
    path = out / "viewer3d.html"
    path.write_text(html, encoding="utf-8")
    return path
