"""Design Router.

Provides JSON Export and Import for card templates and styles.
Code sync has been removed per renewal guidelines.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter

from backend.schemas.jobs import ActionResult
from backend.services.jobs import jobs
from utils.design_manager import export_design, import_design

logger = logging.getLogger("AnkiManagerDesign")
router = APIRouter(prefix="/api/design", tags=["design"])


@router.post("/export")
def handle_export_design() -> ActionResult:
    """Export current card templates and CSS to data/design_config.json."""
    def run() -> None:
        jobs.emit("카드 템플릿 및 스타일 읽는 중...", progress=30)
        export_design()
        jobs.emit("디자인 JSON 백업 완료", progress=100)

    return jobs.start(
        "디자인 JSON 백업",
        run,
        success_message="카드 디자인을 data/design_config.json 파일로 백업했습니다.",
    )


@router.post("/import")
def handle_import_design() -> ActionResult:
    """Import card templates and CSS from data/design_config.json into Anki."""
    def run() -> None:
        jobs.emit("data/design_config.json 읽는 중...", progress=30)
        import_design()
        jobs.emit("디자인 복원 완료", progress=100)

    return jobs.start(
        "디자인 JSON 복원",
        run,
        success_message="data/design_config.json 파일에서 Anki 모델 디자인을 복원했습니다.",
    )
