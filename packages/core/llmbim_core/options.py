"""Design options — clone subset of elements as alternate assemblies."""

from __future__ import annotations

from typing import Any

from llmbim_core.ids import new_id
from llmbim_core.model import Assembly, ProjectModel


def create_design_option(
    model: ProjectModel,
    *,
    name: str,
    element_ids: list[str] | None = None,
    clone: bool = True,
) -> dict[str, Any]:
    """Create a design option assembly.

    If clone=True, duplicate elements with new ids and link them in the assembly
    (originals remain). If clone=False, just group existing ids.
    """
    ids = list(element_ids or [])
    new_ids: list[str] = []
    if clone and ids:
        id_map: dict[str, str] = {}
        for eid in ids:
            el = model.get_element(eid)
            nid = new_id(el.category[:3] if len(el.category) >= 3 else "el")
            id_map[eid] = nid
            ne = el.model_copy(deep=True)
            ne.id = nid
            ne.name = f"{el.name} ({name})" if el.name else name
            ne.params = dict(el.params)
            ne.params["design_option"] = name
            ne.params["option_of"] = eid
            model.add_element(ne)
            new_ids.append(nid)
        # re-link hosts within clone set
        for nid in new_ids:
            el = model.get_element(nid)
            if el.host_id and el.host_id in id_map:
                el.host_id = id_map[el.host_id]
        member_ids = new_ids
    else:
        member_ids = ids

    a = Assembly(
        id=new_id("asm"),
        name=name,
        element_ids=member_ids,
        kind="option",
        params={"clone": clone},
    )
    model.assemblies.append(a)
    return {"assembly_id": a.id, "name": name, "element_ids": member_ids, "count": len(member_ids)}
