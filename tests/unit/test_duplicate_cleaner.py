"""중복 정리: 영구 삭제하지 않고, 리뷰가 많은 노트를 남기며, HTML 차이는 무시한다."""
import pytest

import config
from integrations.anki_connect import AnkiConnector
from utils import cleaner


class FakeAnki:
    def __init__(self, notes, reps_by_card):
        self.notes = notes  # [{noteId, fields:{f:{value}}, cards:[...]}]
        self.reps = reps_by_card
        self.calls = []

    def invoke(self, action, **params):
        self.calls.append((action, params))
        if action == "findNotes":
            return [n["noteId"] for n in self.notes]
        if action == "notesInfo":
            ids = set(params["notes"])
            return [n for n in self.notes if n["noteId"] in ids]
        if action == "cardsInfo":
            return [{"cardId": c, "reps": self.reps.get(c, 0)} for c in params["cards"]]
        if action in ("addTags", "suspend", "deleteNotes"):
            return None
        raise AssertionError(f"unexpected action {action}")

    def actions(self, name):
        return [p for a, p in self.calls if a == name]


def _note(nid, word, cards):
    return {"noteId": nid, "fields": {"단어": {"value": word}}, "cards": cards}


@pytest.fixture
def fake(monkeypatch):
    def make(notes, reps):
        f = FakeAnki(notes, reps)
        monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(f.invoke))
        monkeypatch.setattr(
            config, "DUPLICATE_CLEANUP_LIST",
            [{"note_type": "English Vocabulary", "target_field": "단어", "case_sensitive": True}],
        )
        return f
    return make


def test_never_deletes_notes(fake):
    f = fake([_note(1, "run", [11]), _note(2, "run", [21])], {11: 5, 21: 1})
    cleaner.clean_duplicates()
    assert f.actions("deleteNotes") == []


def test_keeps_most_reviewed_and_suspends_rest(fake):
    # 먼저 나온 노트(1)는 리뷰 0회, 나중 노트(2)는 리뷰 30회 → 2를 남긴다
    f = fake([_note(1, "run", [11]), _note(2, "run", [21])], {11: 0, 21: 30})
    cleaner.clean_duplicates()
    assert f.actions("suspend") == [{"cards": [11]}]
    tagged = f.actions("addTags")
    assert tagged and tagged[0]["notes"] == [1]


def test_html_variants_are_duplicates(fake):
    f = fake([_note(1, "<b>run</b>", [11]), _note(2, "run&nbsp;", [21])], {11: 3, 21: 0})
    cleaner.clean_duplicates()
    assert f.actions("suspend") == [{"cards": [21]}]


def test_no_duplicates_no_changes(fake):
    f = fake([_note(1, "run", [11]), _note(2, "walk", [21])], {})
    cleaner.clean_duplicates()
    assert f.actions("suspend") == [] and f.actions("addTags") == []


def test_vocab_case_difference_is_not_duplicate(fake):
    # 'cancer'(암) / 'Cancer'(게자리), 'stem' / 'STEM' 은 서로 다른 단어
    f = fake([_note(1, "cancer", [11]), _note(2, "Cancer", [21]), _note(3, "stem", [31]), _note(4, "STEM", [41])], {})
    cleaner.clean_duplicates()
    assert f.actions("suspend") == []


def test_sentence_case_difference_is_duplicate(fake, monkeypatch):
    f = fake([], {})
    f.notes = [
        {"noteId": 1, "fields": {"문장": {"value": "Let&#x27;s Keep in touch."}}, "cards": [11]},
        {"noteId": 2, "fields": {"문장": {"value": "Let's keep in touch."}}, "cards": [21]},
    ]
    f.reps = {11: 4, 21: 0}
    monkeypatch.setattr(config, "DUPLICATE_CLEANUP_LIST", [{"note_type": "English Sentence", "target_field": "문장"}])
    cleaner.clean_duplicates()
    assert f.actions("suspend") == [{"cards": [21]}]
