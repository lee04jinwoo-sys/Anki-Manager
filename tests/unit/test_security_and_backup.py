"""외부 사이트 요청 차단, 청크 승격 전 원본 백업, 대시보드 오디오 필드."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.services import corpus_service, maintenance_service
from backend.services.jobs import jobs
from backend.schemas.corpus import PromoteChunkRequest
from integrations.anki_connect import AnkiConnector


@pytest.fixture
def client(monkeypatch):
    import server
    monkeypatch.setattr(maintenance_service, "_STEP_FUNCS", {s: (lambda: None) for s in maintenance_service._STEP_FUNCS})
    jobs.reset()
    return TestClient(server.app)


# ---- ⑥ cross-site requests ------------------------------------------------
@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost.evil.example", "null"])
def test_foreign_origin_post_is_rejected(client, origin):
    r = client.post("/api/organize/duplicates", headers={"Origin": origin})
    assert r.status_code == 403
    assert not jobs.snapshot().is_running and jobs.snapshot().source == ""


@pytest.mark.parametrize("origin", [None, "http://localhost:5173", "http://127.0.0.1:8001", "http://127.0.0.1:40123"])
def test_local_or_no_origin_post_is_allowed(client, origin):
    headers = {"Origin": origin} if origin else {}
    r = client.post("/api/organize/duplicates", headers=headers)
    assert r.status_code == 200, r.text


def test_cors_header_only_for_local_origins(client, monkeypatch):
    from core.link_manager import LinkManager
    monkeypatch.setattr(LinkManager, "get_linked_vocab_for_sentence", classmethod(lambda cls, t: []))
    ok = client.get("/api/links/badge/sentence?text=hi", headers={"Origin": "http://127.0.0.1:40123"})
    assert ok.headers.get("access-control-allow-origin") == "http://127.0.0.1:40123"
    bad = client.get("/api/links/badge/sentence?text=hi", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


# ---- ⑤ promote backup -----------------------------------------------------
ORIGINAL_FIELDS = {"단어": {"value": "beg"}, "뜻": {"value": "구걸하다"}, "예문": {"value": "He begged."}}
CARD_INFO = [{"cardId": 11, "interval": 40, "factor": 1300, "reps": 22, "lapses": 9, "due": 123, "type": 2, "queue": 2}]


class FakeAnki:
    def __init__(self):
        self.calls = []

    def invoke(self, action, **params):
        self.calls.append(action)
        if action == "notesInfo":
            return [{"noteId": 5, "fields": ORIGINAL_FIELDS, "tags": ["leech"], "cards": [11]}]
        if action == "cardsInfo":
            return CARD_INFO
        return None


def _req():
    return PromoteChunkRequest(note_id=5, new_chunk="beg for mercy", meaning="자비를 구하다", pos="v",
                               example_1="a", trans_1="b", example_2="c", trans_2="d", explanation="e",
                               add_sentences_to_deck=False, reset_to_new=True)


@pytest.fixture
def fake_anki(monkeypatch, tmp_path):
    f = FakeAnki()
    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(f.invoke))
    monkeypatch.setattr(corpus_service.AnkiTTSFiller, "generate_gtts", staticmethod(lambda t: ("", None)))
    monkeypatch.setattr(corpus_service.LinkManager, "index_single_vocab", classmethod(lambda cls, *a, **k: None))
    monkeypatch.setattr(corpus_service, "PROMOTE_BACKUP_DIR", tmp_path / "promote", raising=False)
    return f


def test_promote_writes_backup_before_modifying(fake_anki, tmp_path):
    res = corpus_service.CorpusService.promote_chunk(_req())
    assert res.success, res.error
    files = list((tmp_path / "promote").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["note"]["fields"]["단어"]["value"] == "beg"
    assert data["cards"][0]["reps"] == 22 and data["cards"][0]["interval"] == 40
    # 백업(cardsInfo)이 어떤 변경 호출보다 먼저
    assert fake_anki.calls.index("cardsInfo") < fake_anki.calls.index("updateNoteFields")


def test_promote_aborts_if_backup_fails(fake_anki, monkeypatch, tmp_path):
    blocker = tmp_path / "promote"
    blocker.write_text("not a dir")  # 디렉터리를 만들 수 없게 막는다
    res = corpus_service.CorpusService.promote_chunk(_req())
    assert not res.success
    assert "updateNoteFields" not in fake_anki.calls and "forgetCards" not in fake_anki.calls


# ---- dashboard audio field ------------------------------------------------
def test_dashboard_counts_empty_sound_field(client, monkeypatch):
    queries = []

    def invoke(action, **params):
        if action == "version":
            return 6
        if action == "deckNames":
            return []
        if action == "findNotes":
            queries.append(params["query"])
            return [1, 2] if "소리:" in params["query"] else []
        if action == "findCards":
            return []
        return []

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    from backend.routers import dashboard

    class NoInbox:
        def fetch_inbox_content(self):
            return None

    monkeypatch.setattr(dashboard, "ObsidianManager", NoInbox)
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    assert r.json()["maintenance"]["missing_audio_count"] == 2
    assert not any("오디오" in q for q in queries)
