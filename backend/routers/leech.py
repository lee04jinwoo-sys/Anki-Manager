"""Leech 일괄 처리 (다시 학습 / 초기화 / 예문 추가). 청크 승격은 /api/corpus 에서 개별로."""
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.schemas.jobs import ActionResult
from backend.services import leech_service
from backend.services.jobs import jobs


class LeechActionItem(BaseModel):
    note_id: int
    word: str
    meaning: str = ""
    action: leech_service.Action


class LeechApplyRequest(BaseModel):
    items: List[LeechActionItem] = Field(min_length=1)


router = APIRouter(prefix="/api/leech", tags=["leech"])


@router.post("/apply")
def apply_leech_actions(req: LeechApplyRequest) -> ActionResult:
    items = [i.model_dump() for i in req.items]

    def run() -> None:
        summary = leech_service.apply_actions(
            items,
            emit=lambda msg, progress=None: jobs.emit(msg, progress=progress),
            check_cancel=jobs.raise_if_cancelled,
        )
        labels = leech_service.ACTION_LABELS
        parts = [f"{labels[k]} {summary[k]}" for k in ("review_today", "reset", "examples", "skip") if summary[k]]
        jobs.emit("완료: " + " · ".join(parts) + (f" (새 문장 {summary['sentences_created']}개)" if summary["examples"] else ""), progress=100)

    return jobs.start("Leech 처리", run, success_message="Leech 처리가 끝났습니다.")
