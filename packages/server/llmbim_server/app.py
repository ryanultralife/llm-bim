"""FastAPI application — primary launch surface for LLM agents."""

from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from llmbim import __version__ as sdk_version
from llmbim_core.errors import BimError
from llmbim_core.validate import validate_model
from llmbim_drawings import export_elevation_svg, export_plan_svg, export_section_svg
from llmbim_drawings.schedules import export_schedule_csv, schedule_rows
from llmbim_geometry.mesh import export_gltf_walls
from llmbim_server.store import ProjectStore

API_KEY = os.environ.get("LLMBIM_API_KEY", "")
store = ProjectStore()

app = FastAPI(
    title="LLM-BIM Agent API",
    description="Headless BIM operated by LLMs. No human drafting UI.",
    version=sdk_version,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("LLMBIM_CORS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def _ok(result: Any = None) -> dict[str, Any]:
    return {"ok": True, "result": result, "error": None}


def _err(exc: Exception) -> JSONResponse:
    if isinstance(exc, BimError):
        return JSONResponse(
            status_code=400,
            content={"ok": False, "result": None, "error": exc.to_dict()},
        )
    if isinstance(exc, KeyError):
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "result": None,
                "error": {"code": "NOT_FOUND", "message": str(exc), "details": {}},
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "result": None,
            "error": {
                "code": "INTERNAL",
                "message": str(exc),
                "details": {"trace": traceback.format_exc()[-2000:]},
            },
        },
    )


# --- schemas ------------------------------------------------------------------


class CreateProjectBody(BaseModel):
    name: str = "Untitled"


class LevelBody(BaseModel):
    name: str
    elevation_mm: float


class GridBody(BaseModel):
    axis: str
    positions_mm: list[float]
    name: str | None = None


class WallBody(BaseModel):
    level: str
    start: tuple[float, float]
    end: tuple[float, float]
    thickness_mm: float = 200
    height_mm: float = 3000
    name: str | None = None


class SlabBody(BaseModel):
    level: str
    polygon: list[tuple[float, float]]
    thickness_mm: float = 200
    name: str | None = None


class DoorBody(BaseModel):
    host: str
    offset_mm: float
    width_mm: float = 900
    height_mm: float = 2100
    name: str | None = None


class WindowBody(BaseModel):
    host: str
    offset_mm: float
    width_mm: float = 1200
    height_mm: float = 1200
    sill_mm: float = 900
    name: str | None = None


class RoomBody(BaseModel):
    level: str
    name: str
    boundary: list[tuple[float, float]]


class SectionBody(BaseModel):
    p0: tuple[float, float]
    p1: tuple[float, float]
    depth_mm: float = 500
    scale: float = 0.05


class ElevationBody(BaseModel):
    direction: str = Field(description="N|S|E|W")
    scale: float = 0.05


# --- health + review UI -------------------------------------------------------


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": sdk_version,
        "service": "llm-bim",
        "projects": len(store.list_projects()),
        "data_dir": str(store.root),
    }


@app.get("/", response_class=HTMLResponse)
def review_home() -> str:
    """Read-only review landing (not a drafting UI)."""
    projects = store.list_projects()
    rows = "".join(
        f'<li><a href="/review/{p["id"]}">{p.get("name", p["id"])}</a> '
        f'<code>{p["id"]}</code> — {p.get("stats", {})}</li>'
        for p in projects
    ) or "<li><em>No projects yet. Agents create them via POST /v1/projects</em></li>"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LLM-BIM Review</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;background:#0b0f14;color:#e6edf3}}
