"""Workflow Router (Obsidian Inbox Import & Async Jobs Status)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.schemas.importer import ObsidianCommitRequest, VocabItem
from backend.schemas.jobs import ActionResult
from backend.services import importer_service
from backend.services.jobs import jobs

logger = logging.getLogger("AnkiManagerWorkflow")
router = APIRouter(prefix="/api/workflow", tags=["workflow"])


class LegacyExtractRequest(BaseModel):
    source: str = "obsidian"
    input_data: str = ""


class LegacyCommitRequest(BaseModel):
    source: str = "obsidian"
    meta: Optional[Dict[str, Any]] = None
    selected_sentences: List[str] = Field(default_factory=list)
    selected_vocab: List[Dict[str, Any]] = Field(default_factory=list)


@router.get("/state")
def get_workflow_state() -> Dict[str, Any]:
    """Returns the current background job state."""
    return jobs.snapshot().model_dump()


@router.post("/extract")
def extract_workflow(req: Optional[LegacyExtractRequest] = None) -> ActionResult:
    """Trigger extraction (Obsidian Inbox)."""
    return importer_service.start_extract()


@router.post("/commit")
def commit_workflow(req: LegacyCommitRequest) -> ActionResult:
    """Commit selected sentences & vocabulary from Obsidian Inbox."""
    typed_vocab: list[VocabItem] = []
    for item in req.selected_vocab:
        typed_vocab.append(
            VocabItem(
                word=str(item.get("단어", "")),
                meaning=str(item.get("뜻", "")),
            )
        )
    commit_req = ObsidianCommitRequest(
        selected_sentences=req.selected_sentences,
        selected_vocab=typed_vocab,
    )
    return importer_service.start_commit(commit_req)


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
