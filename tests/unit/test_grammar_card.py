"""문법 카드 게이트웨이 (/api/cards/grammar).

English Grammar 노트: 앞면 템플릿이 문장 속 {{정답}}을 정규식 \\b정답\\b로 찾아 빈칸으로 바꾸고,
보기1~3 + 정답 네 개를 선택지로 보여준다. 정답이 문장에 없거나 여러 번 나오거나,
선택지가 겹치면 카드가 망가지므로 추가하지 않는다.
"""
import pytest

from backend.schemas.cards import GrammarCreateRequest
from backend.services import card_service
from config import DECK_GRAMMAR, MODEL_GRAMMAR
from integrations.anki_connect import AnkiConnector

SENTENCE = "I am looking forward to meeting you."


@pytest.fixture
def anki(monkeypatch):
    state = {"added": [], "queued": [], "indexed": [], "existing": set(), "completer_calls": []}

    def invoke(action, **params):
        if action == "findCards":
            state.setdefault("find_queries", []).append(params["query"])
            return [556] if 'card:"Card 3"' in params["query"] else []
        if action == "changeDeck":
            state.setdefault("moved", []).append((params["cards"], params["deck"]))
            return None
        if action == "addNote":
            note = params["note"]
            if note["fields"]["문장"] in state["existing"]:
                raise Exception("cannot create note because it is a duplicate")
            state["added"].append(note)
            return 555
        raise AssertionError(f"unexpected AnkiConnect call: {action}")

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    monkeypatch.setattr(card_service, "queue_background_audio",
                        lambda nid, text, is_sentence=True: state["queued"].append((nid, text)))
    monkeypatch.setattr(card_service.LinkManager, "index_single_sentence",
                        classmethod(lambda cls, nid, text: state["indexed"].append(nid)))

    fill = {"해설": "만나기를 고대합니다.", "설명": "look forward to의 to는 전치사라 동명사가 옵니다.",
            "보기2": "to meet", "보기3": "met"}

    class FakeCompleter:
        def __init__(self, **kw):
            pass

        def complete_fields_batch(self, model_name, notes):
            (n,) = notes
            state["completer_calls"].append((model_name, n["main"], dict(n["current"]), list(n["missing"])))
            return {str(n["id"]): {k: v for k, v in state.get("fill", fill).items() if k in n["missing"]}}

    monkeypatch.setattr(card_service, "NoteCompleter", FakeCompleter)
    return state


def test_adds_grammar_note_with_learner_mistake_as_option(anki):
    res = card_service.create_grammar_card(GrammarCreateRequest(
        sentence=SENTENCE, answer="meeting", distractors=["meet"]))
    assert res.success and res.note_id == 555 and not res.duplicate
    note = anki["added"][0]
    assert note["deckName"] == DECK_GRAMMAR and note["modelName"] == MODEL_GRAMMAR
    f = note["fields"]
    assert f["문장"] == SENTENCE and f["정답"] == "meeting" and f["보기1"] == "meet"
    assert {f["보기2"], f["보기3"]} == {"to meet", "met"}
    assert f["해설"] and f["설명"]
    # only the missing fields are generated; the learner's mistake is kept as given
    _, main, current, missing = anki["completer_calls"][0]
    assert main == SENTENCE and current["보기1"] == "meet"
    assert set(missing) == {"해설", "설명", "보기2", "보기3"}
    assert anki["queued"] == [(555, SENTENCE)] and anki["indexed"] == [555]


def test_given_translation_and_explanation_are_not_regenerated(anki):
    card_service.create_grammar_card(GrammarCreateRequest(
        sentence=SENTENCE, answer="meeting", distractors=["meet", "to meet", "met"],
        translation="번역", explanation="설명"))
    assert anki["completer_calls"] == []
    assert anki["added"][0]["fields"]["해설"] == "번역"


@pytest.mark.parametrize("answer", ["meet you soon", "eting", ""])
def test_rejects_answer_not_found_as_a_whole_phrase(anki, answer):
    res = card_service.create_grammar_card(GrammarCreateRequest(sentence=SENTENCE, answer=answer, distractors=["x"]))
    assert not res.success and res.error
    assert anki["added"] == []


def test_rejects_answer_that_appears_twice(anki):
    res = card_service.create_grammar_card(GrammarCreateRequest(
        sentence="The cat saw the dog.", answer="the", distractors=["a"]))
    assert not res.success and "한 번" in res.error
    assert anki["added"] == []


