"""FastAPI /api/speaking/* v2 엔드포인트 및 card_service tags 전달 단위 테스트."""
import base64
import datetime as dt

from fastapi.testclient import TestClient

from backend.routers import speaking as speaking_router
from server import app
from speaking.models import (
    CardCandidate,
    CardEvaluation,
    QueueCounts,
    SpeakingCard,
    SpeakingMetrics,
    TranscriptionResult,
)
from speaking.service import SpeakingService
from speaking.store import SpeakingStore


class _FakeSTT:
    def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg", language="en"):
        return TranscriptionResult(
            transcript="Hello testing speaking queue.",
            metrics=SpeakingMetrics(duration_sec=5.0, word_count=10, wpm=120.0, filler_count=0, long_pause_count=0, max_pause_sec=0.3),
        )


class _FakeCoach:
    def evaluate_card(self, card, transcript, metrics, prior_history=()):
        return CardEvaluation(
            score=8.0,
            recommended_ease=3,
            summary="명확함.",
            native_model="Here is a cleaner phrasing.",
            card_candidates=[CardCandidate(kind="sentence", text="Here is a cleaner phrasing.", translation="더 깔끔한 표현")],
        )

    def analyze_debrief(self, transcript):
        return CardEvaluation(
            score=7.0,
            recommended_ease=3,
            summary="회수 OK",
            native_model="Let's wrap this up.",
            card_candidates=[CardCandidate(kind="sentence", text="Let's wrap this up.", translation="마무리합시다.")],
        )


class _FakeDeck:
    def __init__(self):
        self.cards = [
            SpeakingCard(card_id=701, note_id=5701, topic_id="daily_001", category="Campus", title="T", prompt_text="Prompt 1", is_new=True),
        ]

    def get_deck_counts(self):
        return QueueCounts(new_count=len(self.cards), learn_count=0, review_count=0, total_in_deck=72)

    def fetch_today_queue(self):
        return self.get_deck_counts(), list(self.cards)

    def answer_speaking_card(self, card_id, ease):
        self.cards = [c for c in self.cards if c.card_id != card_id]

    def update_card_back_log(self, note_id, history):
        pass


def test_v2_speaking_api_endpoints_end_to_end(monkeypatch, tmp_path):
    store = SpeakingStore(tmp_path / "api_speaking.db")
    deck = _FakeDeck()
    created = []
    svc = SpeakingService(
        store=store,
        anki_deck=deck,
        stt=_FakeSTT(),
        coach=_FakeCoach(),
        tts_fn=lambda text: b"OGG-DATA",
        audio_dir=tmp_path / "audio",
        card_creator=lambda kind, payload: (created.append((kind, payload)) or {"success": True, "note_id": 555, "duplicate": False}),
        today_fn=lambda: dt.date(2026, 11, 19),
    )
    monkeypatch.setattr(speaking_router, "get_speaking_service", lambda: svc)

    client = TestClient(app)

    r_start = client.post("/api/speaking/queue/start")
    assert r_start.status_code == 200
    assert r_start.json()["status"] == "question"
    assert r_start.json()["card_id"] == 701

    b64 = base64.b64encode(b"fake-audio").decode("ascii")
    r_voice = client.post("/api/speaking/voice", json={"audio_b64": b64, "filename": "t.ogg"})
    assert r_voice.status_code == 200
    assert r_voice.json()["recommended_ease"] == 3
    assert r_voice.json()["audio_b64"] == base64.b64encode(b"OGG-DATA").decode("ascii")

    r_retry = client.post("/api/speaking/retry")
    assert r_retry.status_code == 200

    r_rate = client.post("/api/speaking/rate", json={"card_id": 701, "ease": 3})
    assert r_rate.status_code == 200
    assert r_rate.json()["status"] == "day_completed"
    cid = r_rate.json()["candidates"][0]["id"]

    r_add = client.post(f"/api/speaking/candidates/{cid}/add")
    assert r_add.status_code == 200
    assert created[0][1]["tags"] == ["speaking"]

    r_sum = client.get("/api/speaking/summary")
    assert r_sum.status_code == 200

    r_stats = client.get("/api/speaking/stats")
    assert r_stats.status_code == 200
    assert r_stats.json()["streaks"]["current"] == 1


def test_card_service_passes_optional_tags(monkeypatch):
    from backend.schemas.cards import SentenceCreateRequest
    from backend.services import card_service
    from core.link_manager import LinkManager
    from integrations.anki_connect import AnkiConnector

    captured = {}
    monkeypatch.setattr(AnkiConnector, "add_note", staticmethod(lambda **kw: (captured.update(kw) or 12345)))
    monkeypatch.setattr(LinkManager, "index_single_sentence", classmethod(lambda cls, nid, text: None))

    res = card_service.create_sentence_card(
        SentenceCreateRequest(
            sentence="That trade-off paid off.",
            translation="그 타협이 효과가 있었다.",
            auto_enrich=False,
            generate_audio=False,
            tags=["speaking", "speaking"],
        )
    )
    assert res.success is True
    assert captured["tags"] == ["speaking"]
