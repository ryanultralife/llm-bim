"""Hero product still pipeline — photoreal-class communication renders.

Engineering packs already produce:
  · sheets / construction set
  · specs + design basis
  · 3D (glTF / STEP / viewer)
  · layout product_views (AABB diagrams)

This module adds the **hero product still** as a first-class deliverable:
  renders/product_hero.*  (+ HERO_BRIEF.json + HERO_MANIFEST.json)

Hero stills are communication assets (pitch, NDA packs, studio index).
They do **not** replace fab drawings or SSOT geometry.

Pipeline stages
---------------
1. **Brief** — write a structured prompt + envelope facts from the pack
2. **Stage** — copy an existing still into ``renders/product_hero.*``
3. **Library** — pull from ``docs/renders/<product>/`` when present
4. **Hook** — agents / external Imagine tools fill the brief (see recipe)

Usage::

    from llmbim_drawings.hero_product import export_hero_pipeline
    man = export_hero_pipeline(pack_dir, product_id="mineclean", kind="skid")

Honesty: stills are ENGINEERING ESTIMATE visualizations unless tagged higher.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

HeroKind = Literal["device", "skid", "structure", "facility"]

# Preferred on-disk names for the pack
HERO_BASENAME = "product_hero"
BRIEF_NAME = "HERO_BRIEF.json"
MANIFEST_NAME = "HERO_MANIFEST.json"

# Product library under repo docs/renders/<id>/
LIBRARY_HERO_NAMES = (
    "field_skid_hero.jpg",
    "skid_hero.jpg",
    "hero.jpg",
    "product_hero.jpg",
    "line_hero.jpg",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repo_root() -> Path:
    # packages/drawings/llmbim_drawings/hero_product.py → repo root
    return Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _equipment_summary(model: dict[str, Any], limit: int = 24) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for el in model.get("elements") or []:
        if el.get("category") != "equipment":
            continue
        p = el.get("params") or {}
        size = p.get("size_mm") or []
        if len(size) < 3:
            continue
        tag = (
            p.get("equipment_tag")
            or p.get("equipment")
            or p.get("mark")
            or el.get("name")
            or "EQ"
        )
        rows.append(
            {
                "tag": str(tag)[:24],
                "name": str(p.get("equipment_name") or el.get("name") or tag)[:48],
                "size_mm": [float(size[0]), float(size[1]), float(size[2])],
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _envelope_mm(model: dict[str, Any]) -> dict[str, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for el in model.get("elements") or []:
        p = el.get("params") or {}
        size = p.get("size_mm") or []
        origin = p.get("origin_mm") or [0, 0]
        if len(size) < 3:
            continue
        w, d, h = float(size[0]), float(size[1]), float(size[2])
        ox, oy = float(origin[0]), float(origin[1])
        z0 = float(p.get("z0_mm") or 0.0)
        xs += [ox, ox + w]
        ys += [oy, oy + d]
        zs += [z0, z0 + h]
    if not xs:
        return None
    return {
        "x_mm": max(xs) - min(xs),
        "y_mm": max(ys) - min(ys),
        "z_mm": max(zs) - min(zs),
        "x0_mm": min(xs),
        "y0_mm": min(ys),
        "z0_mm": min(zs),
    }


def classify_kind(
    *,
    product_id: str | None = None,
    name: str | None = None,
    hint: HeroKind | None = None,
) -> HeroKind:
    if hint:
        return hint
    blob = f"{product_id or ''} {name or ''}".lower()
    if any(k in blob for k in ("skid", "mclean", "mineclean", "melt", "module", "pack")):
        return "skid"
    if any(k in blob for k in ("facility", "plant", "building", "site", "campus")):
        return "facility"
    if any(k in blob for k in ("structure", "frame", "building", "bay", "cell")):
        return "structure"
    return "device"


def build_hero_brief(
    pack_dir: str | Path,
    *,
    product_id: str | None = None,
    kind: HeroKind | None = None,
    title: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured hero-render brief from a deliverables pack."""
    out = Path(pack_dir)
    model = _load_json(out / "model.llmbim.json")
    manifest = _load_json(out / "MANIFEST.json")
    basis = {}
    for cand in out.glob("*_basis.json"):
        basis = _load_json(cand)
        if basis:
            break
    # also common names
    if not basis:
        for name in ("mineclean_basis.json", "rmm_otd_basis.json", "design_basis.json"):
            basis = _load_json(out / name)
            if basis:
                break

    proj = (
        (manifest.get("project") if isinstance(manifest, dict) else None)
        or model.get("name")
        or out.name
    )
    pid = product_id or str(basis.get("product_family") or basis.get("name") or proj).lower().replace(" ", "_")
    hkind = classify_kind(product_id=pid, name=str(proj), hint=kind)
    env = _envelope_mm(model)
    equip = _equipment_summary(model)

    # Scene recipes by kind (agent / Imagine prompt seeds)
    scenes = {
        "device": (
            "Photoreal industrial product photograph of a precision process device on a "
            "clean factory floor, soft studio lighting, copper and steel materials, "
            "no people, no logos, no readable text, cinematic but engineering-believable."
        ),
        "skid": (
            "Photoreal industrial product photograph of a complete process skid package "
            "(ISO container-class or factory skid), brushed stainless and painted steel, "
            "Nevada industrial yard or clean bay, soft late-afternoon light, "
            "crane padeyes visible if present, no people, no logos, no readable text."
        ),
        "structure": (
            "Photoreal architectural/industrial photograph of a process structure or "
            "support frame, concrete pad and steel, clear massing, soft daylight, "
            "no people, no logos, no readable text."
        ),
        "facility": (
            "Photoreal wide view of an industrial process facility or cold campus exterior "
            "at golden hour, concrete and steel, restrained and serious, "
            "no people, no logos, no readable signs."
        ),
    }

    locks = basis.get("locks") if isinstance(basis.get("locks"), dict) else {}
    duty = basis.get("duty") if isinstance(basis.get("duty"), dict) else {}
    geom = basis.get("geometry_mm") if isinstance(basis.get("geometry_mm"), dict) else {}

    brief: dict[str, Any] = {
        "schema": "llmbim.hero_product_brief/v1",
        "generated_at": _utc_now(),
        "honesty": (
            "ENGINEERING ESTIMATE visualization — communication still only; "
            "geometry/performance SSOT remains design basis + pack model"
        ),
        "product_id": pid,
        "title": title or str(proj),
        "kind": hkind,
        "pack_dir": str(out.resolve()),
        "envelope_mm": env,
        "equipment_sample": equip,
        "design_basis_keys": sorted(basis.keys())[:40] if basis else [],
        "locks": locks,
        "duty": duty,
        "geometry_mm": geom,
        "prompt_seed": scenes[hkind],
        "prompt": _compose_prompt(
            title=title or str(proj),
            kind=hkind,
            env=env,
            equip=equip,
            duty=duty,
            geom=geom,
            seed=scenes[hkind],
        ),
        "outputs": {
            "hero": f"renders/{HERO_BASENAME}.jpg",
            "aliases": [f"renders/{HERO_BASENAME}.png", f"renders/{HERO_BASENAME}.webp"],
            "brief": f"renders/{BRIEF_NAME}",
            "manifest": f"renders/{MANIFEST_NAME}",
        },
        "pipeline": [
            "1. export_deliverables / studio pack (sheets + 3D + specs)",
            "2. export_hero_pipeline → HERO_BRIEF.json",
            "3. Generate still from brief (agent Imagine / external renderer)",
            "4. stage_hero_render(pack, image) → renders/product_hero.*",
            "5. index.html features product hero alongside 3D axonometric hero.svg",
        ],
        "related_pack_artifacts": _list_related(out),
        "extra": extra or {},
    }
    return brief


