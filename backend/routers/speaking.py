"""FastAPI router for the v2 Anki-native speaking coach subsystem (/api/speaking/*)."""
from __future__ import annotations

import base64
import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from integrations import anki_sync
from speaking.models import EaseRating
from speaking.service import SpeakingService

logger = logging.getLogger("SpeakingRouter")
router = APIRouter(prefix="/api/speaking", tags=["Speaking Coach"])


class SpeakingVoiceRequest(BaseModel):
    audio_b64: str
    filename: str = "voice.ogg"
    force_debrief: bool = False


class SpeakingRateRequest(BaseModel):
    card_id: int
    ease: EaseRating


class SpeakingActionResponse(BaseModel):
    mode: str = "queue"
    status: str
    date: str = ""
    card_id: Optional[int] = None
    recommended_ease: Optional[int] = None
    show_rating_buttons: bool = False
    counts: Optional[Dict[str, Any]] = None
    message: str
    audio_b64: Optional[str] = None
    candidates: List[Dict[str, Any]] = Field(default_factory=list)


def _sync_anki_background() -> None:
    try:
        notify = anki_sync.telegram_notifier()
    except Exception:
        notify = lambda _msg: None
    threading.Thread(
        target=anki_sync.sync_and_report,
        args=(anki_sync.anki_connect_sync, notify),
        daemon=True,
    ).start()


def get_speaking_service() -> SpeakingService:
    return SpeakingService(on_anki_changed=_sync_anki_background)


def _encode_response(res: Dict[str, Any]) -> SpeakingActionResponse:
    raw_audio = res.get("audio_bytes")
    audio_b64 = base64.b64encode(raw_audio).decode("ascii") if raw_audio else None
    return SpeakingActionResponse(
        mode=res.get("mode", "queue"),
        status=res.get("status", "ok"),
        date=res.get("date", ""),
        card_id=res.get("card_id"),
        recommended_ease=res.get("recommended_ease"),
        show_rating_buttons=bool(res.get("show_rating_buttons", False)),
        counts=res.get("counts"),
        message=res.get("message", ""),
        audio_b64=audio_b64,
        candidates=res.get("candidates") or [],
    )


@router.post("/queue/start", response_model=SpeakingActionResponse)
def start_speaking_queue() -> SpeakingActionResponse:
    res = get_speaking_service().start_or_resume_today()
    return _encode_response(res)


@router.post("/voice", response_model=SpeakingActionResponse)
def submit_voice(req: SpeakingVoiceRequest) -> SpeakingActionResponse:
    try:
        audio_bytes = base64.b64decode(req.audio_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"잘못된 오디오 인코딩: {e}") from e
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="빈 오디오 파일입니다.")

    svc = get_speaking_service()
    try:
        res = svc.submit_voice(
            audio_bytes=audio_bytes,
            filename=req.filename,
            force_debrief=req.force_debrief,
        )
    except Exception as e:
        logger.exception("Speaking voice processing failed")
        raise HTTPException(status_code=500, detail=f"음성 처리 실패: {type(e).__name__}: {e}") from e
    return _encode_response(res)


@router.post("/retry", response_model=SpeakingActionResponse)
def retry_speaking_card() -> SpeakingActionResponse:
    res = get_speaking_service().request_retry()
    return _encode_response(res)


@router.post("/rate", response_model=SpeakingActionResponse)
def rate_speaking_card(req: SpeakingRateRequest) -> SpeakingActionResponse:
    svc = get_speaking_service()
    try:
        res = svc.rate_current_card(card_id=req.card_id, ease=req.ease)
    except Exception as e:
        logger.exception("Speaking rating failed")
        raise HTTPException(status_code=500, detail=f"Anki 평가 실패: {type(e).__name__}: {e}") from e
    return _encode_response(res)


@router.post("/skip", response_model=SpeakingActionResponse)
def skip_speaking_card() -> SpeakingActionResponse:
    res = get_speaking_service().skip_current_card()
    return _encode_response(res)


@router.get("/summary", response_model=SpeakingActionResponse)
def speaking_summary() -> SpeakingActionResponse:
    res = get_speaking_service().get_daily_summary(completed_just_now=False)
    return _encode_response(res)


@router.get("/stats")
def speaking_stats() -> Dict[str, Any]:
    return get_speaking_service().get_stats()


@router.post("/candidates/{candidate_id}/add")
def add_speaking_candidate(candidate_id: int) -> Dict[str, Any]:
    return get_speaking_service().register_candidate(candidate_id)
