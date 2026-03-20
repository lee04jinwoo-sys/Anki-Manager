import traceback
import threading
import concurrent.futures
import io
from contextlib import redirect_stdout
from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition

from youtube_extractor import extract_content
from sentence_selector import run_sentence_selection
from vocabulary_selector import run_vocabulary_selection
from note_completor import run_note_completion
from audio_adder import AnkiTTSFiller
from organizor import run_organizer
# ─────────────────────────────────────────────────────────
#  워커
# ─────────────────────────────────────────────────────────

class PyQtProgressTracker:
    def __init__(self, max_points, signals):
        self.max_points = max_points
        self.signals = signals
        self.current_points = 0
        self.lock = threading.Lock()

    def set_description(self, desc): self.signals.status_changed.emit(desc)
    def write(self, msg, **kwargs):
        with self.lock: self.signals.log_added.emit(str(msg))
    def update(self, amount=1):
        with self.lock:
            self.current_points += amount
            self.signals.progress_updated.emit(min(int(self.current_points / self.max_points * 100), 100))


class WorkflowWorker(QThread):
    progress_updated    = pyqtSignal(int)
    log_added           = pyqtSignal(str)
    status_changed      = pyqtSignal(str)
    inspection_requested = pyqtSignal(dict)
    workflow_finished   = pyqtSignal(bool)

    def __init__(self, url, source, num_sentences=None, num_vocab=None):
        super().__init__()
        self.url = url
        self.source = source
        self.num_sentences = int(num_sentences) if num_sentences else None
        self.num_vocab     = int(num_vocab)     if num_vocab     else None
        self.mutex     = QMutex()
        self.condition = QWaitCondition()
        self.inspected_data = None

    def wait_for_inspection(self, data):
        self.inspection_requested.emit(data)
        self.mutex.lock(); self.condition.wait(self.mutex); self.mutex.unlock()
        return self.inspected_data

    def resume_from_inspection(self, data):
        self.inspected_data = data
        self.mutex.lock(); self.condition.wakeAll(); self.mutex.unlock()

    def run(self):
        try:
            steps_map = {
                "url":       {"콘텐츠 추출":10,"문장 선별":30,"어휘 선별":20,"노트 추가":20,"음성 추가":15,"카드 정리":5},
                "notion":    {"Notion 추출":20,"노트 추가":60,"음성 추가":15,"카드 정리":5},
                "situation": {"상황 생성":40,"노트 추가":40,"음성 추가":15,"카드 정리":5},
            }
            ws = {k: {"points": v} for k, v in steps_map[self.source].items()}
            pbar = PyQtProgressTracker(sum(s["points"] for s in ws.values()), self)

            notion_mgr = selected_sentences = selected_vocab = None

            if self.source == "url":
                pbar.set_description("콘텐츠 추출 중...")
                data = extract_content(self.url, pbar=pbar, step_points=ws["콘텐츠 추출"]["points"])
                if not data: pbar.write("❌ 콘텐츠 추출 실패."); self.workflow_finished.emit(False); return
                pbar.set_description("문장 및 어휘 선별 중 (병렬)...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                    fs = ex.submit(run_sentence_selection,  data, pbar, ws["문장 선별"]["points"])
                    fv = ex.submit(run_vocabulary_selection, data, pbar, ws["어휘 선별"]["points"])
                    selected_sentences, selected_vocab = fs.result(), fv.result()
                if selected_sentences is None or selected_vocab is None:
                    pbar.write("❌ 선별 실패."); self.workflow_finished.emit(False); return

            elif self.source == "notion":
                pbar.set_description("Notion 데이터 가져오는 중...")
                from notion_extractor import NotionManager, NOTION_PAGE_ID
                mgr = NotionManager()
                content = mgr.fetch_page_content(NOTION_PAGE_ID)
                if not content: pbar.write("❌ Notion 데이터 없음."); self.workflow_finished.emit(False); return
                vocab_list, sentence_list, mode = [], [], None
                for line in content.split('\n'):
                    line = line.strip()
                    if not line: continue
                    if line == "[단어 추출 대상]": mode = "vocab"; continue
                    elif line == "[문장 추출 대상]": mode = "sentence"; continue
                    if mode == "vocab": vocab_list.append(line)
                    elif mode == "sentence": sentence_list.append(line)
                try:
                    from vocabulary_selector import AnkiManager as VAM
                    existing = VAM.get_existing_vocab(pbar=pbar)
                    filtered = [w for w in vocab_list if w.lower() not in existing]
                    skipped = len(vocab_list) - len(filtered)
                    if skipped: pbar.write(f"✔️ 이미 존재하는 단어 {skipped}개 제외")
                    vocab_list = filtered
                except Exception as e: pbar.write(f"⚠️ 중복 확인 실패: {e}")
                selected_sentences = {"sentences": sentence_list} if sentence_list else {}
                selected_vocab     = {"vocab": vocab_list}        if vocab_list     else {}
                notion_mgr = mgr
                pbar.update(ws["Notion 추출"]["points"])

            elif self.source == "situation":
                pbar.set_description("상황 기반 콘텐츠 생성 중...")
                from situation_generator import generate_situation_content
                gen = generate_situation_content(self.url, pbar=pbar, step_points=ws["상황 생성"]["points"])
                if not gen or not gen.get('sentences') or not gen.get('vocab'):
                    pbar.write("❌ 생성 실패."); self.workflow_finished.emit(False); return
                try:
                    from vocabulary_selector import AnkiManager as VAM
                    existing = VAM.get_existing_vocab(pbar=pbar)
                    filtered = [w for w in gen.get('vocab', []) if w.lower() not in existing]
                    skipped  = len(gen.get('vocab', [])) - len(filtered)
                    if skipped: pbar.write(f"✔️ 이미 존재하는 단어 {skipped}개 제외")
                    selected_vocab = {"vocab": filtered}
                except Exception as e:
                    pbar.write(f"⚠️ 중복 확인 실패: {e}")
                    selected_vocab = {"vocab": gen.get('vocab', [])}
                selected_sentences = {"sentences": gen.get('sentences', [])}

            def qt_inspector(enriched):
                pbar.set_description("검수 대기 중...")
                pbar.write("\n=== 🔎 데이터 최종 검수 ===")
                return self.wait_for_inspection(enriched)

            pbar.set_description("노트 추가 중...")
            if not run_note_completion(selected_sentences, selected_vocab, pbar=pbar,
                                       step_points=ws["노트 추가"]["points"], inspector_func=qt_inspector):
                pbar.write("❌ 노트 추가 실패."); self.workflow_finished.emit(False); return

            if self.source == "notion" and notion_mgr:
                if selected_sentences or selected_vocab:
                    pbar.set_description("Notion 블록 삭제 중...")
                    notion_mgr.delete_processed_blocks()

            pbar.set_description("음성 추가 중...")
            if not AnkiTTSFiller.run_audio_addition(pbar=pbar, step_points=ws["음성 추가"]["points"]):
                pbar.write("❌ 음성 추가 실패."); self.workflow_finished.emit(False); return

            pbar.set_description("카드 정리 중...")
            if not run_organizer(pbar=pbar, step_points=ws["카드 정리"]["points"]):
                pbar.write("❌ 카드 정리 실패."); self.workflow_finished.emit(False); return

            pbar.write("\n🎉 워크플로우 완료!")
            self.status_changed.emit("완료"); self.progress_updated.emit(100); self.workflow_finished.emit(True)

        except Exception as e:
            traceback.print_exc()
            self.log_added.emit(f"❌ 오류: {e}")
            self.status_changed.emit("에러"); self.workflow_finished.emit(False)


class ScriptRunnerWorker(QThread):
    log_added      = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    task_finished  = pyqtSignal(bool)
    progress_updated = pyqtSignal(int)

    def __init__(self, func): super().__init__(); self.func = func
    def run(self):
        try:
            sig = type('S',(),{'log_added':self.log_added,'status_changed':self.status_changed,'progress_updated':self.progress_updated})()
            pbar = PyQtProgressTracker(100, sig)
            with io.StringIO() as buf, redirect_stdout(buf):
                self.func(pbar=pbar); out = buf.getvalue()
            if out: self.log_added.emit(out.strip())
            self.status_changed.emit("완료"); self.progress_updated.emit(100); self.task_finished.emit(True)
        except Exception as e:
            traceback.print_exc()
            self.log_added.emit(f"❌ 오류: {traceback.format_exc()}")
            self.status_changed.emit("에러"); self.task_finished.emit(False)
