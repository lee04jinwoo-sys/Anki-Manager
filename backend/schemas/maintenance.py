"""Schemas for the unified note-maintenance feature."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StepId = Literal["fields", "audio", "deck_move", "pos", "duplicates"]

# "노트 정리" 기본 구성: 빈 필드 채우기 -> 오디오 생성 -> 규칙별 덱 이동
DEFAULT_STEPS: list[StepId] = ["fields", "audio", "deck_move"]


class StepInfo(BaseModel):
    id: StepId
    label: str
    description: str
    default: bool


class MaintenanceRunRequest(BaseModel):
    steps: list[StepId] = Field(default_factory=lambda: list(DEFAULT_STEPS), min_length=1)
