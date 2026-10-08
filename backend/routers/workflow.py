import time
import threading
import concurrent.futures
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter

from core.generator import generate_situation_content
from core.selector import run_sentence_selection, run_vocabulary_selection
from core.completer import run_note_completion
from collectors.youtube import YouTubeFetcher
from collectors.obsidian import ObsidianManager
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from utils.organizer import run_organizer
from utils.cluster import run_clustering
from config import MODEL_VOCAB

router = APIRouter(prefix="/api/workflow", tags=["workflow"])

class WorkflowExtractRequest(BaseModel):
    source: str
    input_data: str = ""

class WorkflowCommitRequest(BaseModel):
    source: str
    meta: Optional[Dict[str, Any]] = {}
    selected_sentences: List[str] = []
    selected_vocab: List[Dict[str, str]] = [] # [{'단어': '...', '뜻': '...'}]

workflow_state = {
    "is_running": False,
    "source": "",
    "progress": 0,
    "current_step": "대기 중",
    "status": "idle", # "idle", "extracting", "waiting_selection", "committing", "success", "error"
    "logs": [],
    "meta": {},
    "candidates": {
        "sentences": [],
        "vocab": []
    }
}

def emit_log(msg: str, progress: int = None, level: str = "info"):
    timestamp = time.strftime("%H:%M:%S")
    log_entry = {
        "time": timestamp,
        "message": msg,
        "level": level,
        "progress": progress
    }
    workflow_state["logs"].append(log_entry)
    workflow_state["current_step"] = msg
    if progress is not None and progress > 0:
        workflow_state["progress"] = progress
    if level == "error":
        workflow_state["status"] = "error"
    elif level == "success" and workflow_state["status"] != "waiting_selection" and (progress is None or progress >= 100):
        workflow_state["status"] = "success"

@router.get("/status")
def get_workflow_status():
    return workflow_state

@router.post("/clear-logs")
def clear_logs():
    workflow_state["logs"] = []
    workflow_state["progress"] = 0
    workflow_state["status"] = "idle"
    workflow_state["current_step"] = "대기 중"
    workflow_state["candidates"] = {"sentences": [], "vocab": []}
    workflow_state["meta"] = {}
    return {"status": "success"}

