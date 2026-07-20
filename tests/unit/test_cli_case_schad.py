"""WP-SCHAD-S8 acceptance — the Gate D golden command ``llmbim case schad``.

One command rebuilds the full Schad Phase 1 CD pack (transition review §5
Gate D): basis SSOT → model + VCS history → Gate C 21-sheet register, and
hands back exactly one entry path (``<out>/index.html``) plus the VERIFY
status, with a non-zero exit if VERIFY fails. The basis-drift invariants
themselves live in test_schad_areas / test_schad_sheets / test_schad_structure
/ test_schad_types — this suite covers only the CLI contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from llmbim_cli.main import main


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("cli_schad") / "pack"
    # capsys is function-scoped; capture stdout ourselves for module reuse
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["case", "schad", "--out", str(out)])
    return rc, out, buf.getvalue()


def test_exit_zero_with_verify_ok(run):
    rc, _out, stdout = run
    assert rc == 0
    # build_pack's own transparency lines include the VERIFY status
    assert "VERIFY_OK True" in stdout


def test_prints_single_entry_path(run):
    rc, out, stdout = run
    # the JSON summary is the last thing printed
    payload = json.loads(stdout[stdout.index('{\n  "case"') :])
    assert payload["case"] == "schad"
    assert payload["verify_ok"] is True
    assert payload["open"] == str(out / "index.html")
    assert Path(payload["open"]).is_file()


def test_pack_has_gate_c_register_and_vcs(run):
    _rc, out, _stdout = run
    idx = json.loads(
        (out / "construction" / "SHEET_INDEX.json").read_text(encoding="utf-8")
    )
    assert idx["register"] == "custom"
    assert len(idx["sheets"]) == 21
    assert (out / "PLOT_SET.pdf").is_file()
    assert (out / "VERIFY.json").is_file()
    # true model VCS history written next to the pack (Gate D)
    assert any((out / ".llmbim" / "versions").glob("ver_*.json"))


def test_default_out_is_repo_output_schad_garage():
    # the golden command's default target — asserted without building again
    from examples.schad_build import DEFAULT_OUT, REPO_ROOT

    assert DEFAULT_OUT == REPO_ROOT / "output" / "schad_garage"
