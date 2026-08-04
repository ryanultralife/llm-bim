#!/usr/bin/env python3
"""Demo: hero product pipeline on a tiny skid pack.

Writes output/hero_product_demo/ with HERO_BRIEF + staged library still if present.

  python examples/hero_product_pipeline_demo.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Import module file directly so demo works without full editable install.
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "hero_product",
    ROOT / "packages" / "drawings" / "llmbim_drawings" / "hero_product.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
export_hero_pipeline = _mod.export_hero_pipeline


def main() -> None:
    out = ROOT / "examples" / "output" / "hero_product_demo"
    out.mkdir(parents=True, exist_ok=True)
    model = {
        "name": "Demo Process Skid",
        "elements": [
            {
                "category": "equipment",
                "name": "Chamber",
                "params": {
                    "equipment_tag": "CH-01",
                    "size_mm": [500, 2500, 700],
                    "origin_mm": [400, 400],
                    "z0_mm": 300,
                },
            },
            {
                "category": "equipment",
                "name": "Power",
                "params": {
                    "equipment_tag": "PWR",
                    "size_mm": [900, 700, 1800],
                    "origin_mm": [3200, 200],
                    "z0_mm": 0,
                },
            },
        ],
    }
    (out / "model.llmbim.json").write_text(json.dumps(model, indent=2), encoding="utf-8")
    man = export_hero_pipeline(
        out,
        product_id="mineclean",
        kind="skid",
        title="Demo Process Skid",
        use_library=True,
    )
    print(json.dumps(man, indent=2))
    print("OPEN:", (out / "renders" / "HERO_BRIEF.json").resolve())
    if man.get("product_hero"):
        print("HERO:", (out / "renders" / man["product_hero"]).resolve())


if __name__ == "__main__":
    main()
