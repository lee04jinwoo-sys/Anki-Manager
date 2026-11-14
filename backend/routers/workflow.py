"""Workflow Router (Async Jobs Status & Cancellation)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter

from backend.schemas.jobs import ActionResult
from backend.services.jobs import jobs

logger = logging.getLogger("AnkiManagerWorkflow")
router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.get("/state")
def get_workflow_state() -> Dict[str, Any]:
    """Returns the current background job state."""
    return jobs.snapshot().model_dump()


@router.post("/cancel")
def cancel_workflow() -> ActionResult:
    """Cancel the currently running background job."""
    return jobs.cancel()


# Helper bridge for other modules calling emit_log / workflow_state
def emit_log(msg: str, progress: Optional[int] = None, level: str = "info") -> None:
    jobs.emit(msg, progress=progress, level=level)  # type: ignore[arg-type]


class _StateProxy(dict):
    def __getitem__(self, key: str) -> Any:
        return jobs.snapshot().model_dump().get(key)

    def get(self, key: str, default: Any = None) -> Any:
        return jobs.snapshot().model_dump().get(key, default)


workflow_state = _StateProxy()
