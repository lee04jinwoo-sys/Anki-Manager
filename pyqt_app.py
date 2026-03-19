import sys
import traceback
import threading
import concurrent.futures
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QRadioButton, QLineEdit, QPushButton, QLabel, QProgressBar, QTextEdit,
    QDialog, QScrollArea, QCheckBox, QFrame, QButtonGroup, QStyleFactory
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMutex, QWaitCondition
from PyQt6.QtGui import QFont, QIntValidator
import io
from contextlib import redirect_stdout
import sys
import os

# Adjust path for sibling module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
try:
    from util_show_deck_stats import main as deck_stats_main
except ImportError:
    print("WARNING: Could not import deck stats script 'util_show_deck_stats.py'.")
    def deck_stats_main(*args, **kwargs): 
        print("Deck stats script not found or failed to import.")

from note_field_completor import main as field_completor_main

# 내부 모듈 임포트
from youtube_extractor import extract_content
from sentence_selector import run_sentence_selection
from vocabulary_selector import run_vocabulary_selection 
from note_completor import run_note_completion
from audio_adder import AnkiTTSFiller
from organizor import run_organizer

NOTION_STYLESHEET = """
QMainWindow, QDialog {
    background-color: #ffffff;
}
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    color: #37352f;
    font-size: 14px;
}
QLabel {
    color: #37352f;
}
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #e1e1e1;
    border-radius: 6px;
    padding: 8px 12px;
    selection-background-color: #b5d2ff;
}
QLineEdit:focus {
    border: 1px solid #2383e2;
}
QPushButton {
    background-color: #2383e2;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #0060b8;
}
QPushButton:disabled {
    background-color: #e1e1e1;
    color: #9a9a97;
}
QProgressBar {
    border: 1px solid #e1e1e1;
    border-radius: 6px;
    background-color: #f7f7f5;
    text-align: center;
    color: #37352f;
}
QProgressBar::chunk {
    background-color: #2383e2;
    border-radius: 5px;
}
QTextEdit {
    background-color: #f7f7f5;
    border: 1px solid #e1e1e1;
    border-radius: 6px;
    padding: 10px;
    color: #37352f;
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 13px;
}
QScrollArea {
    border: 1px solid #e1e1e1;
    border-radius: 6px;
    background-color: #ffffff;
}
QScrollArea > QWidget > QWidget {
    background-color: #ffffff;
}
QCheckBox {
    spacing: 8px;
}
"""

class PyQtProgressTracker:
    def __init__(self, max_points, signals):
        self.max_points = max_points
        self.signals = signals
        self.current_points = 0
        self.lock = threading.Lock()
        
    def set_description(self, desc):
        self.signals.status_changed.emit(desc)
        
    def write(self, msg, **kwargs):
        with self.lock:
            self.signals.log_added.emit(str(msg))
        
    def update(self, amount=1):
        with self.lock:
            self.current_points += amount
            progress = int((self.current_points / self.max_points) * 100)
            self.signals.progress_updated.emit(min(progress, 100))

