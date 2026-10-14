from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.api as api
from backend.api import Service
from test_core import synthetic_log


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "service", Service(tmp_path))
    return TestClient(api.app)


def test_import_and_history_keep_live_separate(client):
    response = client.post("/api/import", json={"text": synthetic_log(), "player_id": 1})
    assert response.status_code == 200
    imported = response.json()["snapshot"]
    assert imported["source"] == "import"
    assert client.get("/api/state").json()["snapshot"] is None
    assert client.get("/api/history").json()[0]["id"] == imported["id"]
    assert client.get(f"/api/history/{imported['id']}").json()["snapshot"] == imported


def test_invalid_import_returns_actionable_error(client):
    response = client.post("/api/import", json={"text": "invalid"})
    assert response.status_code == 400
    assert client.get("/api/history").json() == []


def test_settings_reject_bad_mode_path_and_identity(client):
    assert client.put("/api/settings", json={"mode": "invalid"}).status_code == 400
    assert client.put("/api/settings", json={"log_path": "Z:/not-found/Power.log"}).status_code == 400
    assert client.put("/api/settings", json={"player_id": 0}).status_code == 422
    assert client.post("/api/demo/next").status_code == 409


def test_reconnect_and_export_demo(client):
    client.put("/api/settings", json={"mode": "demo"})
    first = client.get("/api/state").json()["snapshot"]
    client.post("/api/demo/next")
    assert client.get("/api/state").json()["snapshot"]["turn"] == first["turn"] + 1
    assert client.post("/api/reconnect").status_code == 200
    assert client.get("/api/export").json()["schema_version"] == 1
    client.put("/api/settings", json={"mode": "live"})
    assert client.get("/api/state").json()["advice"] == []
