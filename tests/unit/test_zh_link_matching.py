"""중국어 단어-문장 연결은 단어 단위로 맞춰야 한다. 글자 포함만 보면 '好'가 好吃·好久·好像에 붙는다."""
import pytest

from core import link_manager
from core.link_manager import LinkManager, get_db_connection, init_db
from integrations.anki_connect import AnkiConnector

VOCAB = {1: "好", 2: "好吃", 3: "一个星期", 4: "今天", 5: "天气", 6: "几", 7: "的"}
SENTENCES = {
    101: "可以推荐好吃的饭店吗?",
    102: "好久不见。",
    103: "那个男人好像很帅。",
    104: "大家好！",
    105: "我去了一个星期。",
    106: "今天天气很好。",
    107: "我们几点见?",
}
EXPECTED = {  # 문장 → 연결돼야 하는 단어 (그 외는 연결되면 안 됨)
    101: {"好吃"},
    102: set(),
    103: set(),
    104: {"好"},
    105: {"一个星期"},
    106: {"今天", "天气", "好"},
    107: set(),
}


def _links_by_sentence():
    with get_db_connection() as conn:
        rows = conn.execute("SELECT sentence_note_id, vocab_word FROM links WHERE lang = 'zh'").fetchall()
    out = {s: set() for s in SENTENCES}
    for r in rows:
        out[r["sentence_note_id"]].add(r["vocab_word"])
    return out


@pytest.fixture
def anki(monkeypatch, tmp_path):
    monkeypatch.setattr(link_manager, "DB_PATH", tmp_path / "links.db")
    init_db()

    def find_notes(cls, query):
        return list(VOCAB) if "Vocabulary" in query else list(SENTENCES)

    def get_notes_info(cls, ids):
        out = []
        for i in ids:
            if i in VOCAB:
                out.append({"noteId": i, "fields": {"단어": {"value": VOCAB[i]}, "뜻": {"value": ""}, "품사": {"value": ""}}})
            else:
                out.append({"noteId": i, "fields": {"문장": {"value": SENTENCES[i]}}})
        return out

    writes = []
    monkeypatch.setattr(AnkiConnector, "find_notes", classmethod(find_notes))
    monkeypatch.setattr(AnkiConnector, "get_notes_info", classmethod(get_notes_info))
    monkeypatch.setattr(AnkiConnector, "update_note_fields", classmethod(lambda cls, nid, f: writes.append(nid)))
    return writes


def test_full_scan_links_whole_words_only(anki):
    LinkManager.scan_and_rebuild_links(lang="zh")
    assert _links_by_sentence() == EXPECTED


def test_single_sentence_index_uses_same_rule(anki):
    LinkManager.scan_and_rebuild_links(lang="zh")
    with get_db_connection() as conn:
        conn.execute("DELETE FROM links WHERE lang = 'zh'")
        conn.commit()
    for sid, text in SENTENCES.items():
        LinkManager.index_single_sentence(sid, text, lang="zh")
    assert _links_by_sentence() == EXPECTED
