from fastapi import APIRouter
from integrations.anki_connect import AnkiConnector

router = APIRouter(prefix="/api/status", tags=["status"])

@router.get("/anki")
def get_anki_status():
    try:
        version = AnkiConnector.invoke("version")
        return {"status": "success", "connected": True, "version": version}
    except Exception as e:
        return {"status": "error", "connected": False, "message": str(e)}
