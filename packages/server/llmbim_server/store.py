"""Project persistence for the agent API."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from llmbim import Project
from llmbim_core.ids import new_id


class ProjectStore:
    """Filesystem-backed multi-project store (Railway volume friendly)."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or os.environ.get("LLMBIM_DATA_DIR", "./data"))
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._sessions: dict[str, Project] = {}

    def _path(self, project_id: str) -> Path:
        return self.root / f"{project_id}.llmbim.json"

    def _meta_path(self) -> Path:
        return self.root / "index.json"

    def _load_index(self) -> dict[str, Any]:
        mp = self._meta_path()
        if not mp.exists():
            return {"projects": {}}
        return json.loads(mp.read_text(encoding="utf-8"))

    def _save_index(self, index: dict[str, Any]) -> None:
        self._meta_path().write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            idx = self._load_index()
            return [
                {"id": pid, **meta}
                for pid, meta in idx.get("projects", {}).items()
            ]

    def create(self, name: str = "Untitled") -> tuple[str, Project]:
        with self._lock:
            pid = new_id("prj")
            project = Project.create(name=name)
            # Align stored id with store key
            project.model.id = pid
            project.save(self._path(pid))
            idx = self._load_index()
            idx.setdefault("projects", {})[pid] = {
                "name": name,
                "stats": project.stats(),
            }
            self._save_index(idx)
            self._sessions[pid] = project
            return pid, project

    def get(self, project_id: str) -> Project:
        with self._lock:
            if project_id in self._sessions:
                return self._sessions[project_id]
            path = self._path(project_id)
            if not path.exists():
                raise KeyError(project_id)
            project = Project.open(path)
            self._sessions[project_id] = project
            return project

    def save(self, project_id: str) -> None:
        with self._lock:
            project = self.get(project_id)
            project.save(self._path(project_id))
            idx = self._load_index()
            if project_id in idx.get("projects", {}):
                idx["projects"][project_id]["name"] = project.name
                idx["projects"][project_id]["stats"] = project.stats()
                self._save_index(idx)

    def delete(self, project_id: str) -> None:
        with self._lock:
            self._sessions.pop(project_id, None)
            path = self._path(project_id)
            if path.exists():
                path.unlink()
            idx = self._load_index()
            idx.get("projects", {}).pop(project_id, None)
            self._save_index(idx)

    def import_model(self, data: dict[str, Any], *, name: str | None = None) -> tuple[str, Project]:
        """Import a project document (llmbim JSON body). Assigns a new store id."""
        from llmbim_core.model import ProjectModel

        with self._lock:
            pid = new_id("prj")
            model = ProjectModel.from_dict(data)
            model.id = pid
            if name:
                model.name = name
            project = Project(model)
            project.save(self._path(pid))
            idx = self._load_index()
            idx.setdefault("projects", {})[pid] = {
                "name": project.name,
                "stats": project.stats(),
            }
            self._save_index(idx)
            self._sessions[pid] = project
            return pid, project

    def artifacts_dir(self, project_id: str) -> Path:
        d = self.root / "artifacts" / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d
