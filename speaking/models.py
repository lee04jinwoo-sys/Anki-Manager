"""Pydantic v2 data models for the speaking coach subsystem."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

TrackName = Literal["daily", "interview", "ielts"]
StepName = Literal["warmup_1", "warmup_2", "main_pass1", "main_pass2", "followup", "completed", "cancelled"]
CardKind = Literal["sentence", "vocab", "grammar"]


class Topic(BaseModel):
    id: str
    track: TrackName
    title: str
    prompt: str
    bullets: List[str] = Field(default_factory=list)


class SpeakingMetrics(BaseModel):
    duration_sec: float = 0.0
    word_count: int = 0
    wpm: float = 0.0
    filler_count: int = 0
    long_pause_count: int = 0
    max_pause_sec: float = 0.0


class TranscriptionResult(BaseModel):
    transcript: str
    metrics: SpeakingMetrics


class CardCandidate(BaseModel):
    kind: CardKind
    text: str
    translation: str = ""
    reason: str = ""
    # grammar 전용 (선택)
    answer: str = ""
    distractors: List[str] = Field(default_factory=list)


class CoachFeedback(BaseModel):
    summary: str
    score: Optional[float] = None
    corrections: List[str] = Field(default_factory=list)
    native_model: str = ""
    followup_question: Optional[str] = None
    card_candidates: List[CardCandidate] = Field(default_factory=list)


class SessionState(BaseModel):
    id: int
    session_date: str
    track: str
    topic_id: str
    topic_prompt: str
    warmup_prompts: List[str] = Field(default_factory=list)
    mission_vocab: List[str] = Field(default_factory=list)
    step: StepName
    status: Literal["active", "completed", "cancelled"]
    followup_question: Optional[str] = None