@router.post("/extract")
def extract_candidates(req: WorkflowExtractRequest):
    if workflow_state["is_running"]:
        return {"status": "error", "message": "이미 다른 작업이 실행 중입니다."}

    workflow_state["is_running"] = True
    workflow_state["source"] = req.source
    workflow_state["progress"] = 10
    workflow_state["status"] = "extracting"
    workflow_state["logs"] = []
    workflow_state["candidates"] = {"sentences": [], "vocab": []}
    workflow_state["meta"] = {}

    emit_log(f"후보 추출 시작 (소스: {req.source})", progress=10, level="info")

    def run_extract_bg():
        try:
            source = req.source
            input_data = req.input_data
            sentences = []
            vocab = []
            meta = {}

            if source == "youtube":
                emit_log("YouTube 자막 가져오는 중...", progress=20, level="info")
                import re
                v_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", input_data)
                if not v_id_match:
                    emit_log("유효한 YouTube ID를 찾을 수 없습니다.", level="error")
                    return
                
                video_id = v_id_match.group(1)
                res = YouTubeFetcher.fetch_transcript(video_id)
                if not res:
                    emit_log("YouTube 자막을 불러오지 못했습니다.", level="error")
                    return

                raw_sentences = res["sentences"]
                segments = res["segments"]
                meta["video_id"] = video_id
                meta["segments"] = segments

                emit_log(f"자막 로드 완료 ({len(raw_sentences)} 문장). AI 핵심 문장/어휘 선별 중...", progress=50, level="info")
                
                existing_vocab = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
                data = {"source": input_data, "content": " ".join(raw_sentences)}

                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                    fs = ex.submit(run_sentence_selection, data)
                    fv = ex.submit(run_vocabulary_selection, data, existing_vocab)
                    sel_sentences_res, sel_vocab_res = fs.result(), fv.result()

                if sel_sentences_res:
                    sentences = sel_sentences_res.get("sentences", [])
                if sel_vocab_res:
                    vocab = sel_vocab_res.get("vocab", [])

            elif source == "obsidian":
                emit_log("Obsidian Inbox 데이터 로드 중...", progress=30, level="info")
                obsidian_mgr = ObsidianManager()
                data = obsidian_mgr.fetch_inbox_content()
                if not data or (not data["vocab"] and not data["sentences"]):
                    emit_log("가져올 Obsidian 데이터가 없습니다 (Inbox 비어있음).", level="warn")
                    workflow_state["status"] = "idle"
                    return
                sentences = data.get("sentences", [])
                vocab_raw = data.get("vocab", [])
                # Normalize vocab items to dict format {"단어": v, "뜻": ""}
                for v in vocab_raw:
                    if isinstance(v, str):
                        vocab.append({"단어": v, "뜻": ""})
                    elif isinstance(v, dict):
                        vocab.append(v)

            elif source == "situation":
                emit_log(f"상황({input_data}) 기반 AI 학습 컨텐츠 생성 중...", progress=40, level="info")
                gen = generate_situation_content(input_data)
                if not gen:
                    emit_log("상황 컨텐츠 생성 실패", level="error")
                    return
                sentences = gen.get("sentences", [])
                vocab = gen.get("vocab", [])

            elif source == "knowledge":
                emit_log("Knowledge 콘텐츠 로드 중 (YouTube/웹/텍스트)...", progress=30, level="info")
                from collectors.knowledge_fetcher import KnowledgeFetcher
                from core.knowledge_extractor import KnowledgeExtractor
                fetch_res = KnowledgeFetcher.fetch_from_input(input_data)
                if not fetch_res or not fetch_res.get("content"):
                    emit_log("콘텐츠를 가져오지 못했습니다. URL이나 텍스트를 확인해주세요.", level="error")
                    return
                content = fetch_res["content"]
                source_label = fetch_res.get("source", "직접 입력")
                meta["source_label"] = source_label
                emit_log(f"콘텐츠 로드 완료 ({len(content)}자). Gemini AI 고품질 Q&A 카드 추출 중...", progress=60, level="info")
                extractor = KnowledgeExtractor()
                cards = extractor.extract_qa_cards(content, target_count=10, source_label=source_label)
                for c in cards:
                    vocab.append({
                        "단어": f"Q: {c.get('질문', '')}",
                        "뜻": f"A: {c.get('정답', '')} [{c.get('대주제', '')} > {c.get('소주제', '')}]"
                    })

            workflow_state["candidates"] = {
                "sentences": sentences,
                "vocab": vocab
            }
            workflow_state["meta"] = meta
            emit_log(f"후보 추출 완료: 문장 {len(sentences)}개, 단어 {len(vocab)}개 선별됨. 화면에서 선택해주세요.", progress=100, level="info")
            workflow_state["status"] = "waiting_selection"

        except Exception as e:
            emit_log(f"후보 추출 중 오류 발생: {e}", level="error")
            workflow_state["status"] = "error"
        finally:
            workflow_state["is_running"] = False

    threading.Thread(target=run_extract_bg, daemon=True).start()
    return {"status": "success", "message": "후보 추출이 시작되었습니다."}

