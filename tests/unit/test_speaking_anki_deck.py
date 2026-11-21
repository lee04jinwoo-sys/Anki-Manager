"""speaking.anki_deck 단위 테스트: 전용 프리셋, 72장 시딩, FSRS 큐 조회, answerCards, 뒷면 로그."""
import pytest

from speaking.anki_deck import (
    DAILY_TAG,
    LEGACY_TRACKER_TAG,
    QUESTION_TAG,
    SPEAKING_DECK,
    SPEAKING_PRESET_NAME,
    AnkiSpeakingDeck,
)
from speaking.models import DailyQuestion


class FakeAnki:
    def __init__(
        self,
        deck_cfg=None,
        fail_empty_delays=False,
        existing_notes=None,
        tracker_notes=None,
        deck_stats=None,
        learn_ids=None,
        rev_ids=None,
        new_ids=None,
        cards_info=None,
        notes_info=None,
        answer_result=None,
    ):
        self.calls = []
        self.deck_cfg = deck_cfg or {
            "id": 100,
            "name": "기본",
            "new": {"perDay": 20, "delays": [1.0, 10.0]},
            "rev": {"perDay": 200},
            "lapse": {"delays": [10.0]},
            "desiredRetention": 0.9,
        }
        self.fail_empty_delays = fail_empty_delays
        self.existing_notes = list(existing_notes or [])
        self.tracker_notes = list(tracker_notes or [])
        self.deck_stats = deck_stats or {
            "1795067674171": {
                "deck_id": 1795067674171,
                "name": "Speaking",
                "new_count": 1,
                "learn_count": 0,
                "review_count": 1,
                "total_in_deck": 72,
            }
        }
        self.learn_ids = list(learn_ids or [])
        self.rev_ids = list(rev_ids or [])
        self.new_ids = list(new_ids or [])
        self.cards_info = list(cards_info or [])
        self.notes_info = list(notes_info or [])
        self.answer_result = [True] if answer_result is None else answer_result

    def __call__(self, action, **params):
        self.calls.append((action, params))
        if action == "createDeck":
            return 1795067674171
        if action == "getDeckConfig":
            return dict(self.deck_cfg)
        if action == "cloneDeckConfigId":
            return 222
        if action == "saveDeckConfig":
            cfg = params["config"]
            if self.fail_empty_delays and cfg["new"].get("delays") == []:
                raise RuntimeError("empty delays rejected")
            return True
        if action == "setDeckConfigId":
            return True
        if action == "findNotes":
            q = params.get("query", "")
            if LEGACY_TRACKER_TAG in q:
                return list(self.tracker_notes)
            if QUESTION_TAG in q:
                return list(self.existing_notes)
            return []
        if action == "deleteNotes":
            return None
        if action == "addNotes":
            return [9000 + i for i, _ in enumerate(params.get("notes", []))]
        if action == "getDeckStats":
            return self.deck_stats
        if action == "findCards":
            q = params.get("query", "")
            if "is:learn" in q:
                return list(self.learn_ids)
            if "is:review" in q:
                return list(self.rev_ids)
            if "is:new" in q:
                return list(self.new_ids)
            return []
        if action == "cardsInfo":
            return list(self.cards_info)
        if action == "notesInfo":
            return list(self.notes_info)
        if action == "answerCards":
            return self.answer_result
        if action == "updateNoteFields":
            return None
        return None


def test_ensure_preset_clones_and_falls_back_if_empty_delays_rejected():
    anki = FakeAnki(fail_empty_delays=True)
    deck = AnkiSpeakingDeck(invoke=anki)

    res = deck.ensure_speaking_deck_and_preset()

    assert res["preset_id"] == 222
    assert res["delays_used"] == [1440.0]
    save_calls = [p["config"] for a, p in anki.calls if a == "saveDeckConfig"]
    assert len(save_calls) == 2
    final_cfg = save_calls[-1]
    assert final_cfg["name"] == SPEAKING_PRESET_NAME
    assert final_cfg["new"]["perDay"] == 1
    assert final_cfg["rev"]["perDay"] == 3
    assert final_cfg["desiredRetention"] == 0.85
    assert ("setDeckConfigId", {"decks": [SPEAKING_DECK], "configId": 222}) in anki.calls


