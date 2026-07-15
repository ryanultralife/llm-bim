"""Safe-ish script runner for user/agent building scripts.

Provides a restricted global namespace with Project API only.
Does NOT use full sandbox isolation (no subprocess jail) — for trusted agents.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any


def run_script(
    source: str | Path,
    *,
    project: Any | None = None,
    outfile: str | Path | None = None,
) -> dict[str, Any]:
    """Execute a Python script with `project` bound.

    Script may define `build(project)` or use free-form code with name `project`.
    """
    from llmbim import Project

    code = Path(source).read_text(encoding="utf-8") if Path(str(source)).is_file() else str(source)
    p = project or Project.create("Script Project")
    glb: dict[str, Any] = {
        "__name__": "__llmbim_script__",
        "Project": Project,
        "project": p,
        "p": p,
    }
    # minimal safe builtins
    safe_builtins = {
        "abs": abs,
        "min": min,
        "max": max,
        "range": range,
        "len": len,
        "enumerate": enumerate,
        "zip": zip,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "float": float,
        "int": int,
        "str": str,
        "bool": bool,
        "print": print,
        "True": True,
        "False": False,
        "None": None,
        "round": round,
        "sum": sum,
    }
    glb["__builtins__"] = safe_builtins
    try:
        exec(compile(code, str(source), "exec"), glb, glb)  # noqa: S102
        if callable(glb.get("build")):
            glb["build"](p)
        if outfile:
            p.save(outfile)
        return {"ok": True, "stats": p.stats(), "name": p.name, "project": p}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "trace": traceback.format_exc()[-2000:],
            "stats": p.stats(),
        }
