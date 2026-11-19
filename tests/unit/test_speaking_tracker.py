"""speaking.tracker 단위 테스트: Anki 1장 트래커 카드(1 -> 0) 및 미션 어휘 추출."""
from speaking.tracker import (
    SPEAKING_DECK,
    TRACKER_TAG,
    AnkiSpeakingTracker,
    fetch_mission_vocab,
)


class FakeAnkiInvoke:
    def __init__(self, existing_notes=None, existing_cards=None, vocab_notes=None):
        self.calls = []
        self.existing_notes = list(existing_notes or [])
        self.existing_cards = list(existing_cards or [])
        self.vocab_notes = dict(vocab_notes or {})

    def __call__(self, action, **params):
        self.calls.append((action, params))
        if action == "createDeck":
            return 1
        if action == "findNotes":
            q = params.get("query", "")
            if TRACKER_TAG in q:
                return list(self.existing_notes)
            if "English Vocabulary" in q:
                return list(self.vocab_notes.keys())
            return []
        if action == "addNote":
            self.existing_notes.append(5001)
            self.existing_cards.append(6001)
            return 5001
        if action == "findCards":
            return list(self.existing_cards)
        if action == "notesInfo":
            return [self.vocab_notes[nid] for nid in params["notes"] if nid in self.vocab_notes]
        if action in ("unsuspend", "setDueDate"):
            return True
        return None


def test_ensure_tracker_card_creates_deck_and_single_card_when_missing():
    anki = FakeAnkiInvoke()
    tracker = AnkiSpeakingTracker(invoke=anki)

    card_id = tracker.ensure_tracker_card()

    assert card_id == 6001
    actions = [a for a, _ in anki.calls]
    assert "createDeck" in actions
    assert "addNote" in actions
    add_params = next(p for a, p in anki.calls if a == "addNote")
    assert add_params["note"]["deckName"] == SPEAKING_DECK
    assert add_params["note"]["modelName"] == "Basic"
    assert TRACKER_TAG in add_params["note"]["tags"]


def test_reset_daily_sets_due_today_and_unsuspends():
    anki = FakeAnkiInvoke(existing_notes=[5001], existing_cards=[6001])
    tracker = AnkiSpeakingTracker(invoke=anki)

    res = tracker.reset_daily()

    assert res == {"card_id": 6001, "due_days": "0"}
    assert ("unsuspend", {"cards": [6001]}) in anki.calls
    assert ("setDueDate", {"cards": [6001], "days": "0"}) in anki.calls


def test_mark_done_moves_single_tracker_card_to_tomorrow():
    anki = FakeAnkiInvoke(existing_notes=[5001], existing_cards=[6001])
    tracker = AnkiSpeakingTracker(invoke=anki)

    res = tracker.mark_done()

    assert res == {"card_id": 6001, "due_days": "1"}
    assert ("setDueDate", {"cards": [6001], "days": "1"}) in anki.calls


def test_fetch_mission_vocab_returns_clean_expressions_without_html():
    vocab_notes = {
        1: {"noteId": 1, "fields": {"단어": {"value": "<b>bottleneck</b>"}, "뜻": {"value": "병목 현상"}}},
        2: {"noteId": 2, "fields": {"단어": {"value": "pay off"}, "뜻": {"value": "결실을 맺다"}}},
        3: {"noteId": 3, "fields": {"단어": {"value": "take a toll on"}, "뜻": {"value": "타격을 주다"}}},
    }
    anki = FakeAnkiInvoke(vocab_notes=vocab_notes)

    items = fetch_mission_vocab(count=2, invoke=anki)

    assert len(items) == 2
    assert all("<b>" not in item["word"] for item in items)
    assert all(item["meaning"] for item in items)


def test_update_log_writes_markdown_stats_and_recent_table_to_tracker_note():
    anki = FakeAnkiInvoke(existing_notes=[5001], existing_cards=[6001])
    tracker = AnkiSpeakingTracker(invoke=anki)

    tracker.update_log(
        streaks={"current": 4, "longest": 7, "total_completed": 12},
        recent_14d={"attempts_count": 18, "avg_wpm": 118.4, "avg_fillers": 2.3, "avg_long_pauses": 0.6},
        recent_sessions=[
            {
                "session_date": "2026-11-18",
                "track": "interview",
                "topic_prompt": "Tell me about a tough bug you fixed.",
                "pass1_wpm": 96.0,
                "pass2_wpm": 124.0,
                "pass1_fillers": 5,
                "pass2_fillers": 1,
                "score": 7.8,
                "native_model": "We isolated the root cause within an hour.",
            }
        ],
    )

    update_calls = [p for a, p in anki.calls if a == "updateNoteFields"]
    assert len(update_calls) == 1
    note_payload = update_calls[0]["note"]
    assert note_payload["id"] == 5001
    front = note_payload["fields"]["앞면"]
    back = note_payload["fields"]["뒷면"]
    assert "연속 4일" in front
    assert "118.4" in front
    assert "We isolated the root cause within an hour." in front
    assert "2026-11-18" in back
    assert "96->124" in back or "96 -> 124" in back
