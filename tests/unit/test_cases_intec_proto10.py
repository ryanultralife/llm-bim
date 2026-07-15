"""Real project test cases: INTEC site + Proto10 separator."""

from __future__ import annotations

from pathlib import Path

from examples.intec_site import build_intec
from examples.proto10_separator import build_proto10


def test_intec_site(tmp_path: Path) -> None:
    p = build_intec(tmp_path / "intec")
    s = p.stats()
    assert s["wall"] >= 4
    assert s.get("equipment", 0) >= 6  # vessels + stack
    assert s.get("room", 0) >= 10
    root = tmp_path / "intec"
    assert (root / "model.llmbim.json").is_file()
    assert (root / "model.ifc").is_file()
    assert (root / "model.step").is_file()
    assert (root / "model.gltf").is_file()
    assert (root / "construction" / "A-101_plan.svg").is_file()
    assert (root / "MANIFEST.json").is_file()
    assert "IFCPROJECT" in (root / "model.ifc").read_text(encoding="utf-8")
    assert "MANIFOLD_SOLID_BREP" in (root / "model.step").read_text(encoding="utf-8")
    errors = [i for i in p.validate() if i["severity"] == "error"]
    assert not errors


def test_proto10(tmp_path: Path) -> None:
    p = build_proto10(tmp_path / "p10")
    s = p.stats()
    assert s.get("equipment", 0) >= 8  # pedestal, yoke, shell, 2 flanges, cartridge, 4 magnets
    root = tmp_path / "p10"
    assert (root / "model.step").is_file()
    assert (root / "parts" / "PARTS_INDEX.json").is_file()
    steps = list((root / "parts" / "step").glob("*.step"))
    assert len(steps) >= 8
    ga = root / "parts" / "drawings" / "P-000_assembly_GA.svg"
    assert ga.is_file()
    text = ga.read_text(encoding="utf-8")
    assert "<svg" in text.lower()
