"""Dashboard Router.

Connection state, maintenance backlog and the active job.
Learning statistics live in /api/stats/overview.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from backend.schemas.dashboard import (
    DashboardResponse,
    MaintenanceOverview,
)
from backend.services.jobs import jobs
from config import MODEL_VOCAB
from integrations.anki_connect import AnkiConnector

logger = logging.getLogger("AnkiManagerDashboard")
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("", response_model=DashboardResponse)
@router.get("/", response_model=DashboardResponse)
def get_dashboard_summary() -> DashboardResponse:
    # 1. Anki 연결 상태 확인
    try:
        anki_version = str(AnkiConnector.invoke("version"))
    except Exception as e:
        logger.warning("Anki 연결 실패: %s", e)
        return DashboardResponse(
            connected=False,
            active_job=jobs.snapshot(),
        )

    # 2. 유지보수 대기 카드 카운트 (오디오 누락, 의미 누락)
    missing_audio = 0
    missing_fields = 0
    try:
        audio_ids = AnkiConnector.find_notes(f'note:"{MODEL_VOCAB}" 소리:')
        missing_audio = len(audio_ids)
    except Exception as e:
        logger.debug("오디오 누락 조회 실패: %s", e)

    try:
        field_ids = AnkiConnector.find_notes(f'note:"{MODEL_VOCAB}" "뜻:"')
        missing_fields = len(field_ids)
    except Exception as e:
        logger.debug("뜻 누락 조회 실패: %s", e)

    maintenance = MaintenanceOverview(
        missing_audio_count=missing_audio,
        missing_fields_count=missing_fields,
        total_needs_count=missing_audio + missing_fields,
    )

    return DashboardResponse(
        connected=True,
        anki_version=anki_version,
        maintenance=maintenance,
        active_job=jobs.snapshot(),
    )
