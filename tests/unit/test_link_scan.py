"""링크 스캔: 정규식이 잡는 변화형 문장을 역색인 사전 필터가 떨어뜨리면 안 된다."""
import pytest

from core import link_manager
from core.link_manager import LinkManager, get_db_connection
from integrations.anki_connect import AnkiConnector

SENTENCES = {
    101: "She accommodated all of us.",
    102: "We accommodate guests.",
    103: "They ran into trouble.",
    104: "He took it for granted.",
    105: "Nothing related here.",
}
VOCAB = {1: "accommodate", 2: "run into A", 3: "take A for granted"}


@pytest.fixture
def scan(monkeypatch, tmp_path):
    monkeypatch.setattr(link_manager, "DB_PATH", tmp_path / "links.db")

    def find_notes(cls, q):
        return list(VOCAB) if "Vocabulary" in q else list(SENTENCES)

    def notes_info(cls, ids):
        out = []
        for i in ids:
            if i in VOCAB:
                out.append({"noteId": i, "fields": {"단어": {"value": VOCAB[i]}, "뜻": {"value": ""}, "품사": {"value": ""}}})
            else:
                out.append({"noteId": i, "fields": {"문장": {"value": SENTENCES[i]}}})
        return out

    monkeypatch.setattr(AnkiConnector, "find_notes", classmethod(find_notes))
    monkeypatch.setattr(AnkiConnector, "get_notes_info", classmethod(notes_info))
    LinkManager.scan_and_rebuild_links()
    with get_db_connection() as conn:
        return {(r[0], r[1]) for r in conn.execute("SELECT vocab_note_id, sentence_note_id FROM links")}


def test_inflected_regular_verb_is_linked(scan):
    assert (1, 101) in scan and (1, 102) in scan


def test_irregular_verb_phrase_is_linked(scan):
    assert (2, 103) in scan
    assert (3, 104) in scan


def test_no_false_link(scan):
    assert not any(s == 105 for _, s in scan)
