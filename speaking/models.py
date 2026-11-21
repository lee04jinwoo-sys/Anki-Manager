"""Pydantic v2 data models for the Anki-native speaking coach subsystem."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

EaseRating = Literal[1, 2, 3, 4]
CardKind = Literal["sentence", "vocab", "grammar"]


class DailyQuestion(BaseModel):
    id: str
    category: str
    prompt: str


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


class SpeakingCard(BaseModel):
    card_id: int
    note_id: int
    topic_id: str
    category: str = "Daily"
    title: str = ""
    prompt_text: str
    is_new: bool = False
    reps: int = 0
    interval: int = 0


class CardEvaluation(BaseModel):
    score: float
    recommended_ease: EaseRating = 3
    summary: str
    corrections: List[str] = Field(default_factory=list)
    native_model: str = ""
    card_candidates: List[CardCandidate] = Field(default_factory=list)


class QueueCounts(BaseModel):
    new_count: int = 0
    learn_count: int = 0
    review_count: int = 0
    total_in_deck: int = 0

    @property
    def remaining(self) -> int:
        return self.new_count + self.learn_count + self.review_count
