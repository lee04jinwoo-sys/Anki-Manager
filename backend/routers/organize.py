import threading
from fastapi import APIRouter
from utils.organizer import run_organizer
from integrations.audio import AnkiTTSFiller
from core.completer import run_universal_field_completion
from utils.pos_automator import run_pos_automation
from utils.cluster import run_clustering
from utils.cleaner import clean_duplicates
from integrations.anki_connect import AnkiConnector
from backend.routers.workflow import emit_log, workflow_state

router = APIRouter(prefix="/api/organize", tags=["organize"])

def _run_bg_task(task_name: str, target_fn, success_msg: str):
    if workflow_state["is_running"]:
        return {"status": "error", "message": "이미 다른 작업이 실행 중입니다."}

    workflow_state["is_running"] = True
    workflow_state["source"] = task_name
    workflow_state["progress"] = 15
    workflow_state["status"] = "running"
    workflow_state["logs"] = []
    workflow_state["candidates"] = {"sentences": [], "vocab": []}

    emit_log(f"[{task_name}] 작업 시작...", progress=15, level="info")

    def worker():
        try:
            emit_log(f"[{task_name}] Anki 데이터 분석 및 실행 중...", progress=40, level="info")
            target_fn()
            emit_log(f"✅ {success_msg}", progress=100, level="success")
            workflow_state["status"] = "success"
        except Exception as e:
            emit_log(f"❌ [{task_name}] 오류 발생: {str(e)}", level="error")
            workflow_state["status"] = "error"
        finally:
            workflow_state["is_running"] = False

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return {"status": "success", "message": f"{task_name} 작업을 시작했습니다."}

@router.post("/audio")
def organize_audio():
    return _run_bg_task("누락된 TTS 오디오 생성", AnkiTTSFiller.run_audio_addition, "누락된 TTS 오디오 생성이 완료되었습니다.")

@router.post("/completion")
def organize_completion():
    return _run_bg_task("빈 필드 AI 자동 완성", run_universal_field_completion, "빈 필드 AI 자동 완성이 완료되었습니다.")

@router.post("/pos")
def organize_pos():
    return _run_bg_task("품사 자동 분류", run_pos_automation, "품사 자동 분류가 완료되었습니다.")

@router.post("/cluster")
def organize_cluster():
    return _run_bg_task("AI 유의어 맵 업데이트", lambda: run_clustering(full_recluster=True), "AI 유의어 맵 업데이트가 완료되었습니다.")

@router.post("/organize")
@router.post("/organizer")
def organize_cards():
    return _run_bg_task("카드 규칙별 덱 이동", run_organizer, "카드 규칙별 덱 이동 및 정리가 완료되었습니다.")

@router.post("/duplicates")
def organize_duplicates():
    return _run_bg_task("중복 카드 정리", clean_duplicates, "중복 카드 정리가 완료되었습니다.")

@router.post("/sync")
def organize_sync():
    emit_log("Anki Web 동기화 요청 중...", progress=50, level="info")
    try:
        AnkiConnector.invoke('sync')
        emit_log("✅ Anki Web 동기화 완료!", progress=100, level="success")
        return {"status": "success", "message": "Anki Web 동기화가 완료되었습니다."}
    except Exception as e:
        emit_log(f"❌ 동기화 실패: {str(e)}", level="error")
        return {"status": "error", "message": str(e)}
