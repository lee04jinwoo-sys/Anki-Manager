"""lang 컬럼이 생기기 전에 만든 links.db(서버의 실제 DB)에서도 init_db 후 언어별 조회가 돼야 한다."""
import sqlite3

from core import link_manager
from core.link_manager import LinkManager, init_db

OLD_SCHEMA = """
CREATE TABLE links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vocab_note_id INTEGER NOT NULL,
    vocab_word TEXT NOT NULL,
    sentence_note_id INTEGER NOT NULL,
    sentence_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vocab_note_id, sentence_note_id)
);
CREATE TABLE vocab_cache (
    note_id INTEGER PRIMARY KEY,
    word TEXT NOT NULL,
    meaning TEXT,
    pos TEXT,
    link_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO vocab_cache (note_id, word, meaning, pos, link_count) VALUES (1, 'ice', '얼음', 'n', 1);
INSERT INTO links (vocab_note_id, vocab_word, sentence_note_id, sentence_text)
    VALUES (1, 'ice', 2, 'I broke the ice.');
"""


def test_init_db_adds_lang_to_old_tables_and_keeps_rows_as_english(monkeypatch, tmp_path):
    db = tmp_path / "links.db"
    with sqlite3.connect(db) as conn:
        conn.executescript(OLD_SCHEMA)
    monkeypatch.setattr(link_manager, "DB_PATH", db)

    init_db()

    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT lang FROM links").fetchall() == [("en",)]
        assert conn.execute("SELECT lang FROM vocab_cache").fetchall() == [("en",)]
    assert LinkManager.get_linked_sentences_for_vocab("ice", lang="en")
    assert LinkManager.get_linked_sentences_for_vocab("ice", lang="zh") == []
