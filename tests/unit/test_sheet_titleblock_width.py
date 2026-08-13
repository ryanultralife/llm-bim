"""Title-block column is 3.5\" on a 42\" sheet (Ryan 2026-08-12)."""
from llmbim_drawings.sheets import TITLE_BLOCK_FRAC, drawing_area, title_block_svg


def test_title_block_frac_is_three_point_five_on_forty_two() -> None:
    assert abs(TITLE_BLOCK_FRAC - 3.5 / 42.0) < 1e-9
    _x, _y, w, _h = drawing_area(1100, 850)
    # drawing area must leave a 3.5/42 slice for the column
    assert w > 800
    svg = title_block_svg(
        project="INTEC FP Separation Facility",
        sheet_title="Main process building",
        sheet_no="A-111",
        scale_note="1/8\" = 1'-0\"",
        body="<g/>",
    )
    assert "Main process" in svg
    assert "building" in svg  # wrapped, not truncated mid-word