a{{color:#58a6ff}} code{{background:#21262d;padding:2px 6px;border-radius:4px}}
.badge{{display:inline-block;background:#238636;color:#fff;padding:2px 8px;border-radius:12px;font-size:12px}}
</style></head><body>
<h1>LLM-BIM <span class="badge">review only</span></h1>
<p>Headless BIM for agents. No drafting UI. Version <code>{sdk_version}</code>.</p>
<p>API docs: <a href="/docs">/docs</a> · Health: <a href="/health">/health</a></p>
<h2>Projects</h2>
<ul>{rows}</ul>
</body></html>"""


@app.get("/review/{project_id}", response_class=HTMLResponse)
def review_project(project_id: str) -> str:
    try:
        p = store.get(project_id)
    except KeyError as e:
        raise HTTPException(404, "project not found") from e
    stats = p.stats()
    levels = "".join(f"<li>{lv.name} @ {lv.elevation_mm} mm</li>" for lv in p.levels())
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{p.name}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;background:#0b0f14;color:#e6edf3}}
a{{color:#58a6ff}} code{{background:#21262d;padding:2px 6px;border-radius:4px}}
img,object{{background:#fff;max-width:100%;border:1px solid #30363d;border-radius:8px}}
</style></head><body>
<p><a href="/">← projects</a></p>
<h1>{p.name}</h1>
<p><code>{project_id}</code> · stats: {stats}</p>
<h2>Levels</h2><ul>{levels}</ul>
<h2>Plan L1 (if present)</h2>
<p><a href="/v1/projects/{project_id}/exports/plan/L1.svg">Download plan SVG</a></p>
<object data="/v1/projects/{project_id}/exports/plan/L1.svg" type="image/svg+xml" width="100%" height="480"></object>
</body></html>"""


# --- projects -----------------------------------------------------------------


@app.get("/v1/projects", dependencies=[Depends(require_api_key)])
def list_projects() -> dict[str, Any]:
    return _ok(store.list_projects())


@app.post("/v1/projects", dependencies=[Depends(require_api_key)])
def create_project(body: CreateProjectBody) -> dict[str, Any]:
    pid, p = store.create(body.name)
    return _ok({"project_id": pid, "name": p.name, "stats": p.stats()})


@app.get("/v1/projects/{project_id}", dependencies=[Depends(require_api_key)])
def get_project(project_id: str) -> Any:
    try:
        p = store.get(project_id)
        return _ok(
            {
                "project_id": project_id,
                "name": p.name,
                "stats": p.stats(),
                "levels": [lv.model_dump() for lv in p.levels()],
                "model": p.model.to_dict(),
            }
        )
    except Exception as e:
        return _err(e)


@app.delete("/v1/projects/{project_id}", dependencies=[Depends(require_api_key)])
def delete_project(project_id: str) -> Any:
    try:
        store.delete(project_id)
        return _ok({"deleted": project_id})
    except Exception as e:
        return _err(e)


def _mutate(project_id: str, fn: Any) -> Any:
    try:
        p = store.get(project_id)
        result = fn(p)
        store.save(project_id)
        return _ok(result)
    except Exception as e:
        return _err(e)


@app.post("/v1/projects/{project_id}/levels", dependencies=[Depends(require_api_key)])
def add_level(project_id: str, body: LevelBody) -> Any:
    return _mutate(project_id, lambda p: {"level_id": p.add_level(body.name, body.elevation_mm)})


@app.post("/v1/projects/{project_id}/grids", dependencies=[Depends(require_api_key)])
def add_grid(project_id: str, body: GridBody) -> Any:
    return _mutate(
        project_id,
        lambda p: {"grid_id": p.add_grid(body.axis, body.positions_mm, body.name)},
    )


@app.post("/v1/projects/{project_id}/walls", dependencies=[Depends(require_api_key)])
def create_wall(project_id: str, body: WallBody) -> Any:
    return _mutate(
        project_id,
        lambda p: {
            "element_id": p.create_wall(
                level=body.level,
                start=body.start,
                end=body.end,
                thickness_mm=body.thickness_mm,
                height_mm=body.height_mm,
                name=body.name,
            )
        },
    )


@app.post("/v1/projects/{project_id}/slabs", dependencies=[Depends(require_api_key)])
def create_slab(project_id: str, body: SlabBody) -> Any:
    return _mutate(
        project_id,
        lambda p: {
            "element_id": p.create_slab(
                level=body.level,
                polygon=body.polygon,
                thickness_mm=body.thickness_mm,
                name=body.name,
            )
        },
    )


@app.post("/v1/projects/{project_id}/doors", dependencies=[Depends(require_api_key)])
def place_door(project_id: str, body: DoorBody) -> Any:
    return _mutate(
        project_id,
        lambda p: {
            "element_id": p.place_door(
                host=body.host,
                offset_mm=body.offset_mm,
                width_mm=body.width_mm,
                height_mm=body.height_mm,
                name=body.name,
            )
        },
    )


@app.post("/v1/projects/{project_id}/windows", dependencies=[Depends(require_api_key)])
def place_window(project_id: str, body: WindowBody) -> Any:
    return _mutate(
        project_id,
        lambda p: {
            "element_id": p.place_window(
                host=body.host,
                offset_mm=body.offset_mm,
                width_mm=body.width_mm,
                height_mm=body.height_mm,
                sill_mm=body.sill_mm,
                name=body.name,
            )
        },
    )


@app.post("/v1/projects/{project_id}/rooms", dependencies=[Depends(require_api_key)])
def create_room(project_id: str, body: RoomBody) -> Any:
    return _mutate(
        project_id,
        lambda p: {
            "element_id": p.create_room(
                level=body.level, name=body.name, boundary=body.boundary
            )
        },
    )


@app.post("/v1/projects/{project_id}/undo", dependencies=[Depends(require_api_key)])
def undo(project_id: str) -> Any:
    return _mutate(project_id, lambda p: p.undo())


@app.post("/v1/projects/{project_id}/redo", dependencies=[Depends(require_api_key)])
def redo(project_id: str) -> Any:
    return _mutate(project_id, lambda p: p.redo())


@app.get("/v1/projects/{project_id}/query", dependencies=[Depends(require_api_key)])
def query_elements(
    project_id: str,
    category: str | None = None,
    level: str | None = None,
) -> Any:
    try:
        p = store.get(project_id)
        filters: dict[str, str] = {}
        if category:
            filters["category"] = category
        if level:
            filters["level"] = level
        els = p.query(**filters)
        return _ok([el.model_dump() for el in els])
    except Exception as e:
        return _err(e)


@app.get("/v1/projects/{project_id}/schedules/{kind}", dependencies=[Depends(require_api_key)])
def get_schedule(project_id: str, kind: str) -> Any:
    try:
        p = store.get(project_id)
        return _ok(schedule_rows(p.model, kind))
    except Exception as e:
        return _err(e)


@app.get("/v1/projects/{project_id}/exports/plan/{level}.svg")
def export_plan(project_id: str, level: str) -> Response:
    """Public review export (SVG). Mutations still require API key."""
    try:
        p = store.get(project_id)
        out = store.artifacts_dir(project_id) / f"plan_{level}.svg"
        export_plan_svg(p.model, level, out)
        return FileResponse(out, media_type="image/svg+xml", filename=out.name)
    except BimError as e:
        raise HTTPException(400, e.to_dict()) from e
    except KeyError as e:
        raise HTTPException(404, "project not found") from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.post("/v1/projects/{project_id}/exports/section", dependencies=[Depends(require_api_key)])
def export_section(project_id: str, body: SectionBody) -> Any:
    try:
        p = store.get(project_id)
        out = store.artifacts_dir(project_id) / "section.svg"
        export_section_svg(p.model, body.p0, body.p1, out, depth_mm=body.depth_mm, scale=body.scale)
        return FileResponse(out, media_type="image/svg+xml", filename=out.name)
    except Exception as e:
        return _err(e)


@app.post("/v1/projects/{project_id}/exports/elevation", dependencies=[Depends(require_api_key)])
def export_elevation(project_id: str, body: ElevationBody) -> Any:
    try:
        p = store.get(project_id)
        out = store.artifacts_dir(project_id) / f"elev_{body.direction}.svg"
        export_elevation_svg(p.model, body.direction, out, scale=body.scale)
        return FileResponse(out, media_type="image/svg+xml", filename=out.name)
    except Exception as e:
        return _err(e)


@app.post("/v1/projects/{project_id}/validate", dependencies=[Depends(require_api_key)])
def validate_project(project_id: str) -> Any:
    try:
        p = store.get(project_id)
        issues = validate_model(p.model)
        errors = sum(1 for i in issues if i.severity == "error")
        return _ok(
            {
                "ok": errors == 0,
                "error_count": errors,
                "issue_count": len(issues),
                "issues": [i.to_dict() for i in issues],
            }
        )
    except Exception as e:
        return _err(e)


@app.post("/v1/projects/import", dependencies=[Depends(require_api_key)])
def import_project(body: dict[str, Any]) -> Any:
    """Import full model JSON (same shape as project save file).

    Accepts either the raw ``ProjectModel`` dict, or
    ``{"name": "...", "model": { ... project fields ... }}``.
    """
    try:
        name: str | None = None
        if isinstance(body.get("model"), dict) and "schema_version" not in body:
            data = body["model"]
            name = body.get("name")
        else:
            data = body
            name = body.get("name") if "schema_version" not in body else None
            if name and "schema_version" in body:
                name = None  # name is a model field; don't treat specially
        # Prefer explicit override only via top-level when wrapping
        if isinstance(body.get("model"), dict):
            name = body.get("name")
        pid, p = store.import_model(data, name=name if isinstance(body.get("model"), dict) else None)
        return _ok({"project_id": pid, "name": p.name, "stats": p.stats()})
    except Exception as e:
        return _err(e)


@app.get("/v1/projects/{project_id}/exports/schedule/{kind}.csv")
def export_schedule_file(project_id: str, kind: str) -> Response:
    try:
        p = store.get(project_id)
        out = store.artifacts_dir(project_id) / f"{kind}.csv"
        export_schedule_csv(p.model, kind, out)
        return FileResponse(out, media_type="text/csv", filename=out.name)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.get("/v1/projects/{project_id}/exports/elevation/{direction}.svg")
def export_elevation_get(project_id: str, direction: str) -> Response:
    try:
        p = store.get(project_id)
        out = store.artifacts_dir(project_id) / f"elev_{direction}.svg"
        export_elevation_svg(p.model, direction, out)
        return FileResponse(out, media_type="image/svg+xml", filename=out.name)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.get("/v1/projects/{project_id}/exports/model.gltf")
def export_gltf(project_id: str) -> Response:
    """Simple wall-box glTF for review (not construction LOD)."""
    try:
        p = store.get(project_id)
        out = store.artifacts_dir(project_id) / "model.gltf"
        export_gltf_walls(p.model, out)
        return FileResponse(out, media_type="model/gltf+json", filename=out.name)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.get("/v1/projects/{project_id}/download.json")
def download_project_json(project_id: str) -> Response:
    try:
        p = store.get(project_id)
        out = store.artifacts_dir(project_id) / "project.llmbim.json"
        p.save(out)
        return FileResponse(out, media_type="application/json", filename=out.name)
    except KeyError as e:
        raise HTTPException(404, "project not found") from e


@app.post("/v1/demo/simple-house", dependencies=[Depends(require_api_key)])
def demo_simple_house() -> Any:
    """Seed a complete demo project for launch smoke tests."""
    try:
        pid, p = store.create("Simple House (demo)")
        p.add_level("L1", 0)
        p.add_level("L2", 3000)
        p.add_grid("U", [0, 5000, 10000])
        p.add_grid("V", [0, 4000, 8000])
        footprint = [(0, 0), (10000, 0), (10000, 8000), (0, 8000)]
        p.create_slab(level="L1", polygon=footprint, thickness_mm=200, name="Slab-L1")
        walls = [
            ((0, 0), (10000, 0), "W-S"),
            ((10000, 0), (10000, 8000), "W-E"),
            ((10000, 8000), (0, 8000), "W-N"),
            ((0, 8000), (0, 0), "W-W"),
        ]
        ids: dict[str, str] = {}
        for start, end, name in walls:
            ids[name] = p.create_wall(
                level="L1",
                start=start,
                end=end,
                thickness_mm=200,
                height_mm=3000,
                name=name,
            )
        p.place_door(host=ids["W-S"], offset_mm=2000, width_mm=900, height_mm=2100, name="Entry")
        p.place_window(
            host=ids["W-N"],
            offset_mm=3000,
            width_mm=1500,
            height_mm=1200,
            sill_mm=900,
            name="NorthWin",
        )
        p.create_room(level="L1", name="Living", boundary=footprint)
        store.save(pid)
        # Pre-render plan
        out = store.artifacts_dir(pid) / "plan_L1.svg"
        export_plan_svg(p.model, "L1", out)
        issues = validate_model(p.model)
        return _ok(
            {
                "project_id": pid,
                "stats": p.stats(),
                "validation": {
                    "ok": not any(i.severity == "error" for i in issues),
                    "issues": [i.to_dict() for i in issues],
                },
                "review_url": f"/review/{pid}",
                "plan_url": f"/v1/projects/{pid}/exports/plan/L1.svg",
                "gltf_url": f"/v1/projects/{pid}/exports/model.gltf",
                "json_url": f"/v1/projects/{pid}/download.json",
            }
        )
    except Exception as e:
        return _err(e)


def create_app() -> FastAPI:
    return app
