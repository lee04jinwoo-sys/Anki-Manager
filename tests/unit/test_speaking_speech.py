"""speaking.speech 단위 테스트: Whisper 단어 타임스탬프 기반 WPM·필러·침묵 실측 + Groq STT."""
import pytest

from speaking.speech import (
    GroqWhisperClient,
    analyze_transcript_metrics,
    save_audio_file,
    synthesize_coaching_audio,
)


def test_analyze_transcript_metrics_computes_wpm_fillers_and_long_pauses():
    words = [
        {"word": "So", "start": 0.0, "end": 0.3},
        {"word": "um", "start": 0.4, "end": 0.7},
        {"word": "I", "start": 2.5, "end": 2.7},         # 1.8s 침묵 (>= 1.5s)
        {"word": "think", "start": 2.8, "end": 3.1},
        {"word": "like", "start": 3.2, "end": 3.5},
        {"word": "it", "start": 3.6, "end": 3.8},
        {"word": "you", "start": 3.9, "end": 4.0},
        {"word": "know", "start": 4.1, "end": 4.3},
        {"word": "works", "start": 6.6, "end": 7.0},     # 2.3s 침묵 (>= 1.5s)
        {"word": "well.", "start": 7.1, "end": 7.5},
    ]
    transcript = "So um I think like it you know works well."

    metrics = analyze_transcript_metrics(transcript=transcript, words=words, duration_sec=7.5)

    assert metrics.duration_sec == pytest.approx(7.5)
    assert metrics.word_count == 10
    assert metrics.wpm == pytest.approx(80.0, rel=1e-2)
    # um (1), like (1), you know (1) -> 3
    assert metrics.filler_count == 3
    assert metrics.long_pause_count == 2
    assert metrics.max_pause_sec == pytest.approx(2.3, rel=1e-2)


def test_analyze_transcript_metrics_detects_whisper_absorbed_pause_inside_word_span():
    """실측 Groq Whisper는 단어 사이 침묵을 다음 단어의 start~end 구간에 흡수한다 (예: 'I' 0.94->3.10s)."""
    words = [
        {"word": "So,", "start": 0.08, "end": 0.56},
        {"word": "um,", "start": 0.56, "end": 0.94},
        {"word": "I", "start": 0.94, "end": 3.10},
        {"word": "think", "start": 3.10, "end": 3.36},
        {"word": "this", "start": 3.36, "end": 3.62},
        {"word": "works.", "start": 3.62, "end": 4.52},
    ]
    metrics = analyze_transcript_metrics(
        transcript="So, um, I think this works.",
        words=words,
        duration_sec=4.52,
    )
    assert metrics.long_pause_count == 1
    assert metrics.max_pause_sec >= 1.5


def test_analyze_transcript_metrics_handles_empty_or_no_timestamps():
    metrics = analyze_transcript_metrics(transcript="Hello world today", words=[], duration_sec=3.0)
    assert metrics.word_count == 3
    assert metrics.wpm == pytest.approx(60.0)
    assert metrics.long_pause_count == 0

    empty = analyze_transcript_metrics(transcript="", words=[], duration_sec=0.0)
    assert empty.word_count == 0
    assert empty.wpm == 0.0


def test_groq_whisper_client_parses_verbose_json():
    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "text": "Hello um world.",
                "duration": 4.0,
                "words": [
                    {"word": "Hello", "start": 0.0, "end": 0.5},
                    {"word": "um", "start": 0.6, "end": 0.9},
                    {"word": "world.", "start": 2.8, "end": 3.3},
                ],
            }

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["data"] = data
        return FakeResp()

    client = GroqWhisperClient(api_key="test-key", post=fake_post)
    result = client.transcribe(b"fake-ogg-bytes", filename="voice.ogg")

    assert "audio/transcriptions" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["data"]["model"] == "whisper-large-v3-turbo"
    assert result.transcript == "Hello um world."
    assert result.metrics.filler_count == 1
    assert result.metrics.long_pause_count == 1


def test_groq_whisper_client_raises_without_key():
    client = GroqWhisperClient(api_key="")
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        client.transcribe(b"bytes")


def test_synthesize_coaching_audio_returns_bytes_from_tts_client():
    class FakeTTSResponse:
        audio_content = b"OGG-AUDIO-BYTES"

    class FakeTTSClient:
        def synthesize_speech(self, input, voice, audio_config):
            assert "trade-off" in input.text
            return FakeTTSResponse()

    audio = synthesize_coaching_audio("That trade-off paid off.", tts_client=FakeTTSClient())
    assert audio == b"OGG-AUDIO-BYTES"


def test_save_audio_file_writes_under_date_subdir(tmp_path):
    import datetime as dt

    saved = save_audio_file(
        b"OGG-RAW-BYTES",
        session_date="2026-11-19",
        label="card_101",
        filename="memo.ogg",
        base_dir=tmp_path,
        now=dt.datetime(2026, 11, 19, 9, 15, 30),
    )
    assert saved == tmp_path / "2026-11-19" / "card_101_091530.ogg"
    assert saved.read_bytes() == b"OGG-RAW-BYTES"
