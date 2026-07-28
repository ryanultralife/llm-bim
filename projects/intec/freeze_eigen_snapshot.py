"""Re-freeze Eigen engine outputs into data/eigen_systems_snapshot.json.

Requires Eigen checkout with scripts/ on PYTHONPATH (default sibling path).

  python projects/intec/freeze_eigen_snapshot.py
  python projects/intec/freeze_eigen_snapshot.py --eigen <path-to-local-Eigen-checkout>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DEFAULT_EIGEN = _HERE.parents[1].parent / "Eigen"  # sibling of llm-bim


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eigen", type=Path, default=_DEFAULT_EIGEN)
    args = ap.parse_args()
    scripts = args.eigen / "scripts"
    if not scripts.is_dir():
        print("Eigen scripts not found:", scripts, file=sys.stderr)
        return 2
    sys.path.insert(0, str(scripts))
    sys.path.insert(0, str(args.eigen))

    import intec_bid_basis as bid
    import intec_facility_systems as fs
    import intec_module_basis as mod

    pack = {
        "source": f"Eigen/scripts freeze {date.today().isoformat()}",
        "honesty": (
            "[ENGINEERING ESTIMATE] design-basis from intec_facility_systems / "
            "bid_basis / module_basis"
        ),
        "support_rooms": fs.support_rooms(),
        "lighting": fs.lighting(),
        "electrical": fs.electrical(),
        "hvac": fs.hvac(),
        "plumbing": fs.plumbing(),
        "fire": fs.fire(),
        "rad_monitoring": fs.rad_monitoring(),
        "controls": fs.controls(),
        "doors_windows": fs.doors_windows(),
        "door_instances": fs.door_instances(),
        "hvac_equipment": fs.hvac_equipment(),
        "panel_circuits": fs.panel_circuits(),
        "plumbing_connections": fs.plumbing_connections(),
        "logistics": fs.logistics(),
        "egress": fs.egress(),
        "site": fs.site(),
        "bid_quantities": bid.QUANTITIES,
        "bid_scope": bid.SCOPE,
        "bid_assumptions": bid.ASSUMPTIONS,
        "bid_allowances": bid.ALLOWANCES,
        "bid_exclusions": bid.EXCLUSIONS,
        "room_crosswalk": getattr(bid, "ROOM_CROSSWALK", None),
        "module_stations": {
            k: {kk: vv for kk, vv in v.items()} for k, v in mod.STATIONS.items()
        },
        "module_connections": mod.CONNECTIONS,
        "module_modules": mod.MODULES,
        "module_equipment": getattr(mod, "EQUIPMENT", {}),
        "module_materials": getattr(mod, "MATERIALS", {}),
    }
    out = _HERE / "data" / "eigen_systems_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(pack, indent=2, default=str) + "\n", encoding="utf-8")
    print("wrote", out, "bytes", out.stat().st_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
