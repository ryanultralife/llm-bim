"""Elevation/section include pipe markers; clash includes pipe-pipe."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.clash import find_clashes
from llmbim_drawings.section import write_elevation_svg, write_section_svg


def test_elevation_draws_pipes(tmp_path: Path) -> None:
    p = Project.create("ElevMEP", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    eid = p.place_pipe(level="L1", nps="1", start=(500, 500), end=(7000, 500), material="copper")
    p.model.get_element(eid).params["z0_mm"] = 2400
    out = tmp_path / "elev_S.svg"
    write_elevation_svg(p.model, "S", out, scale=0.02)
    text = out.read_text(encoding="utf-8")
    assert 'class="pipes-elev"' in text
    assert "<line " in text


def test_section_draws_pipe_circles(tmp_path: Path) -> None:
    p = Project.create("SecMEP", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(0, 5000), thickness_mm=200, height_mm=3000)
    # pipe parallel to cut, near cut line y=1000
    eid = p.place_pipe(level="L1", nps="2", start=(1000, 1000), end=(4000, 1000), material="fire")
    p.model.get_element(eid).params["z0_mm"] = 2000
    out = tmp_path / "sec.svg"
    # cut along X at y≈1000
    write_section_svg(p.model, (0, 1000), (5000, 1000), out, scale=0.02, depth_mm=800)
    text = out.read_text(encoding="utf-8")
    assert 'class="pipes-section"' in text
    assert "<circle " in text


def test_section_draws_duct_conduit_tray(tmp_path: Path) -> None:
    p = Project.create("SecMEP-multi", vcs=False)
    p.add_level("L1", 0)
    # cut along X at y=2000; place multi-trade near cut
    p.place_duct(
        level="L1",
        start=(0, 2000),
        end=(5000, 2000),
        width_mm=400,
        height_mm=250,
        z0_mm=2800,
    )
    p.place_conduit(
        level="L1",
        start=(0, 2100),
        end=(5000, 2100),
        trade_size="1",
        z0_mm=2700,
    )
    p.place_cable_tray(
        level="L1",
        start=(0, 1900),
        end=(5000, 1900),
        width_mm=300,
        height_mm=100,
        z0_mm=2900,
    )
    out = tmp_path / "sec_mep.svg"
    write_section_svg(p.model, (0, 2000), (6000, 2000), out, scale=0.02, depth_mm=800)
    text = out.read_text(encoding="utf-8")
    assert 'class="pipes-section"' in text
    assert "<circle " in text
    # multi-trade colors: green duct / purple conduit-tray
    assert "#2e7d32" in text or "#6a1b9a" in text


def test_pipe_pipe_clash():
    p = Project.create("ClashPipe", vcs=False)
    p.add_level("L1", 0)
    p.place_pipe(level="L1", nps="2", start=(0, 0), end=(3000, 0), material="copper")
    p.place_pipe(level="L1", nps="2", start=(0, 0), end=(3000, 0), material="copper")
    c = find_clashes(p.model)
    assert any(
        {x["a_category"], x["b_category"]} <= {"pipe", "plumbing_pipe"}
        or "pipe" in (x["a_category"], x["b_category"])
        for x in c
    )


def test_elevation_draws_columns_and_beams(tmp_path: Path) -> None:
    p = Project.create("ElevStruct", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3500)
    p.place_column(level="L1", origin=(3000, 500), section="W10x33", height_mm=3500)
    p.place_beam(level="L1", start=(0, 500), end=(8000, 500), section="W12x26", z0_mm=3000)
    out = tmp_path / "elev_S.svg"
    write_elevation_svg(p.model, "S", out, scale=0.02)
    text = out.read_text(encoding="utf-8")
    assert 'class="columns-elev"' in text
    assert "W10x33" in text
    # beam drawn as elev line/rect stroke
    assert 'class="pipes-elev"' in text or "<rect " in text


def test_elevation_svg_doors_and_windows(tmp_path: Path) -> None:
    p = Project.create("ElevOpen", vcs=False)
    p.add_level("L1", 0)
    w = p.create_wall(
        level="L1", start=(0, 0), end=(10000, 0), thickness_mm=200, height_mm=3000
    )
    p.place_door(
        host=w,
        offset_mm=2000,
        width_mm=900,
        height_mm=2100,
        type_id="D-HM-36",
        fire_rating="90 min",
    )
    p.place_window(
        host=w,
        offset_mm=5000,
        width_mm=1200,
        height_mm=900,
        sill_mm=900,
        type_id="WIN-VIEW",
    )
    out = tmp_path / "elev_S.svg"
    write_elevation_svg(p.model, "S", out, scale=0.02)
    text = out.read_text(encoding="utf-8")
    assert 'class="openings-elev"' in text
    assert "HM-36" in text or "D-HM" in text
    assert "90m" in text or "90" in text
    assert "WIN" in text or "VIEW" in text


def test_section_svg_doors_and_windows(tmp_path: Path):
    p = Project.create("sec-open-svg", vcs=False)
    p.add_level("L1", 0)
    # wall crosses NS cut at x=4000
    w = p.create_wall(
        level="L1", start=(0, 2000), end=(8000, 2000), thickness_mm=200, height_mm=3000
    )
    p.place_door(
        host=w,
        offset_mm=3500,
        width_mm=900,
        height_mm=2100,
        type_id="D-HM-36",
        fire_rating="90 min",
    )
    p.place_window(
        host=w,
        offset_mm=1000,
        width_mm=1000,
        height_mm=900,
        sill_mm=900,
        type_id="WIN-VIEW",
    )
    out = tmp_path / "section.svg"
    write_section_svg(p.model, (4000, -1000), (4000, 5000), out, scale=0.02, depth_mm=800)
    text = out.read_text(encoding="utf-8")
    assert 'class="openings-section"' in text
    assert "HM-36" in text or "D-HM" in text
    assert "WIN" in text or "VIEW" in text
