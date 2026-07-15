#!/usr/bin/env python3
"""Regenerate real cases and fail if packs are incomplete."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages" / "sdk"))
sys.path.insert(0, str(ROOT / "packages" / "core"))
sys.path.insert(0, str(ROOT / "packages" / "geometry"))
sys.path.insert(0, str(ROOT / "packages" / "drawings"))
sys.path.insert(0, str(ROOT / "packages" / "ifc"))

from examples.intec_site import build_intec  # noqa: E402
from examples.proto10_separator import build_proto10  # noqa: E402
from llmbim_drawings.deliverables import verify_pack  # noqa: E402


def main() -> int:
    out_i = ROOT / "examples" / "output" / "intec"
    out_p = ROOT / "examples" / "output" / "proto10"
    print("Building INTEC…")
    build_intec(out_i)
    print("Building Proto10…")
    build_proto10(out_p)

    vi = verify_pack(out_i, require_parts=True)
    vp = verify_pack(out_p, require_parts=True)
    print("INTEC verify:", json.dumps(vi, indent=2))
    print("Proto10 verify:", json.dumps(vp, indent=2))

    # Read manifests
    for label, path in ("intec", out_i), ("proto10", out_p):
        man = json.loads((path / "MANIFEST.json").read_text(encoding="utf-8"))
        print(f"{label} MANIFEST.ok={man.get('ok')} errors={len(man.get('errors') or [])}")
        if man.get("errors"):
            print(json.dumps(man["errors"], indent=2))

    ok = vi.get("ok") and vp.get("ok")
    if not ok:
        print("VERIFY FAILED", file=sys.stderr)
        return 1
    print("ALL PACKS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
