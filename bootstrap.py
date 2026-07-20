"""Zero-install bootstrap — run the llm-bim kernel from an unzipped repo.

No pip, no venv, no network: the modeling kernel and full pack export are
pure standard-library Python (3.11+). From any Python session (including a
chat assistant's code sandbox) with the repo unzipped:

    import sys; sys.path.insert(0, "<repo_dir>")   # if not already cwd
    import bootstrap                                # this file
    from llmbim import Project

    p = Project.create("My Building")
    p.add_level("L1", 0)
    p.create_rect_shell(level="L1", x=0, y=0, w=7315, d=6096,
                        height_mm=3048, thickness_mm=171, name_prefix="B")
    man = p.export_deliverables("output/my_building")
    assert man.get("ok"), man                       # → output/my_building/index.html

Optional extras (server/MCP/CadQuery BREP) do need `pip install -e .[server]`;
nothing in the modeling/pack path does.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

for _pkg in sorted((_ROOT / "packages").iterdir()):
    if _pkg.is_dir() and str(_pkg) not in sys.path:
        sys.path.insert(0, str(_pkg))
