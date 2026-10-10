"""agent_bridge: 카드 추가 요청이 컬렉션 전체 중복 정리를 일으키면 안 되고, AI 보강은 빈 필드만 채운다."""
import pytest

import agent_bridge
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from utils import cleaner, organizer


@pytest.fixture
def env(monkeypatch):
    added, calls = [], []

    class FakeCompleter:
        def complete_fields(self, model, main_val, fields, missing):
            return {"문장": "AI가 바꾼 문장", "해설": "번역", "unknown": "x"}

    monkeypatch.setattr(agent_bridge, "NoteCompleter", FakeCompleter)
    monkeypatch.setattr(agent_bridge, "setup_nltk", lambda: None)
    monkeypatch.setattr(AnkiConnector, "add_note", classmethod(lambda cls, deck, model, fields, **k: added.append((model, dict(fields))) or 1))
    monkeypatch.setattr(AnkiTTSFiller, "run_audio_addition", classmethod(lambda cls, *a, **k: calls.append("audio")))
    monkeypatch.setattr(organizer, "run_organizer", lambda *a, **k: calls.append("organizer"))
    monkeypatch.setattr(cleaner, "clean_duplicates", lambda *a, **k: calls.append("duplicates"))
    return added, calls


def test_adding_a_card_does_not_run_collection_wide_duplicate_cleanup(env):
    added, calls = env
    agent_bridge.bridge_add_items([{"model": "Sentence", "fields": {"문장": "I am a student."}}])
    assert len(added) == 1
    assert "duplicates" not in calls
    assert "audio" in calls


def test_enrichment_does_not_overwrite_given_fields(env):
    added, _ = env
    agent_bridge.bridge_add_items([{"model": "Sentence", "fields": {"문장": "I am a student."}}])
    model, fields = added[0]
    assert fields["문장"] == "I am a student."
    assert fields["해설"] == "번역"
    assert "unknown" not in fields
