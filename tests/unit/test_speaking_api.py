"""FastAPI /api/speaking/* 엔드포인트 및 card_service tags 전달 단위 테스트."""
import base64
import datetime as dt

from fastapi.testclient import TestClient

from backend.routers import speaking as speaking_router
from speaking.models import CardCandidate, CoachFeedback, SpeakingMetrics, TranscriptionResult
from speaking.service import SpeakingService
from speaking.store import SpeakingStore
from server import app


class _FakeSTT:
    def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg", language="en"):
        return TranscriptionResult(
            transcript="Hello um testing speaking api.",
            metrics=SpeakingMetrics(duration_sec=4.0, word_count=5, wpm=75.0, filler_count=1, long_pause_count=0, max_pause_sec=0.4),
        )


class _FakeCoach:
    def evaluate_warmup(self, prompt, transcript, metrics):
        return CoachFeedback(summary="짧은 테스트 OK", score=7.5, native_model="Testing the speaking API.")

    def analyze_debrief(self, transcript):
        return CoachFeedback(
            summary="회수 OK",
            native_model="Let's wrap this up.",
            card_candidates=[
                CardCandidate(kind="sentence", text="Let's wrap this up.", translation="이만 마무리합시다."),
            ],
        )


class _FakeTracker:
    def __init__(self):
        self.resets = 0
        self.dones = 0

    def reset_daily(self):
        self.resets += 1
        return {"card_id": 7001, "due_days": "0"}

    def mark_done(self):
        self.dones += 1
        return {"card_id": 7001, "due_days": "1"}


def test_speaking_api_endpoints_end_to_end(monkeypatch, tmp_path):
    store = SpeakingStore(tmp_path / "api_speaking.db")
    tracker = _FakeTracker()
    created = []

    def fake_creator(kind, payload):
        created.append((kind, payload))
        return {"success": True, "note_id": 555, "duplicate": False}

    svc = SpeakingService(
        store=store,
        stt=_FakeSTT(),
        coach=_FakeCoach(),
        tracker=tracker,
        tts_fn=lambda text: b"OGG-DATA",
        vocab_fetcher=lambda count: [],
        card_creator=fake_creator,
        today_fn=lambda: dt.date(2026, 11, 18),
    )
    monkeypatch.setattr(speaking_router, "get_speaking_service", lambda: svc)

    client = TestClient(app)

    # 1) 트래커 리셋
    r_reset = client.post("/api/speaking/tracker/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["due_days"] == "0"
    assert tracker.resets == 1

    # 2) 세션 없이 음성 -> debrief 모드 + 후보 반환
    b64 = base64.b64encode(b"fake-audio").decode("ascii")
    r_voice = client.post("/api/speaking/voice", json={"audio_b64": b64, "filename": "test.ogg"})
    assert r_voice.status_code == 200
    body = r_voice.json()
    assert body["mode"] == "debrief"
    assert body["audio_b64"] == base64.b64encode(b"OGG-DATA").decode("ascii")
    assert len(body["candidates"]) == 1

    # 3) 후보 카드 추가
    cid = body["candidates"][0]["id"]
    r_add = client.post(f"/api/speaking/candidates/{cid}/add")
    assert r_add.status_code == 200
    assert r_add.json()["success"] is True
    assert created[0][1]["tags"] == ["speaking"]

    # 4) 세션 시작 -> 통계 -> 취소
    r_start = client.post("/api/speaking/start", json={"track": "daily"})
    assert r_start.status_code == 200
    assert r_start.json()["step"] == "warmup_1"

    r_stats = client.get("/api/speaking/stats")
    assert r_stats.status_code == 200
    assert r_stats.json()["done_today"] is False

    r_cancel = client.post("/api/speaking/cancel")
    assert r_cancel.status_code == 200
    assert r_cancel.json()["cancelled"] is True


def test_card_service_passes_optional_tags(monkeypatch):
    from backend.schemas.cards import SentenceCreateRequest
    from backend.services import card_service
    from core.link_manager import LinkManager
    from integrations.anki_connect import AnkiConnector

    captured = {}

    def fake_add_note(**kwargs):
        captured.update(kwargs)
        return 12345

    monkeypatch.setattr(AnkiConnector, "add_note", staticmethod(fake_add_note))
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
