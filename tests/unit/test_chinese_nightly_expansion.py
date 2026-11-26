"""중국어 밤 정리 확장: 빈 필드 보강(Chinese Vocabulary/Sentence), Chirp3-HD 오디오, nightly 쿼리."""
from core import completer as completer_mod
from integrations import audio as audio_mod
from integrations import nightly_maintenance as nm
from integrations.anki_connect import AnkiConnector


def test_nightly_queries_include_chinese_models():
    assert 'note:"Chinese Vocabulary"' in nm.QUERIES["fields"]
    assert 'note:"Chinese Sentence"' in nm.QUERIES["fields"]
    assert "note:Chinese Vocabulary" in nm.QUERIES["audio"]
    assert "note:Chinese Sentence" in nm.QUERIES["audio"]


def test_universal_field_completion_fills_chinese_vocab_and_sentence(monkeypatch):
    zh_vocab = {
        "noteId": 101,
        "modelName": "Chinese Vocabulary",
        "fields": {
            "단어": {"value": "天气"},
            "뜻": {"value": ""},
            "한어병음": {"value": ""},
            "품사": {"value": ""},
            "예문": {"value": ""},
            "사진": {"value": ""},
            "소리": {"value": ""},
        },
    }
    zh_sent = {
        "noteId": 102,
        "modelName": "Chinese Sentence",
        "fields": {
            "문장": {"value": "今天天气很好。"},
            "뜻": {"value": ""},
            "한어병음": {"value": ""},
            "소리": {"value": ""},
        },
    }
    store = {"Chinese Vocabulary": [zh_vocab], "Chinese Sentence": [zh_sent]}
    updates = []

    def fake_find(cls, q):
        for model, ns in store.items():
            if f'note:"{model}"' in q:
                return [n["noteId"] for n in ns]
        return []

    def fake_info(cls, ids):
        return [n for ns in store.values() for n in ns if n["noteId"] in ids]

    monkeypatch.setattr(AnkiConnector, "find_notes", classmethod(fake_find))
    monkeypatch.setattr(AnkiConnector, "get_notes_info", classmethod(fake_info))
    monkeypatch.setattr(AnkiConnector, "update_note_fields", classmethod(lambda cls, nid, f: updates.append((nid, f))))

    class FakeCompleter:
        def __init__(self, pbar=None, **kw):
            pass

        def complete_fields_batch(self, model, notes):
            out = {}
            for n in notes:
                if model == "Chinese Vocabulary":
                    out[n["id"]] = {"뜻": "날씨", "한어병음": "tiānqì", "품사": "명사", "예문": "今天天气很好。 (jīntiān tiānqì hěn hǎo. / 오늘 날씨가 좋다.)"}
                elif model == "Chinese Sentence":
                    out[n["id"]] = {"뜻": "오늘 날씨가 매우 좋다.", "한어병음": "Jīntiān tiānqì hěn hǎo."}
            return out

    monkeypatch.setattr(completer_mod, "NoteCompleter", FakeCompleter)

    completer_mod.run_universal_field_completion()
    by_id = dict(updates)
    assert 101 in by_id and by_id[101]["한어병음"] == "tiānqì" and by_id[101]["뜻"] == "날씨"
    assert 102 in by_id and by_id[102]["한어병음"] == "Jīntiān tiānqì hěn hǎo."


def test_audio_addition_uses_chinese_chirp_without_gtts_fallback(monkeypatch):
    notes = [
        {
            "noteId": 201,
            "modelName": "Chinese Vocabulary",
            "fields": {"단어": {"value": "天气"}, "소리": {"value": ""}},
        },
        {
            "noteId": 202,
            "modelName": "Chinese Sentence",
            "fields": {"문장": {"value": "今天天气很好。"}, "소리": {"value": ""}},
        },
    ]
    updates = []
    zh_calls = []
    gtts_calls = []

    monkeypatch.setattr(AnkiConnector, "find_notes", classmethod(lambda cls, query="": [201, 202]))
    monkeypatch.setattr(AnkiConnector, "get_notes_info", classmethod(lambda cls, ids: notes))
    monkeypatch.setattr(AnkiConnector, "update_note_fields", classmethod(lambda cls, nid, f: updates.append((nid, f))))
    monkeypatch.setattr(audio_mod.texttospeech, "TextToSpeechClient", lambda: object())
    monkeypatch.setattr(
        audio_mod.AnkiTTSFiller,
        "generate_chinese_tts",
        classmethod(lambda cls, client, text, pbar=None: (zh_calls.append(text) or f"[sound:zh_{len(zh_calls)}.mp3]", "cmn-CN-Chirp3-HD-Charon")),
    )
    monkeypatch.setattr(
        audio_mod.AnkiTTSFiller,
        "generate_gtts",
        classmethod(lambda cls, text, pbar=None: (gtts_calls.append(text) or "[sound:gtts.mp3]", "gTTS")),
    )

    audio_mod.AnkiTTSFiller.run_audio_addition()
    assert set(zh_calls) == {"天气", "今天天气很好。"}
    assert gtts_calls == []
    assert {nid for nid, _ in updates} == {201, 202}
