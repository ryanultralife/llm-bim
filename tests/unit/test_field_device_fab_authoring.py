"""Platform contract: field_device_fab checklist + validate_intent bar."""

from __future__ import annotations

from llmbim import Project
from llmbim_core.authoring import PRODUCT_REQUIREMENTS, authoring_checklist, validate_intent


def test_field_device_fab_in_product_requirements() -> None:
    assert "field_device_fab" in PRODUCT_REQUIREMENTS
    assert "machine_fab_pack" in PRODUCT_REQUIREMENTS
    cl = authoring_checklist("field_device_fab")
    assert cl["ok"] is True
    req = " ".join(cl["required"]).lower()
    extra = str(cl.get("extra") or "").lower()
    assert "pn" in req or "parts" in req
    assert "kind" in req
    assert "mode" in req or "part" in req
    assert "connected" in req
    assert "fitting" in req
    assert "hardware" in req
    assert "product name" in req
    assert "machine_engineering_bar" in extra


def test_validate_intent_rejects_single_box() -> None:
    p = Project.create("Thin", vcs=False)
    p.add_level("Deck", 0)
    p.create_equipment_box(
        level="Deck",
        origin=(0, 0),
        size=(500, 200, 200),
        name="blob",
        kind="equipment",
        centered=True,
    )
    v = validate_intent(p.model, "field_device_fab")
    assert v["ok"] is False
    assert v["stats"]["equipment"] < 20
    assert any("20" in m or "equipment" in m for m in v["missing"])


def test_validate_intent_passes_multi_pn_pack() -> None:
    p = Project.create("Dense", vcs=False)
    p.add_level("Deck", 0)
    kinds = [
        "rail",
        "coil",
        "magnet",
        "flange",
        "shell",
        "electrical",
        "probe",
        "chamber",
        "clamp",
        "header",
        "mount",
        "base",
    ]
    for i in range(24):
        kind = kinds[i % len(kinds)]
        eid = p.create_equipment_box(
            level="Deck",
            origin=(i * 50.0, 0.0),
            size=(40.0, 30.0, 20.0),
            name=f"MB-X-{i:03d} part {kind}",
            kind=kind,
            part=f"MB-X-{i:03d}",
            mark=f"M{i:03d}",
            centered=True,
        )
        p.op("set_param", id=eid, key="pn", value=f"MB-X-{i:03d}")
        p.op("set_param", id=eid, key="system", value="STRUCT" if i % 2 == 0 else "PWR")
        p.op("set_param", id=eid, key="product_class", value="field_deployable_vehicle_array")
        p.op("set_param", id=eid, key="twin_fidelity", value="F1")
    # minimal fab_part so warnings stay soft
    fid = p.create_fab_part(name="MB-X-000 plate", material="steel_A36", level="Deck")
    p.fab_box(fid, size_mm=(40.0, 30.0, 5.0))
    p.gdt_datum(fid, label="A", face="bottom")

    v = validate_intent(p.model, "field_device_fab")
    assert v["stats"]["equipment"] >= 20
    assert v["stats"]["unique_pns"] >= 15
    assert v["stats"]["equipment_kinds"] >= 8
    assert v["ok"] is True, v


def _dense_machine(name: str = "Dense") :
    p = Project.create(name, vcs=False)
    p.add_level("Deck", 0)
    kinds = [
        "rail",
        "coil",
        "magnet",
        "flange",
        "shell",
        "electrical",
        "probe",
        "chamber",
        "clamp",
        "header",
        "mount",
        "base",
    ]
    for i in range(24):
        kind = kinds[i % len(kinds)]
        eid = p.create_equipment_box(
            level="Deck",
            origin=(i * 50.0, 0.0),
            size=(40.0, 30.0, 20.0),
            name=f"MB-X-{i:03d} part {kind}",
            kind=kind,
            part=f"MB-X-{i:03d}",
            mark=f"M{i:03d}",
            centered=True,
        )
        p.op("set_param", id=eid, key="pn", value=f"MB-X-{i:03d}")
        p.op("set_param", id=eid, key="system", value="STRUCT" if i % 2 == 0 else "PWR")
        p.op("set_param", id=eid, key="product_class", value="industrial_skid")
        p.op("set_param", id=eid, key="twin_fidelity", value="F1")
    fid = p.create_fab_part(name="MB-X-000 plate", material="steel_A36", level="Deck")
    p.fab_box(fid, size_mm=(40.0, 30.0, 5.0))
    p.gdt_datum(fid, label="A", face="bottom")
    return p


def test_validate_intent_rejects_diagonal_unfitted_services() -> None:
    p = _dense_machine()
    p.place_pipe(level="Deck", nps="1", start=(0, 0), end=(2000, 800), material="process")
    p.place_pipe(level="Deck", nps="1", start=(2000, 800), end=(4000, 1600), material="process")
    v = validate_intent(p.model, "field_device_fab")
    assert v["ok"] is False, v
    blob = " ".join(v["missing"]).lower()
    assert "diagonal" in blob
    assert "fitting" in blob or "connect" in blob


def test_validate_intent_accepts_orthogonal_connected_services() -> None:
    p = _dense_machine("MineClean")
    p.model.meta["product"] = "MineClean"
    p.model.meta["process_notes"] = ["Process: test loop [EE]."]
    a = p.place_fitting(
        level="Deck", fitting_type="elbow_90", nps="1", origin=(0, 0), material="process"
    )
    b = p.place_fitting(
        level="Deck", fitting_type="elbow_90", nps="1", origin=(2000, 1500), material="process"
    )
    p.mep_route(a, b, kind="pipe", nps="1", material="process", orthogonal=True)
    p.create_equipment_box(
        level="Deck",
        origin=(100, 100),
        size=(20, 20, 10),
        name="M16 cap",
        kind="bolt",
        part="MB-X-BOLT",
        centered=True,
    )
    v = validate_intent(p.model, "field_device_fab")
    assert v["stats"]["diagonal_runs"] == 0
    assert v["stats"]["fittings"] >= 2
    assert v["stats"]["connections"] >= 1
    assert v["ok"] is True, v


def test_validate_intent_warns_pn_as_product_name() -> None:
    p = _dense_machine("MB-MCLEAN")
    v = validate_intent(p.model, "field_device_fab")
    assert v["ok"] is True, v
    assert any("P/N prefix" in w or "product" in w.lower() for w in v["warnings"])
