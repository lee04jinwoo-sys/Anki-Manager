"""Gemini가 번역을 '해설'이 아닌 이름으로 돌려줘도 문장 카드에 번역이 들어가는지.

2026-10-11 서버 실측: 같은 문장 3회 모두 {'sentence': ..., 'explanation': '...'} 로 왔고,
'해설'만 찾던 코드는 번역 없이 카드를 만들었다.
"""
import pytest

from core import completer as completer_mod
from core.completer import NoteCompleter


@pytest.fixture
def fake_generate(monkeypatch):
    monkeypatch.setattr(completer_mod.genai, "Client", lambda **kw: object())
    holder = {}

    def _generate(self, prompt):
        holder["prompt"] = prompt
        return holder["response"]

    monkeypatch.setattr(NoteCompleter, "_generate", _generate)
    return holder


@pytest.mark.parametrize("key", ["해설", "explanation", "translation", "번역"])
def test_translation_key_variants_become_haeseol(fake_generate, key):
    fake_generate["response"] = {"sentences": [{"sentence": "No way!", key: "말도 안 돼!"}]}

    res = NoteCompleter().enrich_sentences(["No way!"])

    assert res[0]["해설"] == "말도 안 돼!"
    assert res[0]["문장"] == "No way!"


def test_prompt_names_the_haeseol_field(fake_generate):
    fake_generate["response"] = {"sentences": [{"해설": "x"}]}

    NoteCompleter().enrich_sentences(["No way!"])

    assert '"해설"' in fake_generate["prompt"]


def test_sentence_card_gets_translation_from_explanation_key(fake_generate, monkeypatch):
    from backend.schemas.cards import SentenceCreateRequest
    from backend.services import card_service

    fake_generate["response"] = {"sentences": [{"sentence": "No way!", "explanation": "말도 안 돼!"}]}
    added = {}

    def fake_add_note(deck_name, model_name, fields, options=None, tags=None):
        added.update(fields)
        return 42

    monkeypatch.setattr(card_service.AnkiConnector, "add_note", fake_add_note)
    monkeypatch.setattr(card_service, "queue_background_audio", lambda *a, **k: None)
    monkeypatch.setattr(card_service.LinkManager, "index_single_sentence", lambda *a, **k: None)

    res = card_service.create_sentence_card(SentenceCreateRequest(sentence="No way!", generate_audio=False))

    assert res.success
    assert added["해설"] == "말도 안 돼!"
    assert res.data["translation"] == "말도 안 돼!"
