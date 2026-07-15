"""Simple query language for agents.

Examples:
  category=wall
  category=door level=L1
  name~Entry
  type_id=W-SHIELD-CONC
  phase=existing
  kind=shell
  param.thickness_mm>200
"""

from __future__ import annotations

import re
from typing import Any

from llmbim_core.model import Element, ProjectModel


def parse_query(q: str) -> list[tuple[str, str, Any]]:
    """Parse space-separated filters into (field, op, value)."""
    tokens = re.findall(r'(\S+?)(=~|~=|>=|<=|!=|=|>|<|~)(\S+)', q.strip())
    if not tokens and q.strip():
        # bare category shortcut
        return [("category", "=", q.strip())]
    out = []
    for field, op, val in tokens:
        # coerce numbers
        try:
            if "." in val:
                val_c: Any = float(val)
            else:
                val_c = int(val)
        except ValueError:
            val_c = val.strip("\"'")
        out.append((field, op, val_c))
    return out


def match_element(el: Element, filters: list[tuple[str, str, Any]], model: ProjectModel) -> bool:
    for field, op, val in filters:
        if field.startswith("param."):
            key = field[6:]
            left = el.params.get(key)
        elif field == "level":
            # name or id
            if el.level_id is None:
                left = None
            else:
                try:
                    left = model.get_level(el.level_id).name
                except Exception:
                    left = el.level_id
            if left != val and el.level_id != val:
                # also try compare
                if op == "=" and str(left) != str(val) and str(el.level_id) != str(val):
                    return False
                if op == "=":
                    continue
        elif field == "kind":
            left = el.params.get("kind")
        elif field == "phase":
            left = el.params.get("phase", "new")
        elif field == "category":
            left = el.category
        elif field == "name":
            left = el.name
        elif field == "type_id":
            left = el.type_id
        elif field == "id":
            left = el.id
        elif field == "host_id":
            left = el.host_id
        else:
            left = getattr(el, field, el.params.get(field))

        if field == "level" and op == "=":
            if str(left) == str(val) or str(el.level_id) == str(val):
                continue
            return False

        if op in ("~", "=~", "~="):
            if left is None or str(val).lower() not in str(left).lower():
                return False
        elif op == "=":
            if str(left) != str(val):
                return False
        elif op == "!=":
            if str(left) == str(val):
                return False
        elif op in (">", ">=", "<", "<="):
            try:
                lv, rv = float(left), float(val)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return False
            if op == ">" and not (lv > rv):
                return False
            if op == ">=" and not (lv >= rv):
                return False
            if op == "<" and not (lv < rv):
                return False
            if op == "<=" and not (lv <= rv):
                return False
    return True


def run_query(model: ProjectModel, q: str) -> list[Element]:
    filters = parse_query(q)
    if not filters:
        return list(model.elements)
    return [el for el in model.elements if match_element(el, filters, model)]