def _compose_prompt(
    *,
    title: str,
    kind: str,
    env: dict[str, float] | None,
    equip: list[dict[str, Any]],
    duty: dict[str, Any],
    geom: dict[str, Any],
    seed: str,
) -> str:
    bits = [seed, f"Subject: {title} ({kind})."]
    if env:
        bits.append(
            f"Approximate envelope ~{env['x_mm']:.0f}×{env['y_mm']:.0f}×{env['z_mm']:.0f} mm."
        )
    if geom:
        # pick a few human dims
        for k in ("skid_L", "skid_W", "skid_H_overall", "chamber_L", "chamber_ID"):
            if k in geom:
                bits.append(f"{k}={geom[k]}")
    if duty:
        for k in ("flow_m3_h", "power_kW", "primary_mode"):
            if k in duty:
                bits.append(f"{k}={duty[k]}")
    if equip:
        tags = ", ".join(e["tag"] for e in equip[:8])
        bits.append(f"Visible equipment tags (approx layout): {tags}.")
    bits.append(
        "Match mechanical-battery brand still language: cream/copper industrial, "
        "sharp product photography, full-frame subject filling the frame."
    )
    return " ".join(bits)


def _list_related(out: Path) -> dict[str, bool]:
    return {
        "hero_svg": (out / "hero.svg").is_file(),
        "viewer3d": (out / "viewer3d.html").is_file(),
        "model_gltf": (out / "model.gltf").is_file(),
        "model_step": (out / "model.step").is_file(),
        "plot_set": (out / "PLOT_SET.pdf").is_file(),
        "product_views": any((out / "renders").glob("R*.png")) if (out / "renders").is_dir() else False,
        "sheets": (out / "sheets").is_dir() or (out / "construction").is_dir(),
    }


