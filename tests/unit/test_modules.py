"""Module / block / machine import and connections."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.modules import expand_block_for_export


def _small_machine(tmp: Path) -> Path:
    p = Project.create("Skid-A", vcs=False)
    p.add_level("Skid", 0)
    shell = p.create_equipment_box(
        level="Skid",
        origin=(0, 0),
        size=(800, 600, 500),
        name="Pump skid",
        kind="skid",
        centered=True,
    )
    p.define_port(shell, "PROC_IN", role="process", medium="slurry", position=(-400, 0))
    p.define_port(shell, "PROC_OUT", role="process", medium="slurry", position=(400, 0))
    p.define_port(shell, "PWR", role="power", medium="480V", position=(0, 300))
    path = tmp / "skid_a.llmbim.json"
    p.save(path)
    return path


def test_import_native_and_block(tmp_path: Path):
    src = _small_machine(tmp_path)
    host = Project.create("Facility", vcs=False)
    host.add_level("L0", 0)
    host.create_rect_shell(
        level="L0", x=0, y=0, w=20000, d=15000, height_mm=6000, thickness_mm=300, name_prefix="B"
    )

    native = host.import_module(
        src, level="L0", origin=(5000, 4000), mode="native", kind="machine", name="Skid native"
    )
    assert native["mode"] == "native"
    assert native["count"] >= 1
    assert host.stats().get("equipment", 0) >= 1

    block = host.import_module(
        src, level="L0", origin=(12000, 4000), mode="block", kind="machine", name="Skid block"
    )
    assert block["mode"] == "block"
    assert host.stats().get("module_instance", 0) >= 1
    mods = host.modules()
    assert len(mods["definitions"]) >= 1
    assert len(mods["instances"]) >= 2


def test_explode_block(tmp_path: Path):
    src = _small_machine(tmp_path)
    host = Project.create("H", vcs=False)
    host.add_level("L1", 0)
    r = host.import_module(src, level="L1", origin=(1000, 1000), mode="block")
    before = host.stats().get("equipment", 0)
    exp = host.explode_block(r["instance_id"])
    assert exp["mode"] == "native"
    assert host.stats().get("equipment", 0) > before
    # block instance gone
    cats = [e.category for e in host.model.elements]
    assert "module_instance" not in cats or all(
        e.id != r["instance_id"] for e in host.model.elements
    )


def test_connect_machine_to_host(tmp_path: Path):
    src = _small_machine(tmp_path)
    host = Project.create("Plant", vcs=False)
    host.add_level("L0", 0)
    header = host.create_equipment_box(
        level="L0",
        origin=(0, 0),
        size=(2000, 400, 400),
        name="Process header",
        kind="header",
    )
    host.define_port(header, "BRANCH_1", role="process", medium="slurry", position=(1000, 0))
    imp = host.import_module(src, level="L0", origin=(5000, 0), mode="native", kind="machine")
    # find skid element with ports
    skid = next(
        e
        for e in host.model.elements
        if e.params.get("ports") and e.category == "equipment"
    )
    conn = host.connect(skid.id, "PROC_IN", header, "BRANCH_1", medium="slurry", name="feed")
    assert conn["from_port"] == "PROC_IN"
    assert len(host.modules()["connections"]) == 1


def test_export_module_package(tmp_path: Path):
    p = Project.create("Proto", vcs=False)
    p.add_level("B", 0)
    p.create_equipment_box(level="B", origin=(0, 0), size=(500, 320, 320), shape="cylinder", centered=True)
    out = tmp_path / "mod_pkg"
    r = p.export_module(out, kind="machine")
    assert Path(r["path"]).is_file()
    assert (out / "MODULE.json").is_file()


def test_expand_blocks_for_export(tmp_path: Path):
    src = _small_machine(tmp_path)
    host = Project.create("X", vcs=False)
    host.add_level("L1", 0)
    host.import_module(src, level="L1", origin=(0, 0), mode="block")
    expanded = expand_block_for_export(host.model)
    assert any(e.category == "equipment" for e in expanded.elements)
