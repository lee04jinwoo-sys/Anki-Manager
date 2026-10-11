"""처리 기록: 처리한 단어는 기본 목록에서 숨기고, 처리 후 오답이 4회 늘면 '재발'로 다시 보여준다."""
import time

import pytest

from backend.services import leech_history as lh
from backend.services import leech_service as ls
from core import link_manager
from core.link_manager import LinkManager, init_db
from integrations.anki_connect import AnkiConnector

# note -> card lapses (factor 1300 → 모두 leech 조건)
LAPSES = {1: 18, 2: 16, 3: 9}


@pytest.fixture
def anki(monkeypatch, tmp_path):
    monkeypatch.setattr(link_manager, "DB_PATH", tmp_path / "links.db")
    monkeypatch.setattr(lh, "DB_PATH", tmp_path / "leech_treatments.db")
    monkeypatch.setattr(ls, "BACKUP_DIR", tmp_path / "backup")
    init_db()
    LinkManager.invalidate_leech_cache()
    lapses = dict(LAPSES)  # 테스트마다 새로 (재발 테스트가 값을 바꾼다)

    def invoke(action, **p):
        if action == "findCards":
            return [n * 10 for n in lapses]
        if action == "cardsInfo":
            return [{"cardId": c, "note": c // 10, "lapses": lapses[c // 10], "factor": 1300, "reps": 30,
                     "interval": 5, "queue": 2, "type": 2, "due": 1, "left": 0, "mod": 1, "deckName": "V",
                     "fields": {"단어": {"value": f"w{c // 10}"}, "뜻": {"value": ""}, "품사": {"value": ""}}}
                    for c in p["cards"]]
        if action == "notesInfo":
            return [{"noteId": n, "cards": [n * 10]} for n in p["notes"]]
        if action in ("forgetCards", "setDueDate"):
            return True
        raise AssertionError(action)

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    return lapses


def _ids(res):
    return [i["note_id"] for i in res["items"]]


def test_treated_word_is_hidden_until_four_new_lapses(anki):
    lh.record([{"note_id": 1, "word": "come over", "action": "reset", "lapses_at": 18}])
    LinkManager.invalidate_leech_cache()
    assert _ids(LinkManager.get_vocab_list(limit=10, offset=0, filter_mode="leech")) == [2, 3]

    anki[1] = 21  # 처리 후 3회 더 틀림 → 아직 숨김
    LinkManager.invalidate_leech_cache()
    assert 1 not in _ids(LinkManager.get_vocab_list(limit=10, offset=0, filter_mode="leech"))

    anki[1] = 22  # 4회 → 재발
    LinkManager.invalidate_leech_cache()
    res = LinkManager.get_vocab_list(limit=10, offset=0, filter_mode="leech")
    item = next(i for i in res["items"] if i["note_id"] == 1)
    assert item["treated"]["relapsed"] is True and item["treated"]["lapses_since"] == 4
    assert res["total"] == 3


def test_treated_tab_lists_treated_words_with_progress(anki):
    lh.record([{"note_id": 1, "word": "come over", "action": "reset", "lapses_at": 18},
               {"note_id": 2, "word": "as for A", "action": "examples", "lapses_at": 15}])
    res = LinkManager.get_vocab_list(limit=10, offset=0, filter_mode="treated")
    by_id = {i["note_id"]: i for i in res["items"]}
    assert set(by_id) == {1, 2}
    assert by_id[2]["treated"]["lapses_since"] == 1 and by_id[2]["treated"]["action"] == "examples"
    assert res["total"] == 2


def test_apply_records_treatments_except_skip_and_promote(anki):
    ls.apply_actions([
        {"note_id": 1, "word": "come over", "meaning": "", "action": "reset"},
        {"note_id": 3, "word": "w3", "meaning": "", "action": "skip"},
    ])
    rows = lh.get_all()
    assert set(rows) == {1}
    assert rows[1]["action"] == "reset" and rows[1]["lapses_at"] == 18


def test_retreating_replaces_the_record(anki):
    lh.record([{"note_id": 1, "word": "w1", "action": "examples", "lapses_at": 10}])
    lh.record([{"note_id": 1, "word": "w1", "action": "reset", "lapses_at": 18}])
    assert lh.get_all()[1]["action"] == "reset" and lh.get_all()[1]["lapses_at"] == 18


def test_link_stats_leech_count_excludes_treated_unless_relapsed(anki, monkeypatch):
    calls = []
    orig = AnkiConnector.invoke

    def invoke(action, **p):
        calls.append(action)
        if action == "findNotes":
            return [1, 2, 3]
        return orig(action, **p)

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    lh.record([{"note_id": 1, "word": "come over", "action": "reset", "lapses_at": 18},
               {"note_id": 2, "word": "as for A", "action": "reset", "lapses_at": 12}])  # 2 는 16-12=4 → 재발
    assert LinkManager.get_stats()["leech_count"] == 2  # 1 제외, 2(재발)·3 포함
