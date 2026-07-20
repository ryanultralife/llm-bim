"""Rich 3D review viewer: glTF element metadata + viewer UI hooks.

Covers:
- per-element glTF scene nodes carrying ``extras`` (id, name, category, level,
  key params such as system / nps / section)
- element index accessors staying local (valid) against their POSITION slices
- viewer3d.html shipping the new picking / filter-chip / measure UI
- optional Playwright smoke (skips without playwright, browser, or network)
"""

from __future__ import annotations

import base64
import json
import os
import struct
from pathlib import Path

import pytest
from llmbim import Project


def _build_pack(tmp_path: Path) -> tuple[Path, dict]:
    """Small multi-trade pack: wall, pipe, duct (L2), column."""
    p = Project.create("Rich3D", vcs=False)
    p.add_level("L1", 0)
    p.add_level("L2", 3500)
    p.create_wall(level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    p.place_pipe(level="L1", nps="3/4", start=(0, 500), end=(4000, 500), material="copper", system="CW")
    p.place_duct(level="L2", start=(0, 1500), end=(4000, 1500), width_mm=400, height_mm=250)
    p.place_column(level="L1", origin=(1000, 1000), section="W10x33", height_mm=3000)
    pack = tmp_path / "pack"
    pack.mkdir(exist_ok=True)
    p.export_gltf(pack / "model.gltf")
    data = json.loads((pack / "model.gltf").read_text(encoding="utf-8"))
    return pack, data


def _scene_nodes(data: dict) -> list[dict]:
    return [data["nodes"][i] for i in data["scenes"][data.get("scene", 0)]["nodes"]]


def test_gltf_scene_nodes_carry_element_extras(tmp_path: Path) -> None:
    _pack, data = _build_pack(tmp_path)
    scene_nodes = _scene_nodes(data)
    assert len(scene_nodes) == 4  # wall + pipe + duct + column
    for node in scene_nodes:
        ex = node.get("extras") or {}
        assert ex.get("id"), node
        assert ex.get("name"), node
        assert ex.get("category"), node
        assert ex.get("level") in {"L1", "L2"}, node
    by_cat = {n["extras"]["category"]: n["extras"] for n in scene_nodes}
    assert set(by_cat) == {"wall", "pipe", "duct", "column"}
    # key params surfaced for inspection
    pipe = by_cat["pipe"]
    assert pipe["params"]["nps"] == "3/4"
    assert pipe["params"]["system"] == "CW"
    assert pipe["level"] == "L1"
    assert by_cat["column"]["params"]["section"] == "W10x33"
    assert by_cat["duct"]["level"] == "L2"
    assert by_cat["wall"]["id"].startswith("wal_")
    # element ids are unique
    ids = [n["extras"]["id"] for n in scene_nodes]
    assert len(set(ids)) == len(ids)
    # top-level extras exposes level names for viewer isolation buttons
    assert data["extras"]["levels"] == ["L1", "L2"]


def test_gltf_element_indices_are_local_and_valid(tmp_path: Path) -> None:
    """Every scene-node primitive's indices must fit its own POSITION slice."""
    _pack, data = _build_pack(tmp_path)
    uri = data["buffers"][0]["uri"]
    blob = base64.b64decode(uri.split(",", 1)[1])
    for node in _scene_nodes(data):
        mesh = data["meshes"][node["mesh"]]
        assert mesh["primitives"], node
        for prim in mesh["primitives"]:
            pos_acc = data["accessors"][prim["attributes"]["POSITION"]]
            idx_acc = data["accessors"][prim["indices"]]
            bv = data["bufferViews"][idx_acc["bufferView"]]
            size, fmt = (2, "<H") if idx_acc["componentType"] == 5123 else (4, "<I")
            off = bv["byteOffset"] + idx_acc.get("byteOffset", 0)
            vals = [
                struct.unpack_from(fmt, blob, off + k * size)[0]
                for k in range(idx_acc["count"])
            ]
            assert max(vals) < pos_acc["count"], (node["name"], max(vals), pos_acc["count"])
            assert "material" in prim


def test_gltf_layered_wall_element_has_per_layer_primitives(tmp_path: Path) -> None:
    p = Project.create("Rich3D-layers", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(level="L1", start=(0, 0), end=(6000, 0), thickness_mm=200, height_mm=3000)
    p.set_type(w, "W-EXT-CMU")
    out = tmp_path / "layers.gltf"
    p.export_gltf(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    nodes = _scene_nodes(data)
    assert len(nodes) == 1
    ex = nodes[0]["extras"]
    assert ex["category"] == "wall"
    prims = data["meshes"][nodes[0]["mesh"]]["primitives"]
    assert len(prims) >= 2  # structure / insulation / finish layers
    mats = {data["materials"][p["material"]]["name"] for p in prims}
    assert mats & {"wall_structure", "wall_insulation", "wall_finish"}


def test_viewer3d_html_rich_ui_hooks(tmp_path: Path) -> None:
    from llmbim_drawings.viewer3d import write_viewer_3d

    pack, _data = _build_pack(tmp_path)
    path = write_viewer_3d(pack)
    assert path is not None and path.is_file()
    text = path.read_text(encoding="utf-8")
    # click-to-inspect (raycast picking + info card)
    assert 'id="inspect"' in text
    assert "pointerup" in text
    assert "pickAt" in text
    assert "selectElement" in text
    assert "clearSelection" in text
    # category chips + level isolation
    assert 'id="chips"' in text
    assert 'id="levelBtns"' in text
    assert "catGroup" in text
    # measure tool
    assert 'id="btnMeasure"' in text
    assert 'id="measureLabel"' in text
    assert "measureClick" in text
    # element metadata reaches the page (embedded glTF extras)
    assert '"extras"' in text or "extras" in text
    assert "elementIndex" in text
    # existing features must survive
    for hook in ("clipOn", "clipAxis", "ghostWalls", "globalAlpha",
                 "UnrealBloomPass", "studioSky", "localClippingEnabled"):
        assert hook in text, hook


def _find_chromium() -> str | None:
    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "", "/opt/pw-browsers"]
    for root in roots:
        if not root or not Path(root).is_dir():
            continue
        for pat in ("chromium_headless_shell-*/chrome-linux/headless_shell",
                    "chromium-*/chrome-linux/chrome"):
            for hit in sorted(Path(root).glob(pat)):
                if hit.is_file():
                    return str(hit)
    return None


def _unpkg_reachable() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen("https://unpkg.com/three@0.160.0/package.json", timeout=10):
            return True
    except Exception:  # noqa: BLE001 — any failure = no usable network
        return False


def test_viewer3d_browser_smoke(tmp_path: Path) -> None:
    """Optional: load viewer3d.html in headless chromium — no page errors.

    Skips when playwright / a chromium build / network to unpkg (three.js CDN)
    is unavailable.
    """
    pw_api = pytest.importorskip("playwright.sync_api")
    exe = _find_chromium()
    if not exe:
        pytest.skip("no chromium build under PLAYWRIGHT_BROWSERS_PATH or /opt/pw-browsers")
    if not _unpkg_reachable():
        pytest.skip("unpkg.com unreachable — three.js CDN needs network")

    from llmbim_drawings.viewer3d import write_viewer_3d

    pack, _data = _build_pack(tmp_path)
    assert write_viewer_3d(pack) is not None

    import functools
    import http.server
    import threading

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(pack)
    )
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    page_errors: list[str] = []
    try:
        with pw_api.sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=exe)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.on("pageerror", lambda e: page_errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{port}/viewer3d.html")
            # wait for boot: status leaves "Loading" once model builds
            for _ in range(60):
                status = page.text_content("#status") or ""
                if "Studio ready" in status or "elements" in status:
                    break
                page.wait_for_timeout(500)
            status = page.text_content("#status") or ""
            assert "Studio ready" in status, status
            # filter chips derived from scene extras
            chips = page.locator("#chips .chip").all_text_contents()
            assert any("walls" in c for c in chips), chips
            assert any("pipes" in c for c in chips), chips
            # level isolation buttons present (L1 + L2 in pack)
            lvls = page.locator("#levelBtns button").all_text_contents()
            assert "All levels" in lvls and "L1" in lvls and "L2" in lvls, lvls
            browser.close()
    finally:
        srv.shutdown()
    assert not page_errors, page_errors


def test_viewer_is_self_contained_offline(tmp_path):
    """viewer3d.html must bundle three.js inline — no CDN imports. A blocked or
    offline CDN previously meant a silent black 3D view for any agent/user."""
    from llmbim import Project

    p = Project.create("SelfContained", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000)
    man = p.export_deliverables(tmp_path / "pack")
    html = (tmp_path / "pack" / "viewer3d.html").read_text(encoding="utf-8")
    assert "unpkg.com" not in html and "cdn." not in html, "viewer depends on a CDN"
    assert "__LLMBIM_THREE__" in html, "bundled three.js runtime missing"
    assert "bootError" in html, "visible error banner missing"
    assert man["verification"]["viewer_self_contained"] is True