def stage_hero_render(
    pack_dir: str | Path,
    image: str | Path,
    *,
    basename: str = HERO_BASENAME,
) -> Path:
    """Copy a finished still into ``renders/product_hero.<ext>``."""
    out = Path(pack_dir)
    src = Path(image)
    if not src.is_file():
        raise FileNotFoundError(src)
    renders = out / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    dest = renders / f"{basename}{ext}"
    shutil.copy2(src, dest)
    # also maintain .jpg alias if we got png
    if ext != ".jpg":
        alias = renders / f"{basename}.jpg"
        if not alias.exists():
            try:
                shutil.copy2(src, alias)
            except OSError:
                pass
    return dest


def find_library_hero(product_id: str, repo_root: Path | None = None) -> Path | None:
    """Locate a committed hero still under docs/renders/<product_id>/."""
    root = repo_root or _repo_root()
    lib = root / "docs" / "renders" / product_id.lower().replace(" ", "_")
    if not lib.is_dir():
        # soft aliases
        aliases = {
            "mb-mclean": "mineclean",
            "mb_mclean": "mineclean",
            "mclean": "mineclean",
            "ti": "mb_ti_melt",
            "ti_melt": "mb_ti_melt",
            "mb-ti-melt": "mb_ti_melt",
            "rmm": "rmm_otd",
            "rmm-otd": "rmm_otd",
        }
        lib = root / "docs" / "renders" / aliases.get(product_id.lower(), product_id)
    if not lib.is_dir():
        return None
    for name in LIBRARY_HERO_NAMES:
        p = lib / name
        if p.is_file():
            return p
    # any jpg/png
    for p in sorted(lib.glob("*.jpg")) + sorted(lib.glob("*.png")):
        return p
    return None


def export_hero_pipeline(
    pack_dir: str | Path,
    *,
    product_id: str | None = None,
    kind: HeroKind | None = None,
    title: str | None = None,
    stage_from: str | Path | None = None,
    use_library: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the hero pipeline on a pack: brief + optional stage from file/library.

    Returns a small manifest dict (also written to renders/HERO_MANIFEST.json).
    """
    out = Path(pack_dir)
    out.mkdir(parents=True, exist_ok=True)
    renders = out / "renders"
    renders.mkdir(parents=True, exist_ok=True)

    brief = build_hero_brief(
        out, product_id=product_id, kind=kind, title=title, extra=extra
    )
    pid = str(brief["product_id"])
    (renders / BRIEF_NAME).write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")

    staged: str | None = None
    source = "none"
    # explicit path wins
    if stage_from:
        dest = stage_hero_render(out, stage_from)
        staged = dest.name
        source = f"explicit:{Path(stage_from).name}"
    elif use_library:
        lib = find_library_hero(pid)
        if lib is not None:
            dest = stage_hero_render(out, lib)
            staged = dest.name
            source = f"library:{lib.as_posix()}"

    # detect existing product_hero
    existing = None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = renders / f"{HERO_BASENAME}{ext}"
        if p.is_file():
            existing = p.name
            break

    man = {
        "schema": "llmbim.hero_product_manifest/v1",
        "generated_at": _utc_now(),
        "product_id": pid,
        "kind": brief["kind"],
        "title": brief["title"],
        "brief": f"renders/{BRIEF_NAME}",
        "product_hero": existing or staged,
        "source": source if staged else ("existing" if existing else "brief_only"),
        "status": "ready" if (existing or staged) else "needs_render",
        "honesty": brief["honesty"],
        "prompt": brief["prompt"],
        "related": brief["related_pack_artifacts"],
        "note": (
            "If status=needs_render: use prompt in HERO_BRIEF.json with an image model "
            "(agent Imagine or external), then stage_hero_render(pack, path)."
        ),
    }
    (renders / MANIFEST_NAME).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return man


def hero_path(pack_dir: str | Path) -> Path | None:
    """Return path to staged product_hero if present."""
    renders = Path(pack_dir) / "renders"
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = renders / f"{HERO_BASENAME}{ext}"
        if p.is_file():
            return p
    return None
