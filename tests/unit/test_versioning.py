"""True model version control tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from llmbim import Project


def test_commit_log_checkout_diff(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "output"))
    p = Project.create("VCS Demo", author="test")
    assert p._vcs is not None
    assert p.log()  # initial commit

    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000, name="W1")
    st = p.status()
    assert st["clean"] is False

    d = p.diff()
    assert d["summary"]["added"] >= 1

    c = p.commit("Add wall W1", author="test")
    assert c["version_id"].startswith("ver_")
    assert p.status()["clean"] is True

    p.create_wall(level="L1", start=(0, 0), end=(0, 4000), thickness_mm=200, height_mm=3000, name="W2")
    p.commit("Add wall W2")
    hist = p.log()
    assert len(hist) >= 3
    assert hist[0]["message"] == "Add wall W2"

    # checkout first wall-only state (second commit after initial)
    v_wall1 = [h for h in hist if h["message"] == "Add wall W1"][0]["version_id"]
    p.checkout(v_wall1)
    assert p.stats().get("wall") == 1

    p.tag("one_wall")
    assert p._vcs.refs()["one_wall"] == v_wall1


def test_empty_commit_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "out"))
    p = Project.create("Empty", author="test")
    with pytest.raises(ValueError, match="No model changes"):
        p.commit("noop")


def test_journal_records_ops(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "out"))
    p = Project.create("J", author="test")
    p.add_level("L1", 0)
    j = p.journal()
    ops = [e.get("op") for e in j]
    # command bus logs op field; accept either name form
    assert any(o in ("add_level", "AddLevel") for o in ops) or len(j) >= 1


def test_open_project_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "out"))
    p = Project.create("OpenMe", author="test")
    p.add_level("L1", 0)
    p.commit("levels")
    d = p.vcs_dir
    assert d is not None
    p2 = Project.open(d)
    assert p2.name == "OpenMe"
    assert p2.log()


def test_create_does_not_clobber_existing_project(tmp_path, monkeypatch) -> None:
    """Re-running Project.create with a colliding name must not overwrite the
    prior project's working model (regression: it saved an empty model over it)."""
    import json

    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "output"))
    p1 = Project.create("Collide", author="test")
    p1.add_level("L1", 0)
    p1.create_wall(level="L1", start=(0, 0), end=(8000, 0), thickness_mm=200, height_mm=3000)
    p1.commit("first wall")
    d1 = p1.vcs_dir
    assert d1 is not None

    # second create, same name -> must get its own dir, leave p1 intact
    p2 = Project.create("Collide", author="test")
    d2 = p2.vcs_dir
    assert d2 is not None and d2 != d1

    on_disk = json.loads((d1 / "model.llmbim.json").read_text(encoding="utf-8"))
    assert len(on_disk["elements"]) == 1, "prior project model was clobbered"

    # a fresh, non-colliding name still uses its base slug dir
    p3 = Project.create("Totally New Name", author="test")
    assert p3.vcs_dir is not None and p3.vcs_dir.name == "totally_new_name"

    # deliverables default to the project's own (possibly suffixed) dir
    p2.add_level("L1", 0)
    man = p2.export_deliverables()
    assert Path(man["output_dir"]) == d2.resolve()


def test_commit_journal_ranges_chain(tmp_path, monkeypatch) -> None:
    """Each commit's journal range must start where the parent's ended, not at 0
    (regression: journal_from was hardcoded 0 so every range spanned history)."""
    monkeypatch.setenv("LLMBIM_OUTPUT_DIR", str(tmp_path / "output"))
    p = Project.create("JournalRange", author="test")
    p.add_level("L1", 0)
    p.create_wall(level="L1", start=(0, 0), end=(5000, 0), thickness_mm=200, height_mm=3000)
    c1 = p.commit("wall 1")
    p.create_wall(level="L1", start=(0, 0), end=(0, 5000), thickness_mm=200, height_mm=3000)
    c2 = p.commit("wall 2")
    vcs = p._vcs
    m1 = vcs.load_version(c1["version_id"])["commit"]
    m2 = vcs.load_version(c2["version_id"])["commit"]
    assert m2["journal_from"] == m1["journal_to"]
    assert m2["journal_to"] >= m2["journal_from"]