class WorkflowWorker(QThread):
    progress_updated = pyqtSignal(int)
    log_added = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    inspection_requested = pyqtSignal(dict)
    workflow_finished = pyqtSignal(bool)

    def __init__(self, url, source, num_sentences=None, num_vocab=None):
        super().__init__()
        self.url = url
        self.source = source
        self.num_sentences = int(num_sentences) if num_sentences else None
        self.num_vocab = int(num_vocab) if num_vocab else None
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.inspected_data = None
        self.is_running = True

    def wait_for_inspection(self, data):
        self.inspection_requested.emit(data)
        
        self.mutex.lock()
        self.condition.wait(self.mutex)
        self.mutex.unlock()
        
        return self.inspected_data
        
    def resume_from_inspection(self, modified_data):
        self.inspected_data = modified_data
        self.mutex.lock()
        self.condition.wakeAll()
        self.mutex.unlock()

    def run(self):
        try:
            if self.source == "url":
                workflow_steps = {
                    "콘텐츠 추출": {"points": 10},
                    "문장 선별": {"points": 30},
                    "어휘 선별": {"points": 20},
                    "노트 추가": {"points": 20},
                    "음성 추가": {"points": 15},
                    "카드 정리": {"points": 5},
                }
            elif self.source == "notion":
                workflow_steps = {
                    "Notion 추출": {"points": 20},
                    "노트 추가": {"points": 60},
                    "음성 추가": {"points": 15},
                    "카드 정리": {"points": 5},
                }
            elif self.source == "situation": # 상황 모드일 때의 포인트 배분
                workflow_steps = {
                    "상황 생성": {"points": 40},
                    "노트 추가": {"points": 40},
                    "음성 추가": {"points": 15},
                    "카드 정리": {"points": 5},
                }

            total_points = sum(step["points"] for step in workflow_steps.values())
            pbar = PyQtProgressTracker(total_points, self)

            notion_manager_instance = None
            selected_sentences = None
            selected_vocab = None

            if self.source == "url":
                pbar.set_description("콘텐츠 추출 중...")
                extracted_data = extract_content(self.url, pbar=pbar, step_points=workflow_steps["콘텐츠 추출"]["points"])
                if not extracted_data:
                    pbar.write("❌ 콘텐츠 추출 실패. 워크플로우를 종료합니다.")
                    self.workflow_finished.emit(False)
                    return

                pbar.set_description("문장 및 어휘 선별 중 (병렬 처리)...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    future_sentence = executor.submit(
                        run_sentence_selection, extracted_data, pbar, workflow_steps["문장 선별"]["points"]
                    )
                    future_vocab = executor.submit(
                        run_vocabulary_selection, extracted_data, pbar, workflow_steps["어휘 선별"]["points"]
                    )
                    
                    selected_sentences = future_sentence.result()
                    selected_vocab = future_vocab.result()

                if selected_sentences is None or selected_vocab is None:
                    pbar.write("❌ 문장 또는 어휘 선별 실패. 워크플로우를 종료합니다.")
                    self.workflow_finished.emit(False)
                    return
            elif self.source == "notion":
                pbar.set_description("Notion 데이터 가져오는 중...")
                from notion_extractor import NotionManager, NOTION_PAGE_ID
                manager = NotionManager()
                content = manager.fetch_page_content(NOTION_PAGE_ID)
                
                if not content:
                    pbar.write("❌ 노션에 데이터가 없거나 추출에 실패했습니다.")
                    self.workflow_finished.emit(False)
                    return

                vocab_list = []
                sentence_list = []
                
                lines = content.split('\n')
                current_mode = None
                for line in lines:
                    line = line.strip()
                    if not line: continue
                    if line == "[단어 추출 대상]":
                        current_mode = "vocab"
                        continue
                    elif line == "[문장 추출 대상]":
                        current_mode = "sentence"
                        continue
                        
                    if current_mode == "vocab":
                        vocab_list.append(line)
                    elif current_mode == "sentence":
                        sentence_list.append(line)

                # Anki 중복 방지 필터링 (Notion 파이프라인용)
                try:
                    from vocabulary_selector import AnkiManager as VocabAnkiManager
                    existing_vocab = VocabAnkiManager.get_existing_vocab(pbar=pbar)
                    
                    filtered_vocab = []
                    skipped_vocab = 0
                    for word in vocab_list:
                        # 대소문자 무관 비교
                        if word.lower() not in existing_vocab:
                            filtered_vocab.append(word)
                        else:
                            skipped_vocab += 1
                    
                    if skipped_vocab > 0:
                        pbar.write(f"✔️ Anki에 이미 존재하는 단어 {skipped_vocab}개를 자동으로 제외했습니다.")
                    vocab_list = filtered_vocab
                except Exception as e:
                    pbar.write(f"⚠️ Anki 중복 단어 확인 실패: {e}")

                # 문장도 중복 방지가 필요하다면 추가 가능 (기본적으로 단어가 더 중복이 잦음)
                        
                selected_sentences = {"sentences": sentence_list} if sentence_list else {}
                selected_vocab = {"vocab": vocab_list} if vocab_list else {}
                notion_manager_instance = manager 
                pbar.update(workflow_steps["Notion 추출"]["points"])

            elif self.source == "situation":
                pbar.set_description("상황 기반 콘텐츠 생성 중...")
                from situation_generator import generate_situation_content
                generated_data = generate_situation_content(self.url, pbar=pbar, step_points=workflow_steps["상황 생성"]["points"])
                
                if not generated_data or not generated_data.get('sentences') or not generated_data.get('vocab'):
                    pbar.write("❌ 상황 기반 콘텐츠 생성에 실패했거나, 생성된 데이터가 비어있습니다.")
                    self.workflow_finished.emit(False)
                    return

                # Anki 중복 방지 필터링
                try:
                    from vocabulary_selector import AnkiManager as VocabAnkiManager
                    existing_vocab = VocabAnkiManager.get_existing_vocab(pbar=pbar)
                    
                    filtered_vocab = []
                    skipped_vocab = 0
                    for word in generated_data.get('vocab', []):
                        if word.lower() not in existing_vocab:
                            filtered_vocab.append(word)
                        else:
                            skipped_vocab += 1
                    
                    if skipped_vocab > 0:
                        pbar.write(f"✔️ Anki에 이미 존재하는 단어 {skipped_vocab}개를 자동으로 제외했습니다.")
                    
                    selected_vocab = {"vocab": filtered_vocab}
                except Exception as e:
                    pbar.write(f"⚠️ Anki 중복 단어 확인 실패: {e}")
                    selected_vocab = {"vocab": generated_data.get('vocab', [])}

                # 문장은 현재 중복 체크를 가정하지 않음
                selected_sentences = {"sentences": generated_data.get('sentences', [])}

            def qt_inspector(enriched_data):
                pbar.set_description("데이터 검수 대기 중...")
                pbar.write("\n=== 🔎 데이터 최종 검수 (Inspector) ===")
                return self.wait_for_inspection(enriched_data)

            pbar.set_description("노트 추가 (뜻 생성 및 검수 포함) 중...")
            if not run_note_completion(selected_sentences, selected_vocab, pbar=pbar, step_points=workflow_steps["노트 추가"]["points"], inspector_func=qt_inspector):
                pbar.write("❌ 노트 추가 실패. 워크플로우를 종료합니다.")
                self.workflow_finished.emit(False)
                return

            if self.source == "notion" and notion_manager_instance:
                if selected_sentences or selected_vocab:
                    pbar.set_description("Notion 블록 삭제 중...")
                    notion_manager_instance.delete_processed_blocks()
                else:
                    pbar.write("ℹ️ 추가할 내용이 없으므로 노션 블록 삭제를 건너뜁니다.")

            pbar.set_description("음성 추가 중...")
            if not AnkiTTSFiller.run_audio_addition(pbar=pbar, step_points=workflow_steps["음성 추가"]["points"]):
                pbar.write("❌ 음성 파일 추가 실패. 워크플로우를 종료합니다.")
                self.workflow_finished.emit(False)
                return

            pbar.set_description("카드 정리 중...")
            if not run_organizer(pbar=pbar, step_points=workflow_steps["카드 정리"]["points"]):
                pbar.write("❌ 카드 정리 실패. 워크플로우를 종료합니다.")
                self.workflow_finished.emit(False)
                return

            pbar.write("\n🎉 Anki 자동화 워크플로우가 성공적으로 완료되었습니다!")
            self.status_changed.emit("작업 완료!")
            self.progress_updated.emit(100)
            self.workflow_finished.emit(True)

        except Exception as e:
            traceback.print_exc()
            self.log_added.emit(f"❌ 오류 발생: {str(e)}")
            self.status_changed.emit("에러 발생")
            self.workflow_finished.emit(False)


