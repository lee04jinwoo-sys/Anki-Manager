"""/undo로 카드를 지울 때 링크 색인과, 문장 등록 때 단어 카드 '예문'에 덧붙인 문장을 되돌린다."""
import pytest

from core import link_manager
from core.link_manager import LinkManager, get_db_connection, init_db
from integrations.anki_connect import AnkiConnector


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(link_manager, "DB_PATH", tmp_path / "links.db")
    init_db()
    notes = {
        10: {"예문": "Old example. ||| I broke the ice at the party."},   # 문장이 덧붙은 단어 카드
        11: {"예문": "I broke the ice at the party."},
        12: {"예문": "Unrelated sentence."},
    }
    updates = []

    def get_notes_info(cls, ids):
        return [{"noteId": i, "fields": {k: {"value": v} for k, v in notes[i].items()}} if i in notes else {}
                for i in ids]

    def update_note_fields(cls, note_id, fields):
        updates.append((note_id, fields))
        notes[note_id].update(fields)

    monkeypatch.setattr(AnkiConnector, "get_notes_info", classmethod(get_notes_info))
    monkeypatch.setattr(AnkiConnector, "update_note_fields", classmethod(update_note_fields))

    with get_db_connection() as conn:
        c = conn.cursor()
        c.executemany("INSERT INTO vocab_cache (note_id, word, meaning, pos, link_count) VALUES (?, ?, '', '', ?)",
                      [(10, "break the ice", 2), (11, "ice", 1), (12, "other", 1)])
        c.executemany("INSERT INTO links (vocab_note_id, vocab_word, sentence_note_id, sentence_text) VALUES (?, ?, ?, ?)",
                      [(10, "break the ice", 500, "I broke the ice at the party."),
                       (11, "ice", 500, "I broke the ice at the party."),
                       (10, "break the ice", 501, "Old example."),
                       (12, "other", 502, "Unrelated sentence.")])
        conn.commit()
    return notes, updates


def _rows(sql, *args):
    with get_db_connection() as conn:
        return [tuple(r) for r in conn.execute(sql, args).fetchall()]


def test_removing_sentence_reverts_appended_examples_and_links(env):
    notes, updates = env
    LinkManager.remove_note(500)

    assert notes[10]["예문"] == "Old example."
    assert notes[11]["예문"] == ""
    assert notes[12]["예문"] == "Unrelated sentence."           # 관련 없는 카드는 그대로
    assert {u[0] for u in updates} == {10, 11}
    assert _rows("SELECT sentence_note_id FROM links WHERE sentence_note_id = 500") == []
    assert _rows("SELECT link_count FROM vocab_cache WHERE note_id = 10") == [(1,)]
    assert _rows("SELECT link_count FROM vocab_cache WHERE note_id = 11") == [(0,)]


def test_removing_vocab_drops_its_cache_and_links(env):
    notes, updates = env
    LinkManager.remove_note(12)

    assert _rows("SELECT * FROM vocab_cache WHERE note_id = 12") == []
    assert _rows("SELECT * FROM links WHERE vocab_note_id = 12") == []
    assert updates == []                                       # 다른 카드 필드는 안 건드림


def test_unknown_note_is_a_noop(env):
    _, updates = env
    LinkManager.remove_note(999)
    assert updates == []
    assert len(_rows("SELECT * FROM links")) == 4


def test_failed_example_revert_still_cleans_index(env, monkeypatch):
    def boom(cls, note_id, fields):
        raise RuntimeError("anki down")

    monkeypatch.setattr(AnkiConnector, "update_note_fields", classmethod(boom))
    LinkManager.remove_note(500)          # 예외가 밖으로 나오지 않아야 한다
    assert _rows("SELECT * FROM links WHERE sentence_note_id = 500") == []
