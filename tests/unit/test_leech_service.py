"""Leech 처리: 단어별 처리 방법 추천과 일괄 실행. 보류(suspend)는 선택지에 없다."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from backend.services import leech_service as ls
from backend.services.jobs import jobs
from integrations.anki_connect import AnkiConnector


# ---- 추천 규칙 -----------------------------------------------------------
def test_common_single_verb_with_many_lapses_suggests_promote():
    s = ls.suggest_action(word="lurk", lapses=15, link_count=0, tier="freq::tier2_common", pos="v")
    assert s["action"] == "promote"


def test_noun_is_not_promoted():
    # anthropology(인류학) 같은 명사는 청크로 바꿀 이유가 약하다
    s = ls.suggest_action(word="anthropology", lapses=13, link_count=0, tier="freq::tier2_common", pos="n")
    assert s["action"] == "examples"


def test_phrase_is_not_promoted_even_if_common():
    s = ls.suggest_action(word="come over", lapses=18, link_count=4, tier="freq::tier1_essential")
    assert s["action"] != "promote"


def test_few_linked_sentences_suggests_examples():
    s = ls.suggest_action(word="as for A", lapses=16, link_count=0, tier="freq::tier1_essential")
    assert s["action"] == "examples"


def test_rare_specialized_word_gets_examples_never_suspend():
    s = ls.suggest_action(word="cytokinesis", lapses=13, link_count=0, tier="freq::tier5_rare")
    assert s["action"] == "examples"
    assert "suspend" not in ls.ACTIONS


def test_well_linked_word_that_keeps_failing_suggests_reset():
    # come over: 문장 5개로 문맥은 충분한데 18회 오답 → 처음부터 다시
    s = ls.suggest_action(word="come over", lapses=18, link_count=5, tier="freq::tier1_essential")
    assert s["action"] == "reset"
    assert "18회" in s["reason"]


def test_well_linked_word_with_few_lapses_suggests_review_today():
    s = ls.suggest_action(word="go over A", lapses=5, link_count=5, tier="freq::tier1_essential")
    assert s["action"] == "review_today"


# ---- 실행 ---------------------------------------------------------------
CARDS = {1: [11, 12], 2: [21, 22], 3: [31], 4: [41]}


@pytest.fixture
def anki(monkeypatch, tmp_path):
    calls = []

    def invoke(action, **p):
        calls.append((action, p))
        if action == "notesInfo":
            return [{"noteId": n, "cards": CARDS[n]} for n in p["notes"]]
        if action == "cardsInfo":
            # 12, 22 는 멀쩡한 카드 (간격 190일, 오답 2회) → 건드리면 안 된다
            healthy = {12, 22}
            return [{"cardId": c, "interval": 190 if c in healthy else 30, "due": 900,
                     "factor": 2100 if c in healthy else 1300, "reps": 20, "lapses": 2 if c in healthy else 9,
                     "type": 2, "queue": 2, "left": 0, "deckName": "V", "mod": 1} for c in p["cards"]]
        if action in ("setDueDate", "forgetCards"):
            return True
        raise AssertionError(action)

    generated = []

    class FakeGen:
        def generate_and_add_sentences(self, words_data, generate_audio=True):
            generated.extend(words_data)
            return {"success": True, "created_count": len(words_data), "results": []}

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    monkeypatch.setattr(ls, "BatchSentenceGenerator", FakeGen)
    monkeypatch.setattr(ls, "BACKUP_DIR", tmp_path / "leech")
    return calls, generated, tmp_path / "leech"


def _items():
    return [
        {"note_id": 1, "word": "go over A", "meaning": "검토하다", "action": "review_today"},
        {"note_id": 2, "word": "dusk", "meaning": "황혼", "action": "reset"},
        {"note_id": 3, "word": "meiosis", "meaning": "감수분열", "action": "examples"},
        {"note_id": 4, "word": "whisk", "meaning": "휘젓다", "action": "skip"},
    ]


def test_apply_runs_each_action_on_the_right_cards(anki):
    calls, generated, _ = anki
    summary = ls.apply_actions(_items())
    actions = {a: p for a, p in calls if a in ("setDueDate", "forgetCards")}
    # 노트의 카드 중 Leech 카드만 (멀쩡한 카드 12, 22 는 제외)
    assert actions["setDueDate"] == {"cards": [11], "days": "0"}
    assert actions["forgetCards"] == {"cards": [21]}
    assert [g["note_id"] for g in generated] == [3]
    assert summary == {"review_today": 1, "reset": 1, "examples": 1, "skip": 1, "sentences_created": 1}


def test_apply_backs_up_scheduling_before_writing(anki):
    calls, _, backup_dir = anki
    ls.apply_actions(_items())
    files = list(backup_dir.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert {c["cardId"] for c in data["cards"]} == {11, 12, 21, 22}
    order = [a for a, _ in calls]
    assert order.index("cardsInfo") < order.index("setDueDate")


def test_apply_aborts_without_writes_if_backup_fails(anki):
    calls, generated, backup_dir = anki
    backup_dir.write_text("not a dir")
    with pytest.raises(Exception):
        ls.apply_actions(_items())
    assert not any(a in ("setDueDate", "forgetCards") for a, _ in calls)
    assert generated == []


def test_promote_is_not_executed_in_batch(anki):
    calls, generated, _ = anki
    summary = ls.apply_actions([{"note_id": 1, "word": "nuisance", "meaning": "", "action": "promote"}])
    assert not any(a in ("setDueDate", "forgetCards") for a, _ in calls) and generated == []
    assert summary["review_today"] == 0


# ---- API ----------------------------------------------------------------
def test_apply_endpoint_runs_as_job(anki, monkeypatch):
    import server
    jobs.reset()
    client = TestClient(server.app)
    r = client.post("/api/leech/apply", json={"items": _items()})
    assert r.status_code == 200 and r.json()["status"] == "success", r.text
    deadline = time.time() + 5
    while jobs.is_running and time.time() < deadline:
        time.sleep(0.01)
    s = jobs.snapshot()
    assert s.status == "success", s.logs
    assert any("다시 학습 1" in l.message for l in s.logs)


def test_apply_endpoint_rejects_unknown_action():
    import server
    r = TestClient(server.app).post("/api/leech/apply", json={"items": [{"note_id": 1, "word": "x", "action": "suspend"}]})
    assert r.status_code == 422


def test_leech_list_items_carry_suggestion_and_tier(monkeypatch):
    from core.link_manager import LinkManager
    from backend.routers import links as links_router

    monkeypatch.setattr(LinkManager, "get_vocab_list", classmethod(lambda cls, **k: {
        "total": 1, "limit": 25, "offset": 0,
        "items": [{"note_id": 1, "word": "lurk", "meaning": "숨어 있다", "pos": "v", "link_count": 0, "lapses": 15}],
    }))
    monkeypatch.setattr(links_router, "evaluate_expression_rank_and_tier", lambda w: (4200, "freq::tier2_common"))
    import server
    r = TestClient(server.app).get("/api/links/vocab?filter_mode=leech")
    item = r.json()["items"][0]
    assert item["tier"] == "freq::tier2_common"
    assert item["suggestion"]["action"] == "promote" and item["suggestion"]["reason"]
