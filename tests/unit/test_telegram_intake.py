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


@pytest.mark.parametrize("text", ["/start", "/help", "/start@ankimanager_bot"])
def test_commands_get_usage_without_backend_call(text):
    backend = FakeBackend({"success": True})

    reply = ti.handle_text(text, ALLOWED, ALLOWED, backend)

    assert backend.calls == []
    assert reply == ti.USAGE


# --- 여러 줄 등록 (2026-10-11) -----------------------------------------------

class RoutingBackend:
    """경로에 따라 성공 응답을 돌려주고 note_id를 1씩 늘린다."""
    def __init__(self, duplicate_words=()):
        self.calls = []
        self.next_id = 1000
        self.duplicate_words = set(duplicate_words)

    def __call__(self, path, payload):
        self.calls.append((path, payload))
        word = payload.get("word") or payload.get("sentence")
        if word in self.duplicate_words:
            return {"success": True, "duplicate": True, "data": {"word": word}}
        self.next_id += 1
        if path.endswith("vocab"):
            return {"success": True, "note_id": self.next_id, "data": {"word": word, "meaning": "뜻"}}
        return {"success": True, "note_id": self.next_id, "data": {"sentence": word, "translation": "번역"}}


def test_multiple_lines_are_registered_separately_with_one_reply():
    backend = RoutingBackend()
    added = []

    reply = ti.handle_text("serendipity\n\nNo way!\n  break the ice ", ALLOWED, ALLOWED, backend,
                           on_added=lambda: added.append(1))

    assert backend.calls == [("/api/cards/vocab", {"word": "serendipity"}),
                             ("/api/cards/sentence", {"sentence": "No way!"}),
                             ("/api/cards/vocab", {"word": "break the ice"})]
    assert "serendipity" in reply and "No way!" in reply and "break the ice" in reply
    assert "3" in reply.splitlines()[0]          # 첫 줄 요약에 처리 개수
    assert added == [1]                          # 동기화는 한 번만


def test_too_many_lines_are_refused_without_backend_calls():
    backend = RoutingBackend()
    reply = ti.handle_text("\n".join(f"w{i}" for i in range(ti.MAX_LINES + 1)), ALLOWED, ALLOWED, backend)
    assert backend.calls == []
    assert str(ti.MAX_LINES) in reply


# --- /undo -------------------------------------------------------------------

class FakeAnki:
    def __init__(self):
        self.notes = {}       # note_id -> reps
        self.deleted = []

    def reps(self, note_id):
        return self.notes.get(note_id)

    def delete(self, note_id):
        self.deleted.append(note_id)
        self.notes.pop(note_id, None)


def _ms(dt):
    return int(dt.timestamp() * 1000)


@pytest.fixture
def undo_env(tmp_path):
    import datetime
    now = datetime.datetime(2026, 10, 12, 12, 0, tzinfo=datetime.timezone.utc)
    history = ti.AddedHistory(tmp_path / "added.json")
    anki = FakeAnki()
    undo = lambda: ti.undo_last(history, anki, now)
    return now, history, anki, undo


def test_successful_adds_are_remembered_but_not_duplicates(undo_env):
    _, history, _, undo = undo_env
    backend = RoutingBackend(duplicate_words={"ice"})
    ti.handle_text("serendipity\nice", ALLOWED, ALLOWED, backend, history=history, undo=undo)
    assert [e["label"] for e in history.entries()] == ["serendipity"]


def test_undo_deletes_newest_then_next(undo_env):
    import datetime
    now, history, anki, undo = undo_env
    a, b = _ms(now - datetime.timedelta(hours=2)), _ms(now - datetime.timedelta(hours=1))
    anki.notes.update({a: 0, b: 0})
    history.push(a, "first")
    history.push(b, "second")
    synced = []

    r1 = ti.handle_text("/undo", ALLOWED, ALLOWED, RoutingBackend(), on_added=lambda: synced.append(1),
                        history=history, undo=undo)
    r2 = ti.handle_text("/undo", ALLOWED, ALLOWED, RoutingBackend(), history=history, undo=undo)

    assert anki.deleted == [b, a]
    assert "second" in r1 and "first" in r2
    assert synced == [1]                       # 삭제 뒤에도 동기화
    assert history.entries() == []


def test_undo_with_nothing_to_undo(undo_env):
    _, _, anki, undo = undo_env
    assert "없" in undo()
    assert anki.deleted == []


def test_undo_refuses_reviewed_card_and_keeps_it(undo_env):
    import datetime
    now, history, anki, undo = undo_env
    nid = _ms(now - datetime.timedelta(hours=1))
    anki.notes[nid] = 3
    history.push(nid, "reviewed")
    reply = undo()
    assert anki.deleted == [] and "복습" in reply
    assert len(history.entries()) == 1


def test_undo_refuses_after_24_hours(undo_env):
    import datetime
    now, history, anki, undo = undo_env
    nid = _ms(now - datetime.timedelta(hours=25))
    anki.notes[nid] = 0
    history.push(nid, "old")
    reply = undo()
    assert anki.deleted == [] and "24시간" in reply


def test_undo_skips_note_already_deleted_in_anki(undo_env):
    import datetime
    now, history, anki, undo = undo_env
    history.push(_ms(now - datetime.timedelta(hours=1)), "gone")   # Anki에 없음
    reply = undo()
    assert anki.deleted == [] and "이미" in reply
    assert history.entries() == []


def test_history_persists_and_is_capped(tmp_path):
    h = ti.AddedHistory(tmp_path / "added.json")
    for i in range(ti.AddedHistory.MAX + 5):
        h.push(i, f"w{i}")
    h2 = ti.AddedHistory(tmp_path / "added.json")
    entries = h2.entries()
    assert len(entries) == ti.AddedHistory.MAX
    assert entries[-1]["label"] == f"w{ti.AddedHistory.MAX + 4}"


def test_corrupt_history_file_starts_empty(tmp_path):
    p = tmp_path / "added.json"
    p.write_text("{oops")
    assert ti.AddedHistory(p).entries() == []


def test_anki_for_undo_deletes_note_then_cleans_links(monkeypatch):
    from core.link_manager import LinkManager
    from integrations.anki_connect import AnkiConnector
    order = []
    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(lambda action, **p: order.append((action, p))))
    monkeypatch.setattr(LinkManager, "remove_note", classmethod(lambda cls, nid: order.append(("remove_note", nid))))

    ti.AnkiForUndo.delete(77)

    assert order == [("deleteNotes", {"notes": [77]}), ("remove_note", 77)]
