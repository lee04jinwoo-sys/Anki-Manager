import json
import os
import config
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit,
    QTextEdit, QDoubleSpinBox, QSpinBox, QPushButton, QScrollArea,
    QMessageBox, QListWidget, QListWidgetItem, QFormLayout, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont

from ui_styles import STYLESHEET
from ui_widgets import SectionLabel, ThinDivider

USER_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_config.json")

def load_user_config() -> dict:
    if not os.path.exists(USER_CONFIG_PATH): return {}
    try:
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_user_config(data: dict):
    with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_config_value(key: str):
    return load_user_config().get(key, getattr(config, key, None))

class VoiceListEditor(QWidget):
    def __init__(self, voices: list, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 5, 0, 0); layout.setSpacing(8)
        self.list_widget = QListWidget(); self.list_widget.addItems(voices); layout.addWidget(self.list_widget)
        btn_row = QHBoxLayout()
        self.input = QLineEdit(); self.input.setPlaceholderText("새 보이스 ID (예: en-US-Studio-O)"); btn_row.addWidget(self.input, 1)
        add_btn = QPushButton("추가"); add_btn.setFixedWidth(70); add_btn.clicked.connect(self._add); btn_row.addWidget(add_btn)
        del_btn = QPushButton("삭제"); del_btn.setFixedWidth(70); del_btn.setStyleSheet("background-color: #d94242; color: white;"); del_btn.clicked.connect(self._delete); btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

    def _add(self):
        text = self.input.text().strip()
        if text: self.list_widget.addItem(text); self.input.clear()

    def _delete(self):
        for item in self.list_widget.selectedItems(): self.list_widget.takeItem(self.list_widget.row(item))

    def get_values(self) -> list:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

