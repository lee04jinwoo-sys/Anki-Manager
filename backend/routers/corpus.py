import logging
from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas.corpus import (
    CollocationResponse,
    PromoteChunkRequest,
    PromoteChunkResponse,
    CorpusAuditStatsResponse
)
from backend.services.corpus_service import CorpusService

logger = logging.getLogger("CorpusRouter")
router = APIRouter(prefix="/api/corpus", tags=["Corpus & Collocations"])


@router.get("/audit-stats", response_model=CorpusAuditStatsResponse)
def get_corpus_audit_stats() -> CorpusAuditStatsResponse:
    """단어 덱 16,000장 전수 빈도 티어 통계 및 낭비 리치 현황 조회"""
    return CorpusService.get_audit_stats()


@router.get("/collocations", response_model=CollocationResponse)
def get_collocations(word: str = Query(..., description="조회할 단어")) -> CollocationResponse:
    """단어의 코퍼스 랭킹 및 고빈도 연어(Collocation)/청크 후보 3~4개 추천"""
    if not word.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Word query parameter cannot be empty"
        )
    try:
        return CorpusService.get_collocations(word.strip())
    except Exception as e:
        logger.error(f"Error fetching collocations for '{word}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/promote-chunk", response_model=PromoteChunkResponse)
def promote_chunk(req: PromoteChunkRequest) -> PromoteChunkResponse:
    """리치 단어를 선택된 고빈도 청크로 1-클릭 승격 (카드 리셋, Ease 250% 복원, 예문 덱 적재)"""
    res = CorpusService.promote_chunk(req)
    if not res.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.error or "Failed to promote chunk"
        )
    return res
