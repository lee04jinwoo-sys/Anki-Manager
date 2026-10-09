"""Schemas for the unified single-screen dashboard."""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from backend.schemas.jobs import JobState


class DeckCardCount(BaseModel):
    name: str
    display_name: str
    total: int = 0
    new_remaining: int = 0       # 덱에 남아있는 전체 미학습 새 카드 수 (is:new)
    due_today: int = 0           # 오늘 복습 대상 카드 (is:due)
    studied_today: int = 0       # 오늘 복습 완료된 카드 (rated:1)
    due_tomorrow: int = 0        # 내일 만료 예정 카드 (prop:due=1)
    due_7days: int = 0           # 향후 7일 내 만료 예정 카드 (prop:due<=7 prop:due>0)
    learning: int = 0            # 학습 중 카드 (is:learn)
    mature: int = 0              # 성숙 카드 (interval >= 21일)
    young: int = 0               # 젊은 카드 (0 < interval < 21일)
    suspended: int = 0           # 보류 카드 (is:suspended)
    deck_leech_count: int = 0    # 만성 오답 카드 수
    avg_interval_days: float = 0.0    # 평균 복습 주기 (일)
    avg_interval_months: float = 0.0  # 평균 복습 주기 (개월)
    avg_ease: float = 0.0        # 평균 Ease (%)
    total_reps_est: int = 0      # 총 누적 복습 횟수 추정치
    today_retention: float = 0.0      # 금일 복습 정답률 (%)
    retention_30d: float = 0.0        # 최근 30일 복습 정답률 (%)
    mature_retention_30d: float = 0.0 # 최근 30일 성숙 카드 유지율 (%)
    retention_rate: float = 0.0  # 성숙 카드 비율 (Mature Card Ratio, %)


class LeechSummaryItem(BaseModel):
    note_id: int
    card_id: int
    word: str
    meaning: str
    lapses: int
    ease: float
    reps: int


class MaintenanceOverview(BaseModel):
    missing_audio_count: int = 0
    missing_fields_count: int = 0
    total_needs_count: int = 0


class ObsidianInboxSummary(BaseModel):
    vocab_count: int = 0
    sentence_count: int = 0
    total_count: int = 0
    available: bool = False


class DashboardResponse(BaseModel):
    connected: bool
    anki_version: Optional[str] = None
    decks: List[DeckCardCount] = Field(default_factory=list)
    maintenance: MaintenanceOverview = Field(default_factory=MaintenanceOverview)
    leeches: List[LeechSummaryItem] = Field(default_factory=list)
    leech_total_count: int = 0
    obsidian_inbox: ObsidianInboxSummary = Field(default_factory=ObsidianInboxSummary)
    active_job: JobState = Field(default_factory=JobState)
