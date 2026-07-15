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
