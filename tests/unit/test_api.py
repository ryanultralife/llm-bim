"""HTTP API smoke tests."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Isolate store
os.environ["LLMBIM_DATA_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"), "llmbim-test-data")
os.environ.pop("LLMBIM_API_KEY", None)

from llmbim_server.app import app  # noqa: E402
from llmbim_server.store import ProjectStore  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMBIM_DATA_DIR", str(tmp_path / "data"))
    # Rebuild store on app module
    import llmbim_server.app as app_mod

    app_mod.store = ProjectStore(tmp_path / "data")
    return TestClient(app_mod.app)


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_demo_and_plan(client: TestClient) -> None:
    r = client.post("/v1/demo/simple-house")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    pid = body["result"]["project_id"]
    plan = client.get(f"/v1/projects/{pid}/exports/plan/L1.svg")
    assert plan.status_code == 200
    assert b"<svg" in plan.content.lower()
    assert len(plan.content) > 200
