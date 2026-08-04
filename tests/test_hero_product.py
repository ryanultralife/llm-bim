"""Hero product still pipeline — brief + stage + library."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmbim_drawings.hero_product import (
    build_hero_brief,
    classify_kind,
    export_hero_pipeline,
    find_library_hero,
    stage_hero_render,
)


def test_classify_kind():
    assert classify_kind(product_id="mineclean", name="Field skid") == "skid"
    assert classify_kind(product_id="rmm_otd", name="Flywheel") == "device"
    assert classify_kind(name="INTEC facility campus") == "facility"
    assert classify_kind(hint="structure") == "structure"


def test_build_brief_from_minimal_pack(tmp_path: Path):
    model = {
        "name": "Demo Skid",
        "elements": [
            {
                "category": "equipment",
                "name": "CHAMBER",
                "params": {
                    "equipment_tag": "CH-01",
                    "size_mm": [500, 2500, 700],
                    "origin_mm": [0, 0],
                    "z0_mm": 200,
                },
            },
            {
                "category": "equipment",
                "name": "POWER",
                "params": {
                    "equipment_tag": "PWR",
                    "size_mm": [800, 600, 1800],
                    "origin_mm": [3000, 0],
                    "z0_mm": 0,
                },
            },
        ],
    }
    (tmp_path / "model.llmbim.json").write_text(json.dumps(model), encoding="utf-8")
    brief = build_hero_brief(tmp_path, product_id="demo_skid", kind="skid")
    assert brief["schema"] == "llmbim.hero_product_brief/v1"
    assert brief["kind"] == "skid"
    assert brief["envelope_mm"] is not None
    assert brief["envelope_mm"]["x_mm"] > 0
    assert len(brief["equipment_sample"]) == 2
    assert "Photoreal" in brief["prompt"] or "photoreal" in brief["prompt"].lower()
    assert "pipeline" in brief


def test_export_pipeline_stages_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # pack
    model = {"name": "MineClean", "elements": []}
    (tmp_path / "model.llmbim.json").write_text(json.dumps(model), encoding="utf-8")

    # fake library under a temp repo root
    lib_root = tmp_path / "repo"
    lib_dir = lib_root / "docs" / "renders" / "mineclean"
    lib_dir.mkdir(parents=True)
    hero = lib_dir / "field_skid_hero.jpg"
    hero.write_bytes(b"\xff\xd8\xfffakejpeg")  # minimal bytes; stage only copies

    monkeypatch.setattr(
        "llmbim_drawings.hero_product._repo_root",
        lambda: lib_root,
    )

    man = export_hero_pipeline(tmp_path, product_id="mineclean", kind="skid", use_library=True)
    assert man["status"] == "ready"
    assert man["product_hero"] is not None
    assert (tmp_path / "renders" / "HERO_BRIEF.json").is_file()
    assert (tmp_path / "renders" / "HERO_MANIFEST.json").is_file()
    assert (tmp_path / "renders" / "product_hero.jpg").is_file()


def test_stage_hero_render(tmp_path: Path):
    pack = tmp_path / "pack"
    pack.mkdir()
    src = tmp_path / "shot.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    dest = stage_hero_render(pack, src)
    assert dest.exists()
    assert dest.name.startswith("product_hero")


def test_find_library_mineclean_if_present():
    # live repo may have docs/renders/mineclean — soft check
    p = find_library_hero("mineclean")
    if p is not None:
        assert p.is_file()
        assert "mineclean" in p.as_posix().lower()
