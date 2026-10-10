"""Schemas describing background job state shared by every long-running action."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

LogLevel = Literal["info", "success", "warn", "error"]
JobStatus = Literal["idle", "running", "waiting_selection", "success", "error", "cancelled"]


class LogEntry(BaseModel):
    time: str
    message: str
    level: LogLevel = "info"
    progress: int | None = None


class Candidates(BaseModel):
    sentences: list[str] = Field(default_factory=list)
    vocab: list[dict[str, str]] = Field(default_factory=list)


class JobState(BaseModel):
    is_running: bool = False
    source: str = ""
    progress: int = 0
    current_step: str = "대기 중"
    status: JobStatus = "idle"
    logs: list[LogEntry] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    candidates: Candidates = Field(default_factory=Candidates)


class ActionResult(BaseModel):
    status: Literal["success", "error"]
    message: str = ""
