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


# --- 서버 실행 (2026-10-11): stdin 입력, 추가 후 동기화 -------------------------

@pytest.fixture
def synced(monkeypatch):
    calls = []
    from integrations import anki_sync
    monkeypatch.setattr(anki_sync, "sync_and_report", lambda *a, **k: calls.append("sync") or True)
    monkeypatch.setattr(anki_sync, "telegram_notifier", lambda: (lambda text: None))
    return calls


def test_added_cards_trigger_one_sync(env, synced):
    agent_bridge.bridge_add_items([{"model": "Sentence", "fields": {"문장": "I am a student."}},
                                   {"model": "Sentence", "fields": {"문장": "You are a teacher."}}])
    assert synced == ["sync"]


def test_nothing_added_means_no_sync(env, synced):
    agent_bridge.bridge_add_items([{"model": "Sentence", "fields": {"문장": ""}}])
    assert synced == []


def test_main_reads_json_from_stdin(monkeypatch):
    import io
    got = {}
    monkeypatch.setattr(agent_bridge, "bridge_add_items", lambda items, enrich=True: got.update(items=items, enrich=enrich))
    monkeypatch.setattr("sys.stdin", io.StringIO('[{"model": "Vocab", "fields": {"단어": "it\'s \\"quoted\\""}}]'))

    agent_bridge.main(["agent_bridge.py", "-"])

    assert got["items"][0]["fields"]["단어"] == 'it\'s "quoted"'
    assert got["enrich"] is True


def test_main_still_accepts_json_argument_and_enrich_flag(monkeypatch):
    got = {}
    monkeypatch.setattr(agent_bridge, "bridge_add_items", lambda items, enrich=True: got.update(items=items, enrich=enrich))

    agent_bridge.main(["agent_bridge.py", '[{"model": "Sentence", "fields": {"문장": "Hi."}}]', "false"])

    assert got["items"][0]["fields"]["문장"] == "Hi."
    assert got["enrich"] is False