class OrganizerRulesEditor(QWidget):
    def __init__(self, rules: list, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(5)
        self.rows_layout = QVBoxLayout(); layout.addLayout(self.rows_layout)
        for rule in rules: self._add_row(rule.get("query", ""), rule.get("target_deck", ""))
        add_btn = QPushButton("+ 규칙 추가"); add_btn.setStyleSheet("background-color: transparent; border: 1px solid #e3e1dc; color: #37352f; font-weight: 400;"); add_btn.setFixedHeight(34); add_btn.clicked.connect(lambda: self._add_row()); layout.addWidget(add_btn, 0, Qt.AlignmentFlag.AlignLeft)

    def _add_row(self, query="", deck=""):
        row = QWidget(); row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0, 2, 0, 2); row_layout.setSpacing(8)
        q_input = QLineEdit(query); q_input.setPlaceholderText("Anki 쿼리"); row_layout.addWidget(q_input, 1)
        d_input = QLineEdit(deck); d_input.setPlaceholderText("대상 덱"); row_layout.addWidget(d_input, 1)
        del_btn = QPushButton("삭제"); del_btn.setFixedWidth(60); del_btn.setStyleSheet("background-color: transparent; border: 1px solid #e3e1dc; color: #d94242; font-weight: 400;"); row_layout.addWidget(del_btn)
        row.setProperty("inputs", (q_input, d_input)); del_btn.clicked.connect(row.deleteLater)
        self.rows_layout.addWidget(row)

    def get_values(self) -> list:
        return [
            {"query": item.widget().property("inputs")[0].text().strip(), "target_deck": item.widget().property("inputs")[1].text().strip()}
            for i in range(self.rows_layout.count()) if (item := self.rows_layout.itemAt(i)) and item.widget()
            and (item.widget().property("inputs")[0].text().strip() or item.widget().property("inputs")[1].text().strip())
        ]

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Anki Manager 설정"); self.resize(820, 680); self.setModal(True); self.setStyleSheet(STYLESHEET)
        self.cfg = {key: get_config_value(key) for key in dir(config) if not key.startswith('__')}
        self.widgets = {}

        root_layout = QVBoxLayout(self); root_layout.setContentsMargins(0,0,0,0); root_layout.setSpacing(0)
        title_bar = QWidget(); title_bar.setFixedHeight(52); title_bar.setStyleSheet("background: #f7f7f5; border-bottom: 1px solid #ebebea;")
        title_layout = QHBoxLayout(title_bar); title_layout.setContentsMargins(24,0,24,0)
        title = QLabel("설정"); title.setFont(QFont(".AppleSystemUIFont", 16, QFont.Weight.Bold)); title_layout.addWidget(title)
        root_layout.addWidget(title_bar)

        main_layout = QHBoxLayout(); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        root_layout.addLayout(main_layout, 1)

        self.nav = QListWidget(); self.nav.setFixedWidth(200)
        self.nav.setStyleSheet("""
            QListWidget { background-color: #f7f7f5; border-right: 1px solid #ebebea; padding-top: 10px; }
            QListWidget::item { padding: 8px 20px; border-radius: 6px; margin: 2px 10px; }
            QListWidget::item:hover { background: #efefed; }
            QListWidget::item:selected { background: #ebebea; color: #37352f; font-weight: 500; }
        """)
        main_layout.addWidget(self.nav)

        self.stack = QStackedWidget(); main_layout.addWidget(self.stack)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self._build_tabs()

        btn_bar = QWidget(); btn_bar.setStyleSheet("background: #ffffff; border-top: 1px solid #ebebea;")
        btn_row = QHBoxLayout(btn_bar); btn_row.setContentsMargins(20, 12, 20, 12); btn_row.addStretch()
        reset_btn = QPushButton("기본값으로 초기화"); reset_btn.setStyleSheet("background-color: #d94242; color: white;"); reset_btn.clicked.connect(self._reset); btn_row.addWidget(reset_btn)
        save_btn = QPushButton("저장"); save_btn.setDefault(True); save_btn.clicked.connect(self._save); btn_row.addWidget(save_btn)
        root_layout.addWidget(btn_bar)

    def _build_tabs(self):
        tabs = [
            ("🤖 AI 모델", self._build_tab_model), ("🗂️ Anki", self._build_tab_anki),
            ("🔊 TTS / 음성", self._build_tab_tts), ("📝 프롬프트", self._build_tab_prompts),
            ("🗃️ 카드 정리", self._build_tab_organizer),
        ]
        for name, builder in tabs:
            item = QListWidgetItem(name); item.setSizeHint(QSize(-1, 36)); self.nav.addItem(item)
            scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(builder()); self.stack.addWidget(scroll)

    def _create_tab_content(self, sections: list):
        content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(32,24,32,24); layout.setSpacing(12)
        for title, fields in sections:
            layout.addWidget(SectionLabel(title)); layout.addWidget(ThinDivider())
            form = QFormLayout(); form.setLabelAlignment(Qt.AlignmentFlag.AlignRight); form.setSpacing(10); form.setContentsMargins(0, 8, 0, 8)
            for field in fields: form.addRow(*field)
            layout.addLayout(form); layout.addSpacing(12)
        layout.addStretch(); return content

    def _build_tab_model(self):
        self.widgets['SENTENCE_SELECTOR_MODEL'] = QLineEdit(self.cfg.get("SENTENCE_SELECTOR_MODEL"))
        self.widgets['VOCAB_SELECTOR_MODEL'] = QLineEdit(self.cfg.get("VOCAB_SELECTOR_MODEL"))
        self.widgets['NOTE_COMPLETOR_MODEL'] = QLineEdit(self.cfg.get("NOTE_COMPLETOR_MODEL"))
        self.widgets['SITUATION_GENERATOR_MODEL'] = QLineEdit(self.cfg.get("SITUATION_GENERATOR_MODEL"))

        self.widgets['GEMINI_DEFAULT_TEMPERATURE'] = QDoubleSpinBox()
        self.widgets['GEMINI_DEFAULT_TEMPERATURE'].setRange(0.0, 2.0); self.widgets['GEMINI_DEFAULT_TEMPERATURE'].setSingleStep(0.05)
        self.widgets['GEMINI_DEFAULT_TEMPERATURE'].setValue(self.cfg.get("GEMINI_DEFAULT_TEMPERATURE", 0.7))

        self.widgets['GEMINI_SITUATION_TEMPERATURE'] = QDoubleSpinBox()
        self.widgets['GEMINI_SITUATION_TEMPERATURE'].setRange(0.0, 2.0); self.widgets['GEMINI_SITUATION_TEMPERATURE'].setSingleStep(0.05)
        self.widgets['GEMINI_SITUATION_TEMPERATURE'].setValue(self.cfg.get("GEMINI_SITUATION_TEMPERATURE", 0.9))

        self.widgets['NOTE_COMPLETOR_MAX_WORKERS'] = QSpinBox()
        self.widgets['NOTE_COMPLETOR_MAX_WORKERS'].setRange(1, 16); self.widgets['NOTE_COMPLETOR_MAX_WORKERS'].setValue(self.cfg.get("NOTE_COMPLETOR_MAX_WORKERS", 4))

        self.widgets['AUDIO_ADDER_MAX_WORKERS'] = QSpinBox()
        self.widgets['AUDIO_ADDER_MAX_WORKERS'].setRange(1, 16); self.widgets['AUDIO_ADDER_MAX_WORKERS'].setValue(self.cfg.get("AUDIO_ADDER_MAX_WORKERS", 4))

        return self._create_tab_content([
            ("Gemini 모델 선택", [
                ("문장 선별:", self.widgets['SENTENCE_SELECTOR_MODEL']), ("어휘 선별:", self.widgets['VOCAB_SELECTOR_MODEL']),
                ("노트 완성:", self.widgets['NOTE_COMPLETOR_MODEL']), ("상황 생성:", self.widgets['SITUATION_GENERATOR_MODEL']),
            ]),
            ("Temperature 설정", [
                ("기본:", self.widgets['GEMINI_DEFAULT_TEMPERATURE']), ("상황 생성:", self.widgets['GEMINI_SITUATION_TEMPERATURE']),
            ]),
            ("동시 실행 설정", [
                ("노트 완성 (Max Workers):", self.widgets['NOTE_COMPLETOR_MAX_WORKERS']),
                ("오디오 추가 (Max Workers):", self.widgets['AUDIO_ADDER_MAX_WORKERS']),
            ]),
        ])

    def _build_tab_anki(self):
        self.widgets['ANKI_URL'] = QLineEdit(self.cfg.get("ANKI_URL"))
        self.widgets['DECK_SENTENCE'] = QLineEdit(self.cfg.get("DECK_SENTENCE"))
        self.widgets['MODEL_SENTENCE'] = QLineEdit(self.cfg.get("MODEL_SENTENCE"))
        self.widgets['DECK_VOCAB'] = QLineEdit(self.cfg.get("DECK_VOCAB"))
        self.widgets['MODEL_VOCAB'] = QLineEdit(self.cfg.get("MODEL_VOCAB"))
        self.widgets['CANDIDATES_FILE'] = QLineEdit(self.cfg.get("CANDIDATES_FILE"))
        self.widgets['SELECTED_SENTENCES_FILE'] = QLineEdit(self.cfg.get("SELECTED_SENTENCES_FILE"))
        self.widgets['SELECTED_VOCAB_FILE'] = QLineEdit(self.cfg.get("SELECTED_VOCAB_FILE"))
        self.widgets['TEMP_DIR'] = QLineEdit(self.cfg.get("TEMP_DIR"))

        return self._create_tab_content([
            ("AnkiConnect", [("URL:", self.widgets['ANKI_URL'])]),
            ("덱 & 노트 타입", [
                ("문장 덱:", self.widgets['DECK_SENTENCE']), ("문장 노트 타입:", self.widgets['MODEL_SENTENCE']),
                ("어휘 덱:", self.widgets['DECK_VOCAB']), ("어휘 노트 타입:", self.widgets['MODEL_VOCAB']),
            ]),
            ("파일 경로", [
                ("candidates.json:", self.widgets['CANDIDATES_FILE']),
                ("selected_sentences.json:", self.widgets['SELECTED_SENTENCES_FILE']),
                ("selected_vocab.json:", self.widgets['SELECTED_VOCAB_FILE']),
                ("임시 디렉토리:", self.widgets['TEMP_DIR']),
            ]),
        ])

    def _build_tab_tts(self):
        content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(32,24,32,24); layout.setSpacing(12)
        
        self.widgets['TTS_SENTENCE_LANGUAGE_CODE'] = QLineEdit(self.cfg.get("TTS_SENTENCE_LANGUAGE_CODE"))
        self.widgets['TTS_VOCAB_LANGUAGE'] = QLineEdit(self.cfg.get("TTS_VOCAB_LANGUAGE"))
        self.widgets['TTS_VOCAB_TLD'] = QLineEdit(self.cfg.get("TTS_VOCAB_TLD"))
        
        tts_settings = self._create_tab_content([("TTS 언어 설정", [
            ("문장 언어 코드 (Google):", self.widgets['TTS_SENTENCE_LANGUAGE_CODE']),
            ("어휘 언어 (gTTS):", self.widgets['TTS_VOCAB_LANGUAGE']),
            ("어휘 TLD (gTTS):", self.widgets['TTS_VOCAB_TLD']),
        ])])
        layout.addWidget(tts_settings)

        layout.addWidget(SectionLabel("사용할 Google TTS 보이스 목록")); layout.addWidget(ThinDivider())
        layout.addWidget(QLabel("위에서부터 순서대로 사용됩니다.", styleSheet="color: #91918e; font-size: 13px;"))
        self.widgets['VOICE_LIST'] = VoiceListEditor(self.cfg.get("VOICE_LIST", [])); layout.addWidget(self.widgets['VOICE_LIST'])
        layout.addStretch(); return content

    def _build_tab_prompts(self):
        content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(32,24,32,24); layout.setSpacing(12)
        self.widgets['prompts'] = {}
        for key, label in [
            ("NOTE_COMPLETOR_SYS_INSTRUCT", "노트 완성"), ("VOCAB_SELECTOR_SYS_INSTRUCT", "어휘 선별"),
            ("SENTENCE_SELECTOR_SYS_INSTRUCT", "문장 선별"), ("SITUATION_GENERATOR_SYS_INSTRUCT", "상황 생성"),
        ]:
            layout.addWidget(SectionLabel(f"{label} 시스템 프롬프트")); layout.addWidget(ThinDivider())
            te = QTextEdit(self.cfg.get(key, "")); te.setMinimumHeight(180); layout.addWidget(te)
            self.widgets['prompts'][key] = te
        layout.addStretch(); return content

    def _build_tab_organizer(self):
        content = QWidget(); layout = QVBoxLayout(content); layout.setContentsMargins(32,24,32,24); layout.setSpacing(12)
        layout.addWidget(SectionLabel("카드 정리 규칙")); layout.addWidget(ThinDivider())
        layout.addWidget(QLabel("쿼리에 매칭되는 카드를 대상 덱으로 이동합니다.", styleSheet="color: #91918e; font-size: 13px;"))
        header = QHBoxLayout(); header.setContentsMargins(0, 8, 0, 4); header.addWidget(QLabel("<b>Anki 쿼리</b>"), 1); header.addWidget(QLabel("<b>대상 덱</b>"), 1); header.addSpacing(74); layout.addLayout(header)
        self.widgets['ORGANIZER_RULES'] = OrganizerRulesEditor(self.cfg.get("ORGANIZER_RULES", [])); layout.addWidget(self.widgets['ORGANIZER_RULES'])
        layout.addStretch(); return content

    def _collect(self):
        data = {}
        for key, w in self.widgets.items():
            if key == 'prompts': continue
            if isinstance(w, QLineEdit): data[key] = w.text().strip()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)): data[key] = w.value()
            elif isinstance(w, (VoiceListEditor, OrganizerRulesEditor)): data[key] = w.get_values()
        for key, te in self.widgets.get('prompts', {}).items(): data[key] = te.toPlainText().strip()
        return data

    def _save(self):
        try:
            save_user_config(self._collect()); QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다."); self.accept()
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", f"설정 저장 중 오류: {e}")

    def _reset(self):
        if QMessageBox.question(self, "초기화 확인", "사용자 설정을 모두 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            if os.path.exists(USER_CONFIG_PATH): os.remove(USER_CONFIG_PATH)
            QMessageBox.information(self, "초기화 완료", "기본값으로 초기화되었습니다."); self.accept()

