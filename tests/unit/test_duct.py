"""HVAC rectangular duct place + CSI + plan/DXF."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_drawings.dxf_export import export_plan_dxf
from llmbim_drawings.plan import write_plan_svg


def test_place_duct_length_area_csi():
    p = Project.create("duct", vcs=False)
    p.add_level("L1", 0)
    eid = p.place_duct(
        level="L1",
        start=(0, 0),
        end=(5000, 0),
        width_mm=400,
        height_mm=250,
        system="SA",
    )
    el = p.model.get_element(eid)
    assert el.category == "duct"
    assert abs(float(el.params["length_m"]) - 5.0) < 0.01
    assert float(el.params["area_m2"]) > 0
    rows = p.csi_instances()
    duct = next(r for r in rows if r.get("element_id") == eid)
    assert duct["csi_code"] == "23 31 00"
    assert duct["csi_division"] == "23"


def test_duct_on_plan_and_dxf(tmp_path: Path):
    p = Project.create("duct-draw", vcs=False)
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p.place_duct(level="L1", start=(1000, 2000), end=(6000, 2000), width_mm=500, height_mm=300)
    plan = tmp_path / "p.svg"
    write_plan_svg(p.model, "L1", plan, scale=0.02)
    pt = plan.read_text(encoding="utf-8")
    assert 'class="ducts"' in pt
    assert "500x300" in pt
    dxf = tmp_path / "d.dxf"
    export_plan_dxf(p.model, "L1", dxf)
    text = dxf.read_text(encoding="utf-8")
    assert "DUCT" in text


def test_place_conduit_csi():
    p = Project.create("conduit", vcs=False)
    p.add_level("L1", 0)
    eid = p.place_conduit(
        level="L1",
        start=(0, 0),
        end=(10000, 0),
        trade_size="1",
        system="P",
    )
    el = p.model.get_element(eid)
    assert el.category == "conduit"
    assert abs(float(el.params["length_m"]) - 10.0) < 0.01
    row = next(r for r in p.csi_instances() if r.get("element_id") == eid)
    assert row["csi_code"] == "26 05 33"
    assert "NPS1" in str(row.get("locator", "")) or row.get("nps") == "1"


def test_duct_pipe_clash():
    from llmbim_core.clash import find_clashes

    p = Project.create("clash-mep", vcs=False)
    p.add_level("L1", 0)
    # same plan corridor, overlapping Z band
    p.place_pipe(
        level="L1",
        nps="4",
        start=(0, 1000),
        end=(5000, 1000),
        material="copper",
        z0_mm=2700,
    )
    p.place_duct(
        level="L1",
        start=(1000, 1000),
        end=(4000, 1000),
        width_mm=600,
        height_mm=400,
        z0_mm=2650,
    )
    clashes = find_clashes(p.model)
    assert any(
        {c.get("a_category"), c.get("b_category")} == {"pipe", "duct"} for c in clashes
    ), clashes[:3]


def test_boq_includes_duct_and_conduit():
    p = Project.create("boq-mep", vcs=False)
    p.add_level("L1", 0)
    p.place_duct(level="L1", start=(0, 0), end=(5000, 0), width_mm=400, height_mm=250)
    p.place_conduit(level="L1", start=(0, 500), end=(8000, 500), trade_size="3/4")
    rows = p.boq()["lines"] if isinstance(p.boq(), dict) and "lines" in p.boq() else None
    if rows is None:
        from llmbim_core.quantities import compute_boq

        rows = compute_boq(p.model)
    cats = {r["category"] for r in rows}
    assert "duct" in cats
    assert "conduit" in cats
    duct = next(r for r in rows if r["category"] == "duct")
    assert duct["unit"] in ("m2", "m")
    assert float(duct["qty"]) > 0
    cond = next(r for r in rows if r["category"] == "conduit")
    assert abs(float(cond["qty"]) - 8.0) < 0.01


def test_duct_and_conduit_takeoff():
    p = Project.create("mep-takeoff", vcs=False)
    p.add_level("L1", 0)
    p.place_duct(
        level="L1",
        start=(0, 0),
        end=(5000, 0),
        width_mm=400,
        height_mm=250,
        system="SA",
    )
    p.place_duct(
        level="L1",
        start=(0, 2000),
        end=(3000, 2000),
        width_mm=300,
        height_mm=200,
        system="RA",
    )
    p.place_conduit(level="L1", start=(0, 500), end=(10000, 500), trade_size="1")
    p.place_conduit(level="L1", start=(0, 800), end=(4000, 800), trade_size="3/4")
    p.place_part(level="L1", kind="vav", origin=(2500, 0), name="VAV-1")

    ducts = p.duct_takeoff()
    assert len(ducts) == 2
    assert all(d["csi_code"] == "23 31 00" for d in ducts)
    assert abs(sum(d["length_m"] for d in ducts) - 8.0) < 0.05
    assert all(d["area_m2"] > 0 for d in ducts)
    assert {d.get("system") for d in ducts} >= {"SA", "RA"}

    conduits = p.conduit_takeoff()
    assert len(conduits) == 2
    by_size = {c["trade_size"]: c for c in conduits}
    assert abs(by_size["1"]["length_m"] - 10.0) < 0.01
    assert abs(by_size["3/4"]["length_m"] - 4.0) < 0.01
    assert all(c["csi_code"] == "26 05 33" for c in conduits)

    trades = p.trade_schedule()
    assert "hvac" in trades and "duct" in trades["hvac"]
    assert "electrical" in trades and "conduit" in trades["electrical"]
    assert len(trades["hvac"]["duct"]) == 2
    assert len(trades["electrical"]["conduit"]) == 2


def test_cli_takeoff_duct_conduit(tmp_path: Path, capsys):
    from llmbim_cli.main import main

    p = Project.create("cli-mep", vcs=False)
    p.add_level("L1", 0)
    p.place_duct(level="L1", start=(0, 0), end=(6000, 0), width_mm=500, height_mm=300)
    p.place_conduit(level="L1", start=(0, 0), end=(12000, 0), trade_size="1")
    model = tmp_path / "model.llmbim.json"
    p.save(model)

    rc = main(["takeoff", str(model), "--kind", "duct"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "duct" in out
    assert "23 31 00" in out

    rc = main(["takeoff", str(model), "--kind", "conduit"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "conduit" in out
    assert "26 05 33" in out


def test_registry_duct_and_tray_takeoff_ops():
    p = Project.create("op-mep", vcs=False)
    p.add_level("L1", 0)
    p.place_duct(level="L1", start=(0, 0), end=(5000, 0), width_mm=400, height_mm=250)
    p.place_cable_tray(level="L1", start=(0, 500), end=(4000, 500), width_mm=300)
    d = p.op("duct_takeoff")
    assert d.get("count") == 1
    assert d["duct"][0]["csi_code"] == "23 31 00"
    t = p.op("cable_tray_takeoff")
    assert t.get("count") == 1
    assert t["cable_tray"][0]["csi_code"] == "26 05 36"
    s = p.op("system_takeoff", system="duct")
    assert "duct" in s
