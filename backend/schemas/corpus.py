from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CollocationCandidate(BaseModel):
    chunk: str = Field(..., description="추천된 고빈도 연어/청크 표현 (예: hoard supplies)")
    meaning: str = Field(..., description="청크의 명확한 한국어 뜻")
    pos: str = Field(default="idiom", description="품사")
    tier: str = Field(..., description="코퍼스 빈도 티어 (freq::tier1_essential 등)")
    rank: int = Field(..., description="코퍼스 랭킹")
    example_1: str = Field(..., description="예문 1")
    trans_1: str = Field(..., description="예문 1 한글 번역")
    example_2: str = Field(..., description="예문 2")
    trans_2: str = Field(..., description="예문 2 한글 번역")
    explanation: str = Field(default="", description="원어민 뉘앙스 및 쓰임새 설명")
    frequency_score: Optional[float] = Field(default=None, description="상대 빈도 지수")


class CollocationResponse(BaseModel):
    original_word: str
    original_rank: int
    original_tier: str
    candidates: List[CollocationCandidate]


class PromoteChunkRequest(BaseModel):
    note_id: int = Field(..., description="승격 대상 Anki Note ID")
    new_chunk: str = Field(..., description="선택된 새 청크 표현")
    meaning: str = Field(..., description="새 한국어 뜻")
    pos: str = Field(default="idiom", description="품사")
    example_1: str = Field(..., description="예문 1")
    trans_1: str = Field(..., description="예문 1 번역")
    example_2: str = Field(..., description="예문 2")
    trans_2: str = Field(..., description="예문 2 번역")
    explanation: str = Field(default="", description="뉘앙스 해설")
    add_sentences_to_deck: bool = Field(default=True, description="문장 덱에 예문 2개 Chirp3-HD로 동시 추가 여부")
    reset_to_new: bool = Field(default=True, description="새 카드로 초기화(lapses=0, reps=0, ease=250%) 여부")


class PromoteChunkResponse(BaseModel):
    success: bool
    note_id: int
    new_chunk: str
    cards_reset_count: int = 0
    sentences_added_count: int = 0
    error: Optional[str] = None


class CorpusAuditStatsResponse(BaseModel):
    total_notes: int
    total_cards: int
    tier_distribution: Dict[str, int]
    waste_leech_count: int
    top_waste_leeches: List[Dict[str, Any]]
    generated_at: Optional[str] = None  # 감사 파일 수정 시각 (재생성 스크립트가 저장소에 없음)
