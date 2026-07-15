"""Schema migrations for .llmbim.json project files."""

from __future__ import annotations

from typing import Any

from llmbim_core.errors import ValidationError

# Current schema version
CURRENT = 2


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade document in place to CURRENT schema version."""
    version = int(data.get("schema_version", 1))
    if version > CURRENT:
        raise ValidationError(
            "Project schema newer than this software",
            got=version,
            supported=CURRENT,
        )
    while version < CURRENT:
        if version == 1:
            data = _v1_to_v2(data)
            version = 2
        else:
            raise ValidationError("No migration path", from_version=version)
    data["schema_version"] = CURRENT
    return data


def _v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """v2: assemblies list, meta dict, default phase on elements."""
    data.setdefault("assemblies", [])
    data.setdefault("meta", {})
    for el in data.get("elements", []):
        params = el.setdefault("params", {})
        params.setdefault("phase", "new")
    for g in data.get("grids", []):
        g.setdefault("params", {})
    return data