def test_seed_daily_questions_skips_existing_and_removes_legacy_tracker():
    q1 = DailyQuestion(
        id="daily_001",
        category="Campus",
        prompt="Explain your major simply.",
    )
    q2 = DailyQuestion(
        id="daily_002",
        category="Toronto",
        prompt="Share a TTC experience.",
    )
    anki = FakeAnki(
        existing_notes=[5001],
        tracker_notes=[4444],
        notes_info=[{"noteId": 5001, "tags": [QUESTION_TAG, DAILY_TAG, "speaking::id::daily_001"], "fields": {}}],
    )
    deck = AnkiSpeakingDeck(invoke=anki)

    removed = deck.remove_legacy_tracker_card()
    seeded = deck.seed_daily_questions([q1, q2])

    assert removed == 1
    assert ("deleteNotes", {"notes": [4444]}) in anki.calls
    assert seeded == {"added": 1, "skipped": 1}
    add_calls = [p["notes"] for a, p in anki.calls if a == "addNotes"]
    assert len(add_calls) == 1
    assert len(add_calls[0]) == 1
    assert "speaking::id::daily_002" in add_calls[0][0]["tags"]
    assert add_calls[0][0]["deckName"] == SPEAKING_DECK


def test_fetch_today_queue_caps_by_get_deck_stats_and_parses_cards():
    anki = FakeAnki(
        deck_stats={
            "1": {"deck_id": 1, "name": "Speaking", "new_count": 1, "learn_count": 0, "review_count": 1, "total_in_deck": 72}
        },
        rev_ids=[101, 102, 103],
        new_ids=[201, 202],
        cards_info=[
            {"cardId": 101, "note": 501, "type": 2, "reps": 3, "interval": 4},
            {"cardId": 201, "note": 502, "type": 0, "reps": 0, "interval": 0},
        ],
        notes_info=[
            {
                "noteId": 501,
                "tags": [QUESTION_TAG, "speaking::id::daily_003"],
                "fields": {
                    "앞면": {"value": "### Group conflict<br><br>How do you handle a slacking teammate?"},
                    "소주제": {"value": "Campus & Classes"},
                    "기타": {"value": "topic_id=daily_003"},
                },
            },
            {
                "noteId": 502,
                "tags": [QUESTION_TAG, "speaking::id::daily_010"],
                "fields": {
                    "앞면": {"value": "### Winter transit<br><br>Describe a snowy commute."},
                    "소주제": {"value": "Toronto Life"},
                    "기타": {"value": "topic_id=daily_010"},
                },
            },
        ],
    )
    deck = AnkiSpeakingDeck(invoke=anki)

    counts, cards = deck.fetch_today_queue()

    assert counts.remaining == 2
    assert len(cards) == 2
    assert cards[0].card_id == 101
    assert cards[0].is_new is False
    assert cards[0].topic_id == "daily_003"
    assert "How do you handle" in cards[0].prompt_text
    assert cards[1].card_id == 201
    assert cards[1].is_new is True


def test_answer_speaking_card_and_update_back_log():
    anki = FakeAnki(answer_result=[True])
    deck = AnkiSpeakingDeck(invoke=anki)

    deck.answer_speaking_card(101, 3)
    assert ("answerCards", {"answers": [{"cardId": 101, "ease": 3}]}) in anki.calls

    deck.update_card_back_log(
        note_id=501,
        history=[
            {
                "session_date": "2026-11-19",
                "score": 7.5,
                "ease": 3,
                "wpm": 116.2,
                "filler_count": 2,
                "native_model": "Let's divide the remaining tasks clearly.",
            }
        ],
    )
    upd = next(p["note"] for a, p in anki.calls if a == "updateNoteFields")
    assert upd["id"] == 501
    assert "2026-11-19" in upd["fields"]["뒷면"]
    assert "Let's divide the remaining tasks clearly." in upd["fields"]["뒷면"]

    bad_anki = FakeAnki(answer_result=[False])
    with pytest.raises(RuntimeError):
        AnkiSpeakingDeck(invoke=bad_anki).answer_speaking_card(101, 3)


def test_refresh_question_fronts_rewrites_only_changed_notes():
    q1 = DailyQuestion(id="daily_001", category="Campus", prompt="What do you study?")
    q2 = DailyQuestion(id="daily_002", category="Toronto", prompt="How is Toronto weather?")
    anki = FakeAnki(
        existing_notes=[1, 2, 3],
        notes_info=[
            {"noteId": 1, "tags": ["speaking::id::daily_001"], "fields": {"앞면": {"value": "### Old<br><br>x<br><br>- a"}}},
            {"noteId": 2, "tags": ["speaking::id::daily_002"], "fields": {"앞면": {"value": "How is Toronto weather?"}}},
            {"noteId": 3, "tags": ["speaking::id::daily_999"], "fields": {"앞면": {"value": "unknown"}}},
        ],
    )
    deck = AnkiSpeakingDeck(invoke=anki)

    assert deck.refresh_question_fronts([q1, q2]) == 1
    updates = [p for a, p in anki.calls if a == "updateNoteFields"]
    assert updates == [{"note": {"id": 1, "fields": {"앞면": "What do you study?"}}}]
