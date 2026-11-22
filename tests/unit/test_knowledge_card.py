"""지식 카드 게이트웨이 (/api/cards/knowledge).

learning 저장소의 study.py가 공부 중 틀린 것·용어를 Knowledge Q&A 노트로 보낸다.
앞면은 {{질문}}, 뒷면은 {{정답}}·{{설명}}·{{출처}}. 덱이 없으면 만들고, 같은 질문은 중복으로 돌려준다.
LLM 보강과 오디오는 하지 않는다 (내용은 보내는 쪽이 정한다).
"""
import pytest
from fastapi.testclient import TestClient

from backend.schemas.cards import KnowledgeCreateRequest
from backend.services import card_service
from config import DECK_KNOWLEDGE, MODEL_KNOWLEDGE
from integrations.anki_connect import AnkiConnector


@pytest.fixture
def anki(monkeypatch):
    state = {"calls": [], "added": [], "existing": set()}

    def invoke(action, **params):
        state["calls"].append(action)
        if action == "createDeck":
            state["deck"] = params["deck"]
            return 1
        if action == "addNote":
            note = params["note"]
            if note["fields"]["질문"] in state["existing"]:
                raise Exception("cannot create note because it is a duplicate")
            state["added"].append(note)
            return 777
        if action == "findCards":
            return []
        raise AssertionError(f"unexpected AnkiConnect call: {action}")

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    monkeypatch.setattr(card_service, "queue_background_audio",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no audio for knowledge cards")))
    monkeypatch.setattr(card_service, "NoteCompleter",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no LLM for knowledge cards")))
    return state


def req(**kw):
    base = dict(question="2자산 포트폴리오 분산 식의 교차항은?", answer="2 w₁ w₂ σ₁₂",
                explanation="교차항 계수 2를 빠뜨리기 쉽다.", topic="MIE375 Financial Engineering",
                source="MIE 375 Nov 5 2026 Mean Variance Portfolio.pdf p.12", tags=["learning::mie375", " "])
    base.update(kw)
    return KnowledgeCreateRequest(**base)


def test_adds_knowledge_note_to_knowledge_deck_with_fields_and_tags(anki):
    res = card_service.create_knowledge_card(req())
    assert res.success and res.note_id == 777 and not res.duplicate
    (note,) = anki["added"]
    assert note["deckName"] == DECK_KNOWLEDGE and note["modelName"] == MODEL_KNOWLEDGE
    assert note["fields"]["질문"] == "2자산 포트폴리오 분산 식의 교차항은?"
    assert note["fields"]["정답"] == "2 w₁ w₂ σ₁₂"
    assert note["fields"]["설명"] == "교차항 계수 2를 빠뜨리기 쉽다."
    assert note["fields"]["주제"] == "MIE375 Financial Engineering"
    assert note["fields"]["출처"].endswith("p.12")
    assert note["tags"] == ["learning::mie375"]
    assert note["options"] == {"allowDuplicate": False}


def test_creates_deck_before_adding(anki):
    card_service.create_knowledge_card(req())
    assert anki["deck"] == DECK_KNOWLEDGE
    assert anki["calls"].index("createDeck") < anki["calls"].index("addNote")


def test_duplicate_question_is_reported_not_failed(anki):
    anki["existing"].add("2자산 포트폴리오 분산 식의 교차항은?")
    res = card_service.create_knowledge_card(req())
    assert res.success and res.duplicate and res.note_id is None


@pytest.mark.parametrize("field", ["question", "answer"])
def test_empty_question_or_answer_is_rejected_without_calling_anki(anki, field):
    res = card_service.create_knowledge_card(req(**{field: "   "}))
    assert not res.success and "비어" in res.error
    assert anki["calls"] == []


def test_anki_error_is_returned_as_failure(anki, monkeypatch):
    def broken(action, **params):
        if action == "createDeck":
            return 1
        raise Exception("collection is not available")
    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(broken))
    res = card_service.create_knowledge_card(req())
    assert not res.success and "collection" in res.error


def test_endpoint_maps_results_to_http(anki):
    from server import app
    client = TestClient(app)
    ok = client.post("/api/cards/knowledge", json={"question": "Q1", "answer": "A1"})
    assert ok.status_code == 200 and ok.json()["note_id"] == 777
    anki["existing"].add("Q1")
    dup = client.post("/api/cards/knowledge", json={"question": "Q1", "answer": "A1"})
    assert dup.status_code == 200 and dup.json()["duplicate"] is True
    bad = client.post("/api/cards/knowledge", json={"question": "", "answer": "A"})
    assert bad.status_code == 400
