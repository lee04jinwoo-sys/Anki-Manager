import logging
from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas.corpus import (
    CollocationResponse,
    PromoteBatchRequest,
    PromoteChunkRequest,
    PromoteChunkResponse,
    CorpusAuditStatsResponse
)
from backend.schemas.jobs import ActionResult
from backend.services.corpus_service import CorpusService
from backend.services.jobs import jobs

logger = logging.getLogger("CorpusRouter")
router = APIRouter(prefix="/api/corpus", tags=["Corpus & Collocations"])


@router.get("/audit-stats", response_model=CorpusAuditStatsResponse)
def get_corpus_audit_stats() -> CorpusAuditStatsResponse:
    """단어 덱 16,000장 전수 빈도 티어 통계 및 낭비 리치 현황 조회"""
    return CorpusService.get_audit_stats()


@router.get("/collocations", response_model=CollocationResponse)
def get_collocations(
    word: str = Query(..., description="조회할 단어"),
    refresh: bool = Query(False, description="저장된 후보를 무시하고 새로 생성"),
) -> CollocationResponse:
    """단어의 코퍼스 랭킹 및 고빈도 연어(Collocation)/청크 후보 3~4개 추천"""
    if not word.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Word query parameter cannot be empty"
        )
    try:
        return CorpusService.get_collocations(word.strip(), refresh=refresh)
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


@router.post("/promote-batch")
def promote_batch(req: PromoteBatchRequest) -> ActionResult:
    """여러 단어를 한 번에 승격 (백그라운드 작업). 단어마다 승격 전 상태가 백업되고, 단어 사이에서 취소할 수 있다."""
    items = list(req.items)

    def run() -> None:
        ok, failed = 0, []
        for i, item in enumerate(items):
            jobs.raise_if_cancelled()
            jobs.emit(f"승격 중 ({i + 1}/{len(items)}): {item.new_chunk}", progress=10 + int(85 * i / len(items)))
            res = CorpusService.promote_chunk(item)
            if res.success:
                ok += 1
            else:
                failed.append(f"{item.new_chunk}: {res.error}")
                jobs.emit(f"⚠ 승격 실패 — {item.new_chunk}: {res.error}", level="warn")
        jobs.emit(f"청크 승격 완료: 성공 {ok} · 실패 {len(failed)}", progress=100)

    return jobs.start("청크 일괄 승격", run, success_message="청크 승격 작업이 끝났습니다.")
