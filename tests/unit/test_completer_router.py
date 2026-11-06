"""NoteCompleter가 라우터를 켰을 때만 쓰고, 라우터가 전부 실패하면 기존 Gemini 유료 키로 돌아가는지.

텔레그램 경로에서만 라우터를 켠다 (요청의 use_free_router).
"""
import json

import pytest

from core import completer as completer_mod
from core import llm_router
from core.completer import NoteCompleter


class FakeGeminiClient:
    """genai.Client 대역. 호출 수를 세고 정해진 JSON을 돌려준다."""

    def __init__(self, payload):
        self.calls = 0
        payload_text = json.dumps(payload, ensure_ascii=False)
        outer = self

        class _Models:
            def generate_content(self, **kwargs):
                outer.calls += 1
                return type("R", (), {"text": payload_text})()

        self.models = _Models()


@pytest.fixture
def gemini(monkeypatch):
    client = FakeGeminiClient({"vocab": [{"단어": "luck", "뜻": "유료키 답"}]})
    monkeypatch.setattr(completer_mod.genai, "Client", lambda **kw: client)
    return client


def test_router_answer_is_used_when_enabled(gemini, monkeypatch):
    monkeypatch.setattr(completer_mod, "generate_json",
                        lambda *a, **k: ({"vocab": [{"단어": "luck", "뜻": "무료 답"}]}, "free-a"))

    res = NoteCompleter(use_router=True).enrich_vocab([{"단어": "luck", "뜻": ""}])

    assert res[0]["뜻"] == "무료 답"
    assert gemini.calls == 0


def test_router_failure_falls_back_to_paid_gemini(gemini, monkeypatch):
    def fail(*a, **k):
        raise llm_router.AllRoutesFailed("all down")

    monkeypatch.setattr(completer_mod, "generate_json", fail)

    res = NoteCompleter(use_router=True).enrich_vocab([{"단어": "luck", "뜻": ""}])

    assert res[0]["뜻"] == "유료키 답"
    assert gemini.calls == 1


def test_router_is_not_used_by_default(gemini, monkeypatch):
    def must_not_call(*a, **k):
        raise AssertionError("router used without use_router=True")

    monkeypatch.setattr(completer_mod, "generate_json", must_not_call)

    res = NoteCompleter().enrich_vocab([{"단어": "luck", "뜻": ""}])

    assert res[0]["뜻"] == "유료키 답"


def test_router_answer_goes_through_same_cleanup(gemini, monkeypatch):
    """라우터 응답도 기존처럼 중첩 해제·HTML 엔티티 제거를 거친다."""
    monkeypatch.setattr(completer_mod, "generate_json",
                        lambda *a, **k: ({"sentence": {"해설": "A &amp; B"}}, "free-a"))

    res = NoteCompleter(use_router=True)._generate("p")

    assert res == {"해설": "A & B"}


@pytest.mark.parametrize("flag", [True, False])
def test_vocab_card_passes_flag_to_completer(monkeypatch, flag):
    from backend.schemas.cards import VocabCreateRequest
    from backend.services import card_service

    seen = {}

    class FakeCompleter:
        def __init__(self, use_router=False, **kw):
            seen["use_router"] = use_router

        def enrich_vocab(self, vocab):
            return [{"뜻": "행운", "품사": "n", "예문": "Good luck."}]

    monkeypatch.setattr(card_service, "NoteCompleter", FakeCompleter)
    monkeypatch.setattr(card_service.AnkiConnector, "add_note", lambda *a, **k: 7)
    monkeypatch.setattr(card_service, "queue_background_audio", lambda *a, **k: None)
    monkeypatch.setattr(card_service.LinkManager, "index_single_vocab", lambda *a, **k: None, raising=False)

    card_service.create_vocab_card(VocabCreateRequest(word="luck", generate_audio=False, use_free_router=flag))

    assert seen["use_router"] is flag


@pytest.mark.parametrize("flag", [True, False])
def test_sentence_card_passes_flag_to_completer(monkeypatch, flag):
    from backend.schemas.cards import SentenceCreateRequest
    from backend.services import card_service

    seen = {}

    class FakeCompleter:
        def __init__(self, use_router=False, **kw):
            seen["use_router"] = use_router

        def enrich_sentences(self, sentences):
            return [{"문장": sentences[0], "해설": "번역"}]

    monkeypatch.setattr(card_service, "NoteCompleter", FakeCompleter)
    monkeypatch.setattr(card_service.AnkiConnector, "add_note", lambda *a, **k: 7)
    monkeypatch.setattr(card_service, "queue_background_audio", lambda *a, **k: None)
    monkeypatch.setattr(card_service.LinkManager, "index_single_sentence", lambda *a, **k: None)

    card_service.create_sentence_card(
        SentenceCreateRequest(sentence="No way!", generate_audio=False, use_free_router=flag))

    assert seen["use_router"] is flag


def test_telegram_asks_backend_for_free_router():
    from integrations import telegram_intake as ti

    calls = []

    def backend(path, payload):
        calls.append((path, payload))
        return {"success": True, "note_id": 1, "data": {}}

    ti.handle_text("serendipity", 1, 1, backend)
    ti.handle_text("No way!", 1, 1, backend)

    assert len(calls) == 2
    assert all(payload.get("use_free_router") is True for _, payload in calls)