@router.post("/commit")
def commit_selected(req: WorkflowCommitRequest):
    if workflow_state["is_running"]:
        return {"status": "error", "message": "이미 다른 작업이 실행 중입니다."}

    if not req.selected_sentences and not req.selected_vocab:
        return {"status": "error", "message": "선택된 문장이나 단어가 없습니다."}

    workflow_state["is_running"] = True
    workflow_state["progress"] = 10
    workflow_state["status"] = "committing"
    emit_log(f"선택 항목 Anki 등록 시작 (문장 {len(req.selected_sentences)}개, 단어 {len(req.selected_vocab)}개)", progress=10, level="info")

    def run_commit_bg():
        try:
            if req.source == "knowledge":
                emit_log("Knowledge Q&A 카드를 안키 대주제별 덱에 저장 중...", progress=40, level="info")
                from utils.topic_manager import TopicManager
                from config import MODEL_KNOWLEDGE, DECK_KNOWLEDGE
                anki_notes = []
                created_decks = set()
                for v in req.selected_vocab:
                    q_text = v.get("단어", "").replace("Q:", "").strip()
                    ans_raw = v.get("뜻", "").replace("A:", "").strip()
                    major = "교양"
                    if "[" in ans_raw and "]" in ans_raw:
                        parts = ans_raw.split("[")[-1].split("]")[0].split(">")
                        major = parts[0].strip() if parts else "교양"
                        ans_clean = ans_raw.split("[")[0].strip()
                    else:
                        ans_clean = ans_raw

                    target_deck = TopicManager.get_target_deck_for_major(major, default_deck=DECK_KNOWLEDGE)
                    if target_deck not in created_decks:
                        AnkiConnector.invoke('createDeck', deck=target_deck)
                        created_decks.add(target_deck)

                    anki_notes.append({
                        "deckName": target_deck,
                        "modelName": MODEL_KNOWLEDGE,
                        "fields": {
                            "질문": q_text,
                            "정답": ans_clean,
                            "설명": "",
                            "주제": major,
                            "출처": req.meta.get("source_label", "Web UI") if req.meta else "Web UI"
                        },
                        "options": {"allowDuplicate": False}
                    })
                if anki_notes:
                    AnkiConnector.add_notes(anki_notes)
                emit_log(f"Knowledge Q&A {len(anki_notes)}장 안키 저장 완료!", progress=100, level="success")
                workflow_state["status"] = "success"
                workflow_state["progress"] = 100
                return

            video_id = req.meta.get("video_id") if req.meta else None
            segments = req.meta.get("segments") if req.meta else None

            sel_sentences = {"sentences": req.selected_sentences, "video_id": video_id, "segments": segments}
            sel_vocab = {"vocab": req.selected_vocab, "video_id": video_id, "segments": segments}

            emit_log("AI 상세 보강(뜻, 예문, 품사, 번역) 및 Anki 카드 추가 중...", progress=30, level="info")
            run_note_completion(sel_sentences, sel_vocab)

            if req.source == "obsidian":
                emit_log("Obsidian Inbox 정리 중...", progress=60, level="info")
                obsidian_mgr = ObsidianManager()
                obsidian_mgr.clear_processed_content()

            emit_log("고품질 TTS 오디오 생성 및 추가 중...", progress=75, level="info")
            AnkiTTSFiller.run_audio_addition()

            emit_log("덱 규칙별 카드 자동 정리 중...", progress=90, level="info")
            run_organizer()

            emit_log("AI 유의어 맵 클러스터링 동기화 중...", progress=95, level="info")
            run_clustering()

            emit_log("모든 작업이 성공적으로 완료되었습니다!", progress=100, level="success")
            workflow_state["status"] = "success"
            workflow_state["progress"] = 100

        except Exception as e:
            emit_log(f"Anki 등록 및 보강 중 오류: {e}", level="error")
            workflow_state["status"] = "error"
        finally:
            workflow_state["is_running"] = False

    threading.Thread(target=run_commit_bg, daemon=True).start()
    return {"status": "success", "message": "Anki 등록 및 AI 보강이 시작되었습니다."}

@router.post("/")
def trigger_workflow_auto(req: WorkflowExtractRequest):
    # Auto mode: extract and commit without user prompt
    if workflow_state["is_running"]:
        return {"status": "error", "message": "이미 실행 중인 워크플로우가 있습니다."}

    from main import run_workflow
    workflow_state["is_running"] = True
    workflow_state["source"] = req.source
    workflow_state["progress"] = 5
    workflow_state["status"] = "running"
    workflow_state["logs"] = []
    emit_log(f"원클릭 자동 작업 시작 (소스: {req.source})", progress=5, level="info")

    def run_bg():
        try:
            run_workflow(req.source, req.input_data, progress_cb=emit_log, is_web=True)
            if workflow_state["status"] != "error":
                workflow_state["status"] = "success"
                workflow_state["progress"] = 100
        except Exception as e:
            emit_log(f"워크플로우 오류: {e}", level="error")
            workflow_state["status"] = "error"
        finally:
            workflow_state["is_running"] = False

    threading.Thread(target=run_bg, daemon=True).start()
    return {"status": "success", "message": f"{req.source} 자동 워크플로우가 시작되었습니다."}
