"""Audio tags must use the file name AnkiConnect actually stored.

The server Anki (Linux) stores media under a lowercase name and returns it from storeMediaFile;
a tag with the requested mixed-case name then points at no file there (and on phones).
"""
from integrations import audio
from integrations.audio import AnkiTTSFiller


class FakeTTSClient:
    def synthesize_speech(self, **kwargs):
        class R:
            audio_content = b"mp3-bytes"
        return R()


def lowercasing_store(calls):
    def invoke(action, **params):
        calls.append((action, params))
        assert action == "storeMediaFile"
        return params["filename"].lower()
    return invoke


def test_chirp_tag_uses_the_stored_name(monkeypatch):
    calls = []
    monkeypatch.setattr(audio.AnkiConnector, "invoke", staticmethod(lowercasing_store(calls)))
    tag, voice = AnkiTTSFiller.generate_random_tts(FakeTTSClient(), "Hello there.")
    requested = calls[0][1]["filename"]
    assert requested != requested.lower()          # voice names are mixed case
    assert tag == f"[sound:{requested.lower()}]"
    assert voice in requested


def test_gtts_tag_uses_the_stored_name(monkeypatch):
    calls = []
    monkeypatch.setattr(audio.AnkiConnector, "invoke", staticmethod(lambda action, **p: calls.append(p) or "stored_name.mp3"))

    class FakeGTTS:
        def __init__(self, *a, **k):
            pass

        def save(self, path):
            open(path, "wb").write(b"mp3")

    monkeypatch.setattr(audio, "gTTS", FakeGTTS)
    tag, method = AnkiTTSFiller.generate_gtts("hello")
    assert tag == "[sound:stored_name.mp3]"
