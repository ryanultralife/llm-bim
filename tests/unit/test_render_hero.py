"""Tests for the baked shaded axonometric hero SVG render."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_SCHAD = Path(__file__).resolve().parents[2] / "projects" / "schad"
if str(_SCHAD) not in sys.path:
    sys.path.insert(0, str(_SCHAD))

from llmbim_geometry.render_hero import render_hero_svg  # noqa: E402

_SVG_NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def schad_model():  # type: ignore[no-untyped-def]
    from build_llmbim import build_model

    res = build_model()
    p = res[0] if isinstance(res, tuple) else res
    return getattr(p, "model", p)


def test_render_hero_svg_is_well_formed(schad_model, tmp_path):  # type: ignore[no-untyped-def]
    out = render_hero_svg(schad_model, tmp_path / "hero.svg")
    assert out.exists()
    text = out.read_text(encoding="utf-8")

    # Valid, parseable XML.
    root = ET.fromstring(text)
    assert root.tag == f"{_SVG_NS}svg"

    # Non-trivial deliverable (the building has thousands of triangles).
    assert out.stat().st_size > 20_000

    # Hundreds of shaded polygons.
    polys = root.findall(f".//{_SVG_NS}polygon")
    assert len(polys) > 200

    # The gradient background and the honesty footer are present.
    assert root.find(f".//{_SVG_NS}linearGradient") is not None
    assert "NOT FOR CONSTRUCTION" in text


def test_render_hero_svg_has_distinct_shaded_colors(schad_model, tmp_path):  # type: ignore[no-untyped-def]
    out = render_hero_svg(schad_model, tmp_path / "hero.svg")
    root = ET.fromstring(out.read_text(encoding="utf-8"))
    fills = {
        p.get("fill")
        for p in root.findall(f".//{_SVG_NS}polygon")
        if p.get("fill")
    }
    # Flat Lambert + multiple materials must yield many distinct fills; at the
    # very least far more than a couple, proving the shading actually varies.
    assert len(fills) > 10


def test_render_hero_svg_is_deterministic(schad_model, tmp_path):  # type: ignore[no-untyped-def]
    a = render_hero_svg(schad_model, tmp_path / "a.svg").read_bytes()
    b = render_hero_svg(schad_model, tmp_path / "b.svg").read_bytes()
    assert a == b  # byte-identical: no RNG, no wall-clock
