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
    assert (tmp_path / "intec" / "intec_plan_L0.svg").is_file()
    assert (tmp_path / "intec" / "intec_plan_L0.svg").stat().st_size > 500
    errors = [i for i in p.validate() if i["severity"] == "error"]
    assert not errors


def test_proto10(tmp_path: Path) -> None:
    p = build_proto10(tmp_path / "p10")
    s = p.stats()
    assert s.get("equipment", 0) >= 8  # pedestal, yoke, shell, 2 flanges, cartridge, 4 magnets
    assert (tmp_path / "p10" / "proto10_plan.svg").is_file()
    text = (tmp_path / "p10" / "proto10_plan.svg").read_text(encoding="utf-8")
    assert "<svg" in text.lower()
    assert "shell" in text.lower() or "Al6061" in text or "equipment" in text.lower()
