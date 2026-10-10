"""Leech 목록: 노트 단위로 한 번씩, 전체에서 오답(lapses) 많은 순으로 페이지를 나눈다."""
import pytest

from core import link_manager
from core.link_manager import LinkManager, init_db
from integrations.anki_connect import AnkiConnector

# note -> [(card_id, lapses, factor)] ; Anki가 돌려주는 카드 순서는 오답 수와 무관
CARDS = {
    10: [(101, 2, 1300), (102, 13, 1300), (103, 3, 2500)],   # 최악: 13 (같은 노트의 덜 나쁜 카드가 뒤에 온다)
    20: [(201, 5, 2500)],
    30: [(301, 8, 1300), (302, 1, 2500)],
    40: [(401, 4, 2500)],
}


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(link_manager, "DB_PATH", tmp_path / "links.db")
    init_db()
    order = [101, 201, 301, 401, 302, 102, 103]  # 의도적으로 뒤섞인 순서
    info = {cid: {"cardId": cid, "note": nid, "lapses": lap, "factor": f, "reps": lap * 3,
                  "fields": {"단어": {"value": f"w{nid}"}, "뜻": {"value": ""}, "품사": {"value": ""}}}
            for nid, cards in CARDS.items() for cid, lap, f in cards}

    def invoke(action, **p):
        if action == "findCards":
            q = p["query"]
            if "prop:lapses>=3" in q:
                return [c for c in order if info[c]["lapses"] >= 3]
            return order
        if action == "cardsInfo":
            return [info[c] for c in p["cards"]]
        raise AssertionError(action)

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))


def test_leech_list_one_row_per_note_sorted_globally(fake):
    page1 = LinkManager.get_vocab_list(limit=2, offset=0, filter_mode="leech")
    page2 = LinkManager.get_vocab_list(limit=2, offset=2, filter_mode="leech")
    assert page1["total"] == 4
    assert [i["note_id"] for i in page1["items"]] == [10, 30]
    assert [i["lapses"] for i in page1["items"]] == [13, 8]
    assert [i["note_id"] for i in page2["items"]] == [20, 40]


def test_worst_leech_unlinked_uses_all_cards_and_max_lapses(fake):
    # vocab_cache에 link_count=0 으로 4개 단어를 넣어둔다
    with link_manager.get_db_connection() as conn:
        conn.executemany("INSERT INTO vocab_cache (note_id, word, link_count) VALUES (?, ?, 0)",
                         [(n, f"w{n}") for n in CARDS])
        conn.commit()
    items = LinkManager.get_worst_leech_unlinked_vocab(count=2)
    assert [(i["note_id"], i["lapses"]) for i in items] == [(10, 13), (30, 8)]
