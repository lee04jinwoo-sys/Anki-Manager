from fastapi import APIRouter
from utils.stats import get_deck_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])

@router.get("/")
def read_stats():
    # fast_mode=True to load stats quickly for dashboard
    stats = get_deck_stats(fast_mode=True)
    if stats is None:
        return {"status": "error", "message": "Anki is offline"}
    return {"status": "success", "data": stats}
