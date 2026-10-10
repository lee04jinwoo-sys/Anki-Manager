"""노트 정리 실행 / 작업 취소 API."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.services import maintenance_service
from backend.services.jobs import jobs


@pytest.fixture
def client():
    import server
    return TestClient(server.app)


@pytest.fixture
def fake_steps(monkeypatch):
    ran = []
    gate = threading.Event()

    def make(step):
        def run():
            ran.append(step)
            gate.wait(2)
        return run

    monkeypatch.setattr(
        maintenance_service, "_STEP_FUNCS", {s: make(s) for s in maintenance_service._STEP_FUNCS}
    )
    yield ran, gate
    gate.set()
    _wait_idle()
    jobs.reset()


def _wait_idle(timeout=5):
    deadline = time.time() + timeout
    while jobs.is_running and time.time() < deadline:
        time.sleep(0.01)


@pytest.mark.parametrize(
    "path, body, expected",
    [
        ("/api/organize/run", {"steps": ["audio"]}, ["audio"]),
        ("/api/organize/run", None, ["fields", "audio", "deck_move"]),
        ("/api/organize/audio", None, ["audio"]),
        ("/api/organize/completion", None, ["fields"]),
        ("/api/organize/pos", None, ["pos"]),
        ("/api/organize/organizer", None, ["deck_move"]),
        ("/api/organize/duplicates", None, ["duplicates"]),
    ],
)
def test_organize_routes_start_job(client, fake_steps, path, body, expected):
    ran, gate = fake_steps
    jobs.reset()
    r = client.post(path, json=body) if body is not None else client.post(path)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "success"
    gate.set()
    _wait_idle()
    assert ran == expected


def test_cancel_stops_before_next_step(client, fake_steps):
    ran, gate = fake_steps
    jobs.reset()
    assert client.post("/api/organize/run", json={"steps": ["fields", "audio"]}).json()["status"] == "success"
    deadline = time.time() + 2
    while not ran and time.time() < deadline:
        time.sleep(0.01)

    r = client.post("/api/workflow/cancel")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "success"

    gate.set()
    _wait_idle()
    assert ran == ["fields"]  # audio 단계는 실행되지 않음
    state = jobs.snapshot()
    assert state.status == "cancelled"
    assert not state.is_running


def test_cancel_when_idle_is_harmless(client):
    jobs.reset()
    r = client.post("/api/workflow/cancel")
    assert r.status_code == 200
    assert jobs.snapshot().status == "idle"


def test_cancel_clears_waiting_selection(client):
    jobs.reset()
    jobs.start("pick", lambda: "waiting_selection")
    _wait_idle()
    assert jobs.snapshot().status == "waiting_selection"
    client.post("/api/workflow/cancel")
    s = jobs.snapshot()
    assert s.status == "idle" and s.candidates.sentences == []