class InspectorDialog(QDialog):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("데이터 최종 검수 (Inspector)")
        self.resize(750, 600)
        self.setModal(True)
        self.data = data
        self.checkboxes = {}

        layout = QVBoxLayout(self)

        info_label = QLabel("체크를 해제하면 Anki에 추가되지 않습니다.")
        info_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(info_label)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)

        # 문장 섹션
        if data and 'sentences' in data and data['sentences']:
            s_label = QLabel("📖 문장 검수")
            s_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            scroll_layout.addWidget(s_label)
            
            self.checkboxes['sentences'] = []
            for item in data['sentences']:
                text = f"[문장] {item.get('문장', '')}\n └ 해석: {item.get('해설', '')}"
                cb = QCheckBox(text)
                cb.setChecked(True)
                scroll_layout.addWidget(cb)
                self.checkboxes['sentences'].append((cb, item))
                
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            scroll_layout.addWidget(line)

        # 어휘 섹션
        if data and 'vocab' in data and data['vocab']:
            v_label = QLabel("📚 어휘 검수")
            v_label.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            scroll_layout.addWidget(v_label)
            
            self.checkboxes['vocab'] = []
            for item in data['vocab']:
                text = f"[단어] {item.get('단어', '')}\n ├ 뜻: {item.get('뜻', '')}\n └ 설명: {item.get('설명', '')}"
                cb = QCheckBox(text)
                cb.setChecked(True)
                scroll_layout.addWidget(cb)
                self.checkboxes['vocab'].append((cb, item))

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        confirm_btn = QPushButton("확인 및 계속")
        confirm_btn.setMinimumHeight(40)
        confirm_btn.setMinimumWidth(150)
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(confirm_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def get_modified_data(self):
        modified = {}
        if 'sentences' in self.checkboxes:
            modified['sentences'] = [item for cb, item in self.checkboxes['sentences'] if cb.isChecked()]
        if 'vocab' in self.checkboxes:
            modified['vocab'] = [item for cb, item in self.checkboxes['vocab'] if cb.isChecked()]
        return modified


class ScriptRunnerWorker(QThread):
    log_added = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    task_finished = pyqtSignal(bool)
    progress_updated = pyqtSignal(int)

    def __init__(self, target_func, pbar_enabled=True):
        super().__init__()
        self.target_func = target_func
        self.pbar_enabled = pbar_enabled

    def run(self):
        try:
            pbar = None
            if self.pbar_enabled:
                signals = type('Signals', (), {
                    'log_added': self.log_added,
                    'status_changed': self.status_changed,
                    'progress_updated': self.progress_updated
                })()
                # tqdm progress requires a total. We'll use a dummy total, 
                # as these scripts are mostly about log output.
                pbar = PyQtProgressTracker(100, signals)

            with io.StringIO() as buf, redirect_stdout(buf):
                self.target_func(pbar=pbar)
                output = buf.getvalue()

            if output:
                self.log_added.emit(output.strip())
            
            self.status_changed.emit("작업 완료!")
            self.progress_updated.emit(100)
            self.task_finished.emit(True)

        except Exception as e:
            traceback.print_exc()
            self.log_added.emit(f"❌ 오류 발생: {traceback.format_exc()}")
            self.status_changed.emit("에러 발생")
            self.task_finished.emit(False)


class AnkiPyQtApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anki 자동화 매니저 (PyQt6)")
        self.resize(850, 700)
        self.worker = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- Mode Selection ---
        mode_layout = QHBoxLayout()
        mode_label = QLabel("실행 모드:")
        mode_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        mode_layout.addWidget(mode_label)

        self.btn_workflow_mode = QRadioButton("콘텐츠 생성")
        self.btn_workflow_mode.setChecked(True)
        self.btn_workflow_mode.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.btn_workflow_mode)

        self.btn_stats_mode = QRadioButton("통계 분석")
        self.btn_stats_mode.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.btn_stats_mode)

        self.btn_audio_mode = QRadioButton("오디오 채우기")
        self.btn_audio_mode.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.btn_audio_mode)

        self.btn_fields_mode = QRadioButton("필드 채우기")
        self.btn_fields_mode.toggled.connect(self.on_mode_changed)
        mode_layout.addWidget(self.btn_fields_mode)

        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)
        
        # --- Workflow Source Selection (Initially visible) ---
        self.workflow_source_widget = QWidget()
        source_layout = QHBoxLayout(self.workflow_source_widget)
        source_layout.setContentsMargins(10, 5, 0, 5)
        source_label = QLabel("입력 소스:")
        source_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        source_layout.addWidget(source_label)

        self.btn_url = QRadioButton("YouTube / Web")
        self.btn_url.setChecked(True)
        self.btn_url.toggled.connect(self.on_source_changed)
        source_layout.addWidget(self.btn_url)

        self.btn_notion = QRadioButton("Notion")
        self.btn_notion.toggled.connect(self.on_source_changed)
        source_layout.addWidget(self.btn_notion)
        
        self.btn_situation = QRadioButton("상황별 생성")
        self.btn_situation.toggled.connect(self.on_source_changed)
        source_layout.addWidget(self.btn_situation)

        source_layout.addStretch()
        main_layout.addWidget(self.workflow_source_widget)

        # --- URL Input & Options (Shared UI elements) ---
        self.input_options_widget = QWidget()
        input_options_layout = QVBoxLayout(self.input_options_widget)
        input_options_layout.setContentsMargins(0,0,0,0)
        input_options_layout.setSpacing(8)

        url_layout = QHBoxLayout()
        self.url_label = QLabel("URL / 상황 설명:")
        url_layout.addWidget(self.url_label)
        
        self.url_input = QLineEdit()
        url_layout.addWidget(self.url_input)
        input_options_layout.addLayout(url_layout)

        option_layout = QHBoxLayout()
        option_layout.setContentsMargins(0, 5, 0, 0)
        self.num_sentences_label = QLabel("문장 수:")
        option_layout.addWidget(self.num_sentences_label)
        self.num_sentences_input = QLineEdit()
        self.num_sentences_input.setValidator(QIntValidator(1, 100))
        self.num_sentences_input.setMaximumWidth(120)
        option_layout.addWidget(self.num_sentences_input)
        self.num_vocab_label = QLabel("어휘 수:")
        option_layout.addWidget(self.num_vocab_label)
        self.num_vocab_input = QLineEdit()
        self.num_vocab_input.setValidator(QIntValidator(1, 100))
        self.num_vocab_input.setMaximumWidth(120)
        option_layout.addWidget(self.num_vocab_input)
        option_layout.addStretch()
        input_options_layout.addLayout(option_layout)
        main_layout.addWidget(self.input_options_widget)

        # --- Start Button ---
        start_layout = QHBoxLayout()
        start_layout.addStretch()
        self.btn_start = QPushButton("시작")
        self.btn_start.setMinimumWidth(120)
        self.btn_start.setMinimumHeight(35)
        self.btn_start.clicked.connect(self.start_task)
        start_layout.addWidget(self.btn_start)
        main_layout.addLayout(start_layout)
        
        # --- Status & Progress ---
        self.status_label = QLabel("대기 중...")
        self.status_label.setFont(QFont("Arial", 12))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # --- Log Box ---
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Menlo", 12))
        main_layout.addWidget(self.log_box)
        
        self.on_mode_changed()

    def on_mode_changed(self):
        if self.btn_workflow_mode.isChecked():
            self.workflow_source_widget.setVisible(True)
            self.input_options_widget.setVisible(True)
            self.on_source_changed()
        else:
            self.workflow_source_widget.setVisible(False)
            self.input_options_widget.setVisible(False)

    def on_source_changed(self):
        selected_source = "url"
        if self.btn_notion.isChecked(): selected_source = "notion"
        elif self.btn_situation.isChecked(): selected_source = "situation"

        is_situation = selected_source == "situation"
        is_notion = selected_source == "notion"

        self.num_sentences_label.setVisible(is_situation)
        self.num_sentences_input.setVisible(is_situation)
        self.num_vocab_label.setVisible(is_situation)
        self.num_vocab_input.setVisible(is_situation)
        self.url_input.setEnabled(not is_notion)

        if is_notion:
            self.url_label.setText("URL (Notion):")
            self.url_input.setPlaceholderText("Notion 페이지 ID는 config.py에 설정됩니다.")
        elif is_situation:
            self.url_label.setText("상황 설명:")
            self.url_input.setPlaceholderText("예: 식당에서 주문할 때, 회의에서 의견을 제시할 때")
        else: # URL
            self.url_label.setText("URL:")
            self.url_input.setPlaceholderText("YouTube 영상 또는 웹페이지 주소를 입력하세요.")

    def run_deck_stats(self, pbar):
        if pbar: pbar.set_description("덱 통계 분석 중...")
        deck_stats_main(pbar=pbar)

    def run_audio_adder(self, pbar):
        if pbar: pbar.set_description("오디오 파일 채우는 중...")
        AnkiTTSFiller.run_audio_addition(pbar=pbar, step_points=100 if pbar else 0)

    def run_field_completor(self, pbar):
        if pbar: pbar.set_description("노트 필드 채우는 중...")
        field_completor_main(pbar=pbar)

    def start_task(self):
        self.btn_start.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log_box.clear()

        if self.btn_workflow_mode.isChecked():
            source = "url"
            if self.btn_notion.isChecked(): source = "notion"
            elif self.btn_situation.isChecked(): source = "situation"
            
            input_text = self.url_input.text().strip()
            num_sentences = self.num_sentences_input.text().strip()
            num_vocab = self.num_vocab_input.text().strip()

            if (source == "url" or source == "situation") and not input_text:
                self.append_log(f"❌ {self.url_label.text()}을(를) 입력해주세요.")
                self.btn_start.setEnabled(True)
                return

            self.update_status(f"🚀 콘텐츠 생성 모드 시작... ({source.upper()})")
            self.worker = WorkflowWorker(input_text, source, num_sentences, num_vocab)
            self.worker.inspection_requested.connect(self.handle_inspection)
            self.worker.workflow_finished.connect(self.on_task_finished)
        
        else: # Other modes
            target_func, pbar_enabled = None, True
            if self.btn_stats_mode.isChecked():
                self.update_status("🚀 통계 분석 모드 시작...")
                target_func = self.run_deck_stats
            elif self.btn_audio_mode.isChecked():
                self.update_status("🚀 오디오 채우기 모드 시작...")
                target_func = self.run_audio_adder
            elif self.btn_fields_mode.isChecked():
                self.update_status("🚀 필드 채우기 모드 시작...")
                target_func = self.run_field_completor

            if target_func:
                self.worker = ScriptRunnerWorker(target_func, pbar_enabled=pbar_enabled)
                self.worker.task_finished.connect(self.on_task_finished)

        # Connect common signals and start worker
        if self.worker:
            self.worker.progress_updated.connect(self.update_progress)
            self.worker.log_added.connect(self.append_log)
            self.worker.status_changed.connect(self.update_status)
            self.worker.start()
        else:
            self.btn_start.setEnabled(True)

    def append_log(self, msg):
        self.log_box.append(msg)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def update_progress(self, val):
        self.progress_bar.setValue(val)

    def update_status(self, msg):
        self.status_label.setText(msg)

    def handle_inspection(self, data):
        self.append_log("✨ 검수 창이 열렸습니다. 항목을 확인해주세요.")
        dialog = InspectorDialog(self, data)
        dialog.exec()
        modified_data = dialog.get_modified_data()
        self.append_log("✔️ 검수가 완료되어 작업을 재개합니다.")
        self.worker.resume_from_inspection(modified_data)

    def on_task_finished(self, success):
        self.btn_start.setEnabled(True)
        self.worker = None

if __name__ == '__main__':
    # Mac 네이티브 스타일(Fusion 또는 macOS 기본) 설정
    app = QApplication(sys.argv)
    app.setStyleSheet(NOTION_STYLESHEET)
    if 'macOS' in QStyleFactory.keys():
        app.setStyle('macOS')
    elif 'Fusion' in QStyleFactory.keys():
        app.setStyle('Fusion')
        
    window = AnkiPyQtApp()
    window.show()
    sys.exit(app.exec())