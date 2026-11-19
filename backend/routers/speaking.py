"""FastAPI router for the speaking coach subsystem (/api/speaking/*)."""
from __future__ import annotations

import base64
import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from integrations import anki_sync
from speaking.models import TrackName
from speaking.service import SpeakingService

logger = logging.getLogger("SpeakingRouter")
router = APIRouter(prefix="/api/speaking", tags=["Speaking Coach"])


class SpeakingStartRequest(BaseModel):
    track: Optional[TrackName] = None


class SpeakingVoiceRequest(BaseModel):
    audio_b64: str
    filename: str = "voice.ogg"
    force_debrief: bool = False


class SpeakingActionResponse(BaseModel):
    mode: str = "session"
    session_id: Optional[int] = None
    step: str
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
        mode=res.get("mode", "session"),
        session_id=res.get("session_id"),
        step=res.get("step", "unknown"),
        message=res.get("message", ""),
        audio_b64=audio_b64,
        candidates=res.get("candidates") or [],
    )


@router.post("/start", response_model=SpeakingActionResponse)
def start_speaking(req: SpeakingStartRequest) -> SpeakingActionResponse:
    svc = get_speaking_service()
    res = svc.start_session(track=req.track)
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
        res = svc.handle_voice(
            audio_bytes=audio_bytes,
            filename=req.filename,
            force_debrief=req.force_debrief,
        )
    except Exception as e:
        logger.exception("Speaking voice processing failed")
        raise HTTPException(status_code=500, detail=f"음성 처리 실패: {type(e).__name__}: {e}") from e
    return _encode_response(res)


@router.post("/cancel")
def cancel_speaking() -> Dict[str, Any]:
    return get_speaking_service().cancel_session()


@router.get("/stats")
def speaking_stats() -> Dict[str, Any]:
    return get_speaking_service().get_stats()


@router.post("/candidates/{candidate_id}/add")
def add_speaking_candidate(candidate_id: int) -> Dict[str, Any]:
    return get_speaking_service().register_candidate(candidate_id)


@router.post("/tracker/reset")
def reset_speaking_tracker() -> Dict[str, Any]:
    svc = get_speaking_service()
    try:
        res = svc.tracker.reset_daily()
        return {"success": True, **res}
    except Exception as e:
        logger.exception("Speaking tracker reset failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/tracker/done")
def complete_speaking_tracker() -> Dict[str, Any]:
    svc = get_speaking_service()
    try:
        res = svc.tracker.mark_done()
        return {"success": True, **res}
    except Exception as e:
        logger.exception("Speaking tracker mark_done failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
