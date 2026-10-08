import threading
from fastapi import APIRouter
from utils.design_manager import export_design, import_design, sync_design_from_code
from backend.routers.workflow import emit_log, workflow_state

router = APIRouter(prefix="/api/design", tags=["design"])

def _run_bg_design_task(task_name: str, target_fn, success_msg: str):
    if workflow_state["is_running"]:
        return {"status": "error", "message": "이미 다른 작업이 실행 중입니다."}

    workflow_state["is_running"] = True
    workflow_state["source"] = task_name
    workflow_state["progress"] = 20
    workflow_state["status"] = "running"
    workflow_state["logs"] = []

    emit_log(f"[{task_name}] 디자인 작업 시작...", progress=20, level="info")

    def worker():
        try:
            emit_log(f"[{task_name}] Anki 모델 템플릿 및 CSS 처리 중...", progress=50, level="info")
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

@router.post("/export")
def handle_export_design():
    return _run_bg_design_task("카드 디자인 JSON 백업", export_design, "Anki에서 디자인을 data/design_config.json 파일로 백업했습니다.")

@router.post("/import")
def handle_import_design():
    return _run_bg_design_task("카드 디자인 JSON 복원", import_design, "data/design_config.json 파일에서 Anki로 디자인을 복원했습니다.")

@router.post("/sync")
def handle_sync_design():
    return _run_bg_design_task("config.py 디자인 강제 동기화", sync_design_from_code, "config.py 디자인 프리셋을 Anki 모델들에 강제 적용했습니다.")