def test_rejects_overlapping_options(anki):
    anki["fill"] = {"해설": "t", "설명": "e", "보기2": "Meeting", "보기3": "met"}  # 보기2 == 정답
    res = card_service.create_grammar_card(GrammarCreateRequest(
        sentence=SENTENCE, answer="meeting", distractors=["meet"]))
    assert not res.success and "선택지" in res.error
    assert anki["added"] == []


def test_distractor_equal_to_answer_is_dropped(anki):
    card_service.create_grammar_card(GrammarCreateRequest(
        sentence=SENTENCE, answer="meeting", distractors=["Meeting", "meet"]))
    f = anki["added"][0]["fields"]
    assert f["보기1"] == "meet"


def test_duplicate_sentence(anki):
    anki["existing"].add(SENTENCE)
    res = card_service.create_grammar_card(GrammarCreateRequest(
        sentence=SENTENCE, answer="meeting", distractors=["meet"]))
    assert res.success and res.duplicate
    assert anki["queued"] == []


def test_cards_go_to_their_configured_decks_right_away(anki):
    # English Grammar: Card 1 -> Grammar deck, Card 3 -> Sentence deck (config deck_assignment).
    # addNote puts every card in one deck; the organizer used to fix it only when run by hand.
    card_service.create_grammar_card(GrammarCreateRequest(sentence=SENTENCE, answer="meeting", distractors=["meet"]))
    assert anki["moved"] == [([556], "1. Language::1.1. English::Sentence")]
    assert all("nid:555" in q for q in anki["find_queries"])


# --- entry cleanup (2026-11-24): HTML left over from editors and option case that gives the answer away ---

import json
import re
from pathlib import Path

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "grammar_defects_20261124.json").read_text())["cards"]


def _no_html(text):
    return not re.search(r"<[a-z/][^>]*>|&nbsp;", text, flags=re.I)


def test_html_is_stripped_from_sentence_answer_and_options(anki):
    res = card_service.create_grammar_card(GrammarCreateRequest(
        sentence="<div>I am&nbsp;looking forward to meeting&nbsp;you.</div>", answer="meeting<br>",
        distractors=["meet<br>", "to&nbsp;meet", "met"], translation="번역", explanation="설명"))
    assert res.success
    f = anki["added"][0]["fields"]
    assert f["문장"] == SENTENCE and f["정답"] == "meeting"
    assert [f["보기1"], f["보기2"], f["보기3"]] == ["meet", "to meet", "met"]


def test_generated_options_are_cleaned_too(anki):
    anki["fill"] = {"해설": "번역", "설명": "설명", "보기2": "to meet<br>", "보기3": "met&nbsp;"}
    card_service.create_grammar_card(GrammarCreateRequest(sentence=SENTENCE, answer="meeting", distractors=["meet"]))
    f = anki["added"][0]["fields"]
    assert {f["보기2"], f["보기3"]} == {"to meet", "met"}


def test_options_are_capitalized_like_an_answer_at_sentence_start(anki):
    card_service.create_grammar_card(GrammarCreateRequest(
        sentence="The sky is getting dark.", answer="The", distractors=["a", "an", "-"],
        translation="번역", explanation="설명"))
    f = anki["added"][0]["fields"]
    assert [f["보기1"], f["보기2"], f["보기3"]] == ["A", "An", "-"]


def test_options_are_lowercased_like_an_answer_mid_sentence(anki):
    card_service.create_grammar_card(GrammarCreateRequest(
        sentence="She has a dog at home.", answer="a", distractors=["The", "An", "-"],
        translation="번역", explanation="설명"))
    f = anki["added"][0]["fields"]
    assert [f["보기1"], f["보기2"], f["보기3"]] == ["the", "an", "-"]


def test_pronoun_i_keeps_its_capital(anki):
    card_service.create_grammar_card(GrammarCreateRequest(
        sentence="She thinks that we are right.", answer="we", distractors=["I", "us", "our"],
        translation="번역", explanation="설명"))
    assert anki["added"][0]["fields"]["보기1"] == "I"


@pytest.mark.parametrize("card", FIXTURE, ids=lambda c: f'{c["note_id"]}-{c["expect"]}')
def test_real_defective_cards_from_the_deck(anki, card):
    """Cards that were broken in the deck: double blanks and duplicate options are refused, HTML is cleaned."""
    res = card_service.create_grammar_card(GrammarCreateRequest(
        sentence=card["sentence"], answer=card["answer"], distractors=card["distractors"],
        translation=card["translation"], explanation=card["explanation"], auto_enrich=False))
    if card["expect"] == "reject":
        assert not res.success and not anki["added"], card["why"]
    else:
        assert res.success, res.error
        f = anki["added"][0]["fields"]
        assert all(_no_html(f[k]) for k in ["문장", "정답", "보기1", "보기2", "보기3"]), f
