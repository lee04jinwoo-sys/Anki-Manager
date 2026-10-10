"""Learning statistics (heatmap, retention, workload forecast, deck composition)."""
import logging

from fastapi import APIRouter, HTTPException

from backend.services import stats_service

logger = logging.getLogger("StatsRouter")
router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
def read_overview():
    try:
        return stats_service.get_overview()
    except Exception as e:
        logger.warning("stats overview failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Anki 통계를 가져오지 못했습니다: {e}")
