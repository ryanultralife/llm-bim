"""Restroom + CW loop with CSI room locators → output/restroom_pack/."""

from __future__ import annotations

from pathlib import Path

from llmbim import Project
from llmbim_core.paths import project_output_dir


def build_restroom(out: Path | None = None) -> Project:
    out = Path(out) if out else project_output_dir("restroom_pack")
    p = Project.create("Restroom Pack", vcs=True)
    p.add_level("L1", 0)
    p.create_rect_shell(
        level="L1", x=0, y=0, w=5000, d=4000, height_mm=3000, thickness_mm=200
    )
    p.create_room(
        level="L1",
        name="Restroom A",
        boundary=[(200, 200), (4800, 200), (4800, 3800), (200, 3800)],
    )
    p.place_part(level="L1", kind="toilet", origin=(1200, 1500))
    p.place_part(level="L1", kind="tp_dispenser", origin=(900, 1500))
    p.place_part(level="L1", kind="grab_bar", origin=(1500, 1200))
    p.place_pipe(
        level="L1", nps="3/4", start=(500, 1500), end=(2500, 1500), material="copper"
    )
    p.place_fitting(
        level="L1", fitting_type="elbow_90", nps="3/4", origin=(500, 1500), material="copper"
    )
    p.place_fitting(
        level="L1", fitting_type="tee", nps="3/4", origin=(1200, 1500), material="copper"
    )
    p.place_riser(
        level="L1",
        nps="2",
        origin=(2500, 1500),
        z0_mm=0,
        z1_mm=3000,
        material="copper",
    )
    p.commit("Restroom rough-in")
    man = p.export_deliverables(out)
    print(
        {
            "out": str(out.resolve()),
            "open": str(Path(man.get("output_dir", out)) / "index.html"),
            "rooms_in_csi": sum(1 for r in p.csi_instances() if r.get("room")),
            "ok": man.get("ok"),
        }
    )
    return p


if __name__ == "__main__":
    build_restroom()
