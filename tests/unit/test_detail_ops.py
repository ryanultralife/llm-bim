"""Detail ops DSL renderer (WP-SCHAD-S5) — schad detail data → SVG DrawingViews."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from llmbim_core.errors import ValidationError
from llmbim_drawings.detail_ops import (
    SUPPORTED_OPS,
    format_feet_inches,
    render_detail_ops,
    render_detail_sheet,
    scale_note_from_ratio,
)

_SCHAD_DIR = Path(__file__).resolve().parents[2] / "projects" / "schad"


def _schad_details() -> list[dict]:
    """Load detail dicts from projects/schad (data stays in the project module)."""
    for name in ("schad_details", "details"):
        path = _SCHAD_DIR / f"{name}.py"
        if not path.is_file():
            continue
        sys.path.insert(0, str(_SCHAD_DIR))
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            assert spec and spec.loader
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return list(mod.build_details())
        except ImportError as exc:  # basis module renamed mid-port — skip, don't fail
            pytest.skip(f"projects/schad details not importable: {exc}")
        finally:
            sys.path.remove(str(_SCHAD_DIR))
    pytest.skip("projects/schad details module not present")
    return []


def test_render_d01_from_schad_data() -> None:
    details = _schad_details()
    assert details, "schad build_details() returned nothing"
    d01 = details[0]
    assert d01["id"] == "D01"
    view = render_detail_ops(d01["ops"], scale=24.0, title=d01["title"])
    assert view.width > 0 and view.height > 0
    body = view.body
    assert body.strip(), "D01 rendered empty"
    # D01 carries lines, rects (footing/plates), circles (rebar), hatch, labels
    assert "<line" in body
    assert "<rect" in body
    assert "<circle" in body
    assert "<text" in body
    assert 'class="hatch"' in body
    assert "stroke-dasharray" in body  # 'd' dashed gravel line
    assert "STANDING SEAM" in body  # label text survives (wrapped tspans)


def test_all_schad_details_render() -> None:
    details = _schad_details()
    assert len(details) >= 12
    for det in details:
        view = render_detail_ops(det["ops"], scale=24.0, title=det["title"])
        assert view.width > 0 and view.height > 0 and "<" in view.body, det["id"]


def test_dim_op_extension_lines_and_feet_inches_text() -> None:
    view = render_detail_ops(
        [("l", 0, 0, 4, 0), ("dim", 0, 0, 4, 0, 0.8)], scale=30.0
    )
    body = view.body
    assert "4'-0\"" in body
    assert 'class="dim"' in body
    # dim group: 2 extension lines + dim line + 2 ticks = 5 <line> elements
    dim_part = body.split('class="dim"', 1)[1]
    assert dim_part.count("<line") >= 5


def test_feet_inches_formatting() -> None:
    assert format_feet_inches(3.5) == "3'-6\""
    assert format_feet_inches(0.53125) == "0'-6 3/8\""
    assert format_feet_inches(10.0) == "10'-0\""
    assert format_feet_inches(1.0 + 1.0 / 24.0) == "1'-0 1/2\""


def test_scale_notes_from_detail_ratio() -> None:
    assert scale_note_from_ratio(12) == '1" = 1\'-0"'
    assert scale_note_from_ratio(8) == '1 1/2" = 1\'-0"'
    assert scale_note_from_ratio(16) == '3/4" = 1\'-0"'
    assert scale_note_from_ratio(0) == "NTS"


def test_unknown_op_raises_listing_supported() -> None:
    with pytest.raises(ValidationError) as ei:
        render_detail_ops([("q", 0, 0, 1, 1)])
    msg = str(ei.value)
    for code in SUPPORTED_OPS:
        assert code in msg
    assert ei.value.details["supported_ops"] == list(SUPPORTED_OPS)


def test_malformed_op_args_raise() -> None:
    with pytest.raises(ValidationError):
        render_detail_ops([("l", 0, 0)])  # too few coords
    with pytest.raises(ValidationError):
        render_detail_ops([("c", 0, "x", 1)])  # non-numeric
    with pytest.raises(ValidationError):
        render_detail_ops([])  # no ops at all


def test_detail_sheet_composes_4up_with_labels() -> None:
    details = _schad_details()[:4]
    sheet = render_detail_sheet(details, width=860, height=740)
    body = sheet.body
    assert body.count('class="view-cell"') == 4
    for det in details:
        assert det["id"] in body  # D01…D04 labels present
    # scale note derived from each detail's ratio rides in the label
    assert "3/4&quot; = 1'-0&quot;" in body or "3/4\" = 1'-0\"" in body


def test_detail_sheet_rejects_more_than_four() -> None:
    details = _schad_details()
    with pytest.raises(ValidationError):
        render_detail_sheet(details[:5])
    with pytest.raises(ValidationError):
        render_detail_sheet([])
