"""Organize / Maintenance Router.

Consolidates missing audio, empty fields, and rule-based deck moves
into a unified maintenance workflow via maintenance_service.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.schemas.jobs import ActionResult
from backend.schemas.maintenance import StepInfo, MaintenanceRunRequest
from backend.services import maintenance_service
from backend.services.jobs import jobs
from integrations.anki_connect import AnkiConnector

logger = logging.getLogger("AnkiManagerOrganize")
router = APIRouter(prefix="/api/organize", tags=["organize"])


@router.get("/steps")
def get_available_steps() -> List[StepInfo]:
    """Returns catalog of all available maintenance steps."""
    return maintenance_service.step_catalog()


@router.post("/run")
def run_unified_maintenance(req: Optional[MaintenanceRunRequest] = None) -> ActionResult:
    """Run consolidated maintenance pipeline (fields, audio, deck_move, etc.)."""
    steps = req.steps if req and req.steps else None
    return maintenance_service.start_job(steps)


# Individual step triggers (for granular execution or legacy callers)
@router.post("/audio")
def organize_audio() -> ActionResult:
    return maintenance_service.start_job(["audio"])


@router.post("/completion")
def organize_completion() -> ActionResult:
    return maintenance_service.start_job(["fields"])


@router.post("/pos")
def organize_pos() -> ActionResult:
    return maintenance_service.start_job(["pos"])


@router.post("/organize")
@router.post("/organizer")
def organize_cards() -> ActionResult:
    return maintenance_service.start_job(["deck_move"])


@router.post("/duplicates")
def organize_duplicates() -> ActionResult:
    return maintenance_service.start_job(["duplicates"])


@router.post("/sync")
def organize_sync() -> ActionResult:
    jobs.emit("Anki Web 동기화 요청 중...", progress=50, level="info")
    try:
        AnkiConnector.invoke("sync")
        jobs.emit("Anki Web 동기화 완료", progress=100, level="success")
        return ActionResult(status="success", message="Anki Web 동기화가 완료되었습니다.")
    except Exception as e:
        jobs.emit(f"동기화 실패: {e}", level="error")
        return ActionResult(status="error", message=str(e))
