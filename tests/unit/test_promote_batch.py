"""여러 단어 청크 승격을 한 번에: 백그라운드 작업, 단어별 결과, 단어 사이 취소."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.schemas.corpus import PromoteChunkResponse
from backend.services.corpus_service import CorpusService
from backend.services.jobs import jobs


def _req(nid, chunk):
    return {"note_id": nid, "new_chunk": chunk, "meaning": "m", "pos": "v", "example_1": "a", "trans_1": "b",
            "example_2": "c", "trans_2": "d", "explanation": "", "add_sentences_to_deck": True, "reset_to_new": True}


@pytest.fixture
def client():
    import server
    jobs.reset()
    return TestClient(server.app)


def _wait():
    deadline = time.time() + 5
    while jobs.is_running and time.time() < deadline:
        time.sleep(0.01)


def test_promote_batch_runs_each_and_reports(client, monkeypatch):
    done = []

    def fake(req):
        done.append(req.note_id)
        ok = req.note_id != 2
        return PromoteChunkResponse(success=ok, note_id=req.note_id, new_chunk=req.new_chunk,
                                    sentences_added_count=2 if ok else 0, error=None if ok else "Note 2 not found")

    monkeypatch.setattr(CorpusService, "promote_chunk", staticmethod(fake))
    r = client.post("/api/corpus/promote-batch", json={"items": [_req(1, "lurk behind A"), _req(2, "x"), _req(3, "appraise A critically")]})
    assert r.status_code == 200 and r.json()["status"] == "success", r.text
    _wait()
    s = jobs.snapshot()
    assert done == [1, 2, 3]
    assert s.status == "success"
    msgs = " ".join(l.message for l in s.logs)
    assert "성공 2" in msgs and "실패 1" in msgs and "Note 2 not found" in msgs


def test_promote_batch_cancel_stops_between_words(client, monkeypatch):
    gate = threading.Event()
    done = []

    def fake(req):
        done.append(req.note_id)
        gate.wait(2)
        return PromoteChunkResponse(success=True, note_id=req.note_id, new_chunk=req.new_chunk)

    monkeypatch.setattr(CorpusService, "promote_chunk", staticmethod(fake))
    client.post("/api/corpus/promote-batch", json={"items": [_req(1, "a"), _req(2, "b"), _req(3, "c")]})
    deadline = time.time() + 2
    while not done and time.time() < deadline:
        time.sleep(0.01)
    client.post("/api/workflow/cancel")
    gate.set()
    _wait()
    assert done == [1]
    assert jobs.snapshot().status == "cancelled"


def test_promote_batch_requires_items(client):
    assert client.post("/api/corpus/promote-batch", json={"items": []}).status_code == 422
