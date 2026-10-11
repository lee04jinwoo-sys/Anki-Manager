"""텔레그램으로 받은 단어·문장을 카드로 등록하고 결과를 답장하는 흐름.

텔레그램 API와 백엔드 호출은 가짜 함수로 바꿔 끼운다. 실제 네트워크·Anki에는 붙지 않는다.
"""
import pytest

from integrations import telegram_intake as ti

ALLOWED = 111


class FakeBackend:
    def __init__(self, response=None, exc=None):
        self.calls = []
        self.response = response
        self.exc = exc

    def __call__(self, path, payload):
        self.calls.append((path, payload))
        if self.exc:
            raise self.exc
        return self.response


def _update(update_id, text, chat_id=ALLOWED):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text}}


# --- 분류 ---------------------------------------------------------------

@pytest.mark.parametrize("text, kind, body", [
    ("serendipity", "vocab", "serendipity"),
    ("  break the ice  ", "vocab", "break the ice"),
    ("look forward to", "vocab", "look forward to"),
    ("I was about to call you.", "sentence", "I was about to call you."),
    ("Are you kidding me?", "sentence", "Are you kidding me?"),
    ("No way!", "sentence", "No way!"),
])
def test_classify_by_final_punctuation(text, kind, body):
    assert ti.classify(text) == (kind, body)


@pytest.mark.parametrize("text", ["", "   ", "\n"])
def test_classify_rejects_empty(text):
    assert ti.classify(text) is None


# --- 메시지 처리 ----------------------------------------------------------

def test_vocab_goes_to_vocab_endpoint_and_reply_shows_meaning():
    backend = FakeBackend({"success": True, "note_id": 5, "duplicate": False,
                           "data": {"word": "serendipity", "meaning": "뜻밖의 행운", "pos": "n"}})

    reply = ti.handle_text("serendipity", ALLOWED, ALLOWED, backend)

    assert backend.calls == [("/api/cards/vocab", {"word": "serendipity"})]
    assert "serendipity" in reply and "뜻밖의 행운" in reply and "단어" in reply


def test_sentence_goes_to_sentence_endpoint_and_reply_shows_translation():
    backend = FakeBackend({"success": True, "note_id": 6, "duplicate": False,
                           "data": {"sentence": "No way!", "translation": "말도 안 돼!"}})

    reply = ti.handle_text("No way!", ALLOWED, ALLOWED, backend)

    assert backend.calls == [("/api/cards/sentence", {"sentence": "No way!"})]
    assert "말도 안 돼!" in reply and "문장" in reply


def test_duplicate_is_reported_not_as_success():
    backend = FakeBackend({"success": False, "duplicate": True, "data": {"word": "ice"}})

    reply = ti.handle_text("ice", ALLOWED, ALLOWED, backend)

    assert "이미" in reply


def test_other_chats_are_ignored_without_calling_backend():
    backend = FakeBackend({"success": True})

    assert ti.handle_text("serendipity", 999, ALLOWED, backend) is None
    assert backend.calls == []


def test_backend_failure_becomes_error_reply():
    backend = FakeBackend(exc=ti.BackendError("Gemini quota exceeded"))

    reply = ti.handle_text("serendipity", ALLOWED, ALLOWED, backend)

    assert "실패" in reply and "Gemini quota exceeded" in reply


def test_empty_message_gets_usage_hint_without_backend_call():
    backend = FakeBackend({"success": True})

    reply = ti.handle_text("   ", ALLOWED, ALLOWED, backend)

    assert backend.calls == []
    assert "." in reply  # 문장은 마침표로 끝내라는 안내


# --- 업데이트 묶음 처리 ----------------------------------------------------

def test_process_updates_replies_and_advances_offset():
    backend = FakeBackend({"success": True, "data": {"word": "x", "meaning": "엑스"}})
    sent = []

    offset = ti.process_updates(
        [_update(10, "x"), _update(11, "y", chat_id=999), {"update_id": 12, "message": {"chat": {"id": ALLOWED}}}],
        ALLOWED, backend, lambda chat_id, text: sent.append((chat_id, text)),
    )

    assert offset == 13
    assert len(backend.calls) == 1          # 다른 채팅·글자 없는 메시지는 등록하지 않는다
    assert [c for c, _ in sent] == [ALLOWED]


def test_offset_advances_even_when_a_message_fails():
    """실패한 메시지를 다음 폴링에서 다시 받아 무한 반복하지 않는다."""
    backend = FakeBackend(exc=RuntimeError("boom"))
    sent = []

    offset = ti.process_updates([_update(20, "x")], ALLOWED, backend,
                                lambda chat_id, text: sent.append(text))

    assert offset == 21
    assert sent and "실패" in sent[0]


# --- 등록 직후 동기화 ------------------------------------------------------

def test_new_card_triggers_on_added():
    backend = FakeBackend({"success": True, "data": {"word": "x", "meaning": "엑스"}})
    added = []

    ti.handle_text("x", ALLOWED, ALLOWED, backend, on_added=lambda: added.append(1))

    assert added == [1]


@pytest.mark.parametrize("response, exc", [
    ({"success": False, "duplicate": True, "data": {"word": "x"}}, None),
    (None, ti.BackendError("boom")),
])
def test_duplicate_or_failure_does_not_trigger_on_added(response, exc):
    added = []

    ti.handle_text("x", ALLOWED, ALLOWED, FakeBackend(response, exc), on_added=lambda: added.append(1))

    assert added == []


def test_on_added_failure_still_returns_success_reply():
    backend = FakeBackend({"success": True, "data": {"word": "x", "meaning": "엑스"}})

    def broken():
        raise RuntimeError("sync down")

    reply = ti.handle_text("x", ALLOWED, ALLOWED, backend, on_added=broken)

    assert reply.startswith("✅")
