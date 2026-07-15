"""Stable unique IDs for BIM elements."""

from __future__ import annotations

import uuid


def new_id(prefix: str = "") -> str:
    """Return a new UUID4 string, optionally prefixed (e.g. ``wal_``)."""
    uid = uuid.uuid4().hex
    if prefix:
        clean = prefix if prefix.endswith("_") else f"{prefix}_"
        return f"{clean}{uid}"
    return uid
