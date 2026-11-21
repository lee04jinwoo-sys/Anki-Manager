"""Speech-to-text (Groq Whisper), quantitative fluency metrics, and Chirp 3 HD TTS audio bytes."""
from __future__ import annotations

import datetime as dt
import logging
import os
import random
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import requests

from config import VOICE_LIST
from speaking.models import SpeakingMetrics, TranscriptionResult

logger = logging.getLogger("speaking.speech")

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_WHISPER_MODEL = "whisper-large-v3-turbo"
LONG_PAUSE_THRESHOLD_SEC = 1.5
# Groq Whisper word timestamp는 단어 앞 침묵을 다음 단어의 [start, end] 구간에 흡수하는 경향이 있어
# 단일 단어 발화 상한(0.6초)을 초과한 잔여 구간도 침묵으로 추정한다.
MAX_NORMAL_WORD_SPAN_SEC = 0.6
DEFAULT_AUDIO_DIR = Path(os.getenv("SPEAKING_AUDIO_DIR", str(Path.home() / "speaking_audio")))


def save_audio_file(
    audio_bytes: bytes,
    session_date: str,
    label: str,
    filename: str = "voice.ogg",
    base_dir: Optional[Path] = None,
    now: Optional[dt.datetime] = None,
) -> Path:
    """사용자 녹음 파일을 data/ 백업과 분리된 폴더(YYYY-MM-DD/<label>_<HHMMSS>.ogg)에 영구 보관한다."""
    root = Path(base_dir) if base_dir is not None else DEFAULT_AUDIO_DIR
    day_dir = root / session_date
    day_dir.mkdir(parents=True, exist_ok=True)

    safe_label = re.sub(r"[^A-Za-z0-9_-]", "_", label or "voice")
    ext = Path(filename or "voice.ogg").suffix.lower() or ".ogg"
    if not ext.startswith("."):
        ext = f".{ext}"

    stamp = (now or dt.datetime.now()).strftime("%H%M%S")
    dest = day_dir / f"{safe_label}_{stamp}{ext}"
    counter = 1
    while dest.exists():
        dest = day_dir / f"{safe_label}_{stamp}_{counter}{ext}"
        counter += 1
    dest.write_bytes(audio_bytes)
    return dest

_SINGLE_FILLER_RE = re.compile(r"\b(?:um|uh|erm|er|ah|hmm|like|basically|actually)\b", re.IGNORECASE)
_MULTI_FILLER_RE = re.compile(r"\b(?:you know|i mean|kind of|sort of)\b", re.IGNORECASE)


def count_fillers(transcript: str) -> int:
    if not transcript:
        return 0
    return len(_SINGLE_FILLER_RE.findall(transcript)) + len(_MULTI_FILLER_RE.findall(transcript))


def analyze_transcript_metrics(
    transcript: str,
    words: Sequence[Dict[str, Any]],
    duration_sec: float,
    pause_threshold_sec: float = LONG_PAUSE_THRESHOLD_SEC,
) -> SpeakingMetrics:
    """Whisper 단어 타임스탬프와 전사문에서 WPM, 필러 횟수, 1.5초 이상 침묵을 실측한다."""
    clean_tokens = [tok for tok in re.findall(r"[A-Za-z0-9']+", transcript or "") if tok]
    word_count = len(clean_tokens)

    effective_duration = float(duration_sec or 0.0)
    if effective_duration <= 0.0 and words:
        last_end = words[-1].get("end")
        if last_end is not None:
            effective_duration = float(last_end)

    wpm = round((word_count / effective_duration) * 60.0, 1) if effective_duration > 0 else 0.0
    filler_count = count_fillers(transcript)

    long_pause_count = 0
    max_pause_sec = 0.0
    prev_end: Optional[float] = None
    for item in words:
        start = item.get("start")
        end = item.get("end")
        if start is None or end is None:
            continue
        start_f = float(start)
        end_f = float(end)
        gap = max(0.0, start_f - prev_end) if prev_end is not None else 0.0
        absorbed = max(0.0, (end_f - start_f) - MAX_NORMAL_WORD_SPAN_SEC) if prev_end is not None else 0.0
        effective_pause = max(gap, absorbed)
        if effective_pause > max_pause_sec:
            max_pause_sec = effective_pause
        if effective_pause >= pause_threshold_sec:
            long_pause_count += 1
        prev_end = max(prev_end or 0.0, end_f)

    return SpeakingMetrics(
        duration_sec=round(effective_duration, 1),
        word_count=word_count,
        wpm=wpm,
        filler_count=filler_count,
        long_pause_count=long_pause_count,
        max_pause_sec=round(max_pause_sec, 2),
    )


def _groq_filename(filename: str) -> str:
    """텔레그램 음성은 `.oga`로 오는데 Groq가 거절하므로(내용은 ogg와 동일) `.ogg`로 바꿔 보낸다."""
    path = Path(filename or "voice.ogg")
    if path.suffix.lower() == ".oga":
        return path.with_suffix(".ogg").name
    return path.name


class GroqWhisperClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_WHISPER_MODEL,
        post: Optional[Callable[..., Any]] = None,
        timeout_sec: int = 45,
    ) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "") if api_key is None else api_key
        self.model = model
        self._post = post or requests.post
        self.timeout_sec = timeout_sec

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        language: Optional[str] = "en",
    ) -> TranscriptionResult:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY 환경 변수가 설정되어 있지 않습니다.")

        data: Dict[str, Any] = {
            "model": self.model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "word",
        }
        if language:
            data["language"] = language

        resp = self._post(
            GROQ_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            files={"file": (_groq_filename(filename), audio_bytes, "audio/ogg")},
            data=data,
            timeout=self.timeout_sec,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Groq Whisper HTTP {resp.status_code}: {getattr(resp, 'text', '')[:200]}")

        body = resp.json()
        transcript = (body.get("text") or "").strip()
        duration = float(body.get("duration") or 0.0)
        words: List[Dict[str, Any]] = body.get("words") or []
        metrics = analyze_transcript_metrics(transcript=transcript, words=words, duration_sec=duration)
        return TranscriptionResult(transcript=transcript, metrics=metrics)


def synthesize_coaching_audio(text: str, tts_client: Any = None) -> Optional[bytes]:
    """교정된 원어민 대안 문장을 Telegram voice(OGG_OPUS) 또는 MP3 바이트로 생성한다."""
    clean = (text or "").strip()
    if not clean:
        return None
    try:
        from google.cloud import texttospeech
    except Exception:
        return None

    client = tts_client
    if client is None:
        try:
            client = texttospeech.TextToSpeechClient()
        except Exception as e:
            logger.warning("GCP TTS client unavailable for speaking feedback: %s", e)
            return None

    try:
        voice_name = random.choice(VOICE_LIST)
        lang_code = "-".join(voice_name.split("-")[:2])
        synthesis_input = texttospeech.SynthesisInput(text=clean)
        voice = texttospeech.VoiceSelectionParams(language_code=lang_code, name=voice_name)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
            speaking_rate=1.05,
        )
        resp = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        return bytes(resp.audio_content)
    except Exception as e:
        logger.warning("GCP Chirp3-HD synthesis failed for speaking feedback: %s", e)
        return None
