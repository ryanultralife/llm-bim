"""INTEC construction set — one command (Schad-style).

Builds the full MB-INT-CAD-001 sheet spine (128 sheets / 13 disciplines)
as an llm-bim pack under ``output/intec_construction/``.

  python projects/intec/build_construction_set.py
  python projects/intec/build_construction_set.py --out output/intec_cd
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from build_llmbim import build_pack  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Build INTEC llm-bim construction set")
    ap.add_argument(
        "--out",
        type=Path,
        default=_ROOT / "output" / "intec_construction",
        help="Output pack directory",
    )
    args = ap.parse_args()
    print("=== INTEC construction set (MB-INT-CAD-001) ===")
    print("out:", args.out.resolve())
    _p, verify = build_pack(args.out)
    ok = bool(verify.get("ok"))
    print("DONE ok=", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
