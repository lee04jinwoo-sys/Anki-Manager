import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QStyleFactory
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPalette

# 내부 모듈 임포트
from ui_icons import ICON, make_svg_label
from ui_styles import STYLESHEET
from ui_widgets import NavItem, GhostButton
from ui_pages import ContentPage, SimplePage
from workers import WorkflowWorker, ScriptRunnerWorker
from inspector_dialog import InspectorDialog
from audio_adder import AnkiTTSFiller

# 유틸리티 스크립트 임포트
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
try:
    from util_show_deck_stats import main as deck_stats_main
except ImportError:
    def deck_stats_main(*args, **kwargs):
        print("Deck stats script not found.")
from note_field_completor import main as field_completor_main

# ─────────────────────────────────────────────────────────
#  메인 윈도우
# ─────────────────────────────────────────────────────────

class AnkiPyQtApp(QMainWindow):
    _PAGE_TITLES = ["콘텐츠 생성", "통계 분석", "오디오 채우기", "필드 채우기"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anki Manager")
        self.resize(860, 660)
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 사이드바
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background:#f7f7f5; border-right: 1px solid #ebebea;")
        sbl = QVBoxLayout(sidebar)
        sbl.setContentsMargins(0, 0, 0, 0)
        sbl.setSpacing(0)

        ws_hdr = QWidget()
        ws_hdr.setFixedHeight(48)
        ws_hdr.setStyleSheet("border-bottom: 1px solid #ebebea;")
        whl = QHBoxLayout(ws_hdr)
        whl.setContentsMargins(14, 0, 14, 0)
        icon_box = QWidget()
        icon_box.setFixedSize(26, 26)
        icon_box.setStyleSheet("background:#37352f; border-radius:6px;")
        ibl = QHBoxLayout(icon_box)
        ibl.setContentsMargins(5, 5, 5, 5)
        ibl.addWidget(make_svg_label(ICON["grid"], 16))
        whl.addWidget(icon_box)
        wn = QLabel("Anki Manager")
        wn.setFont(QFont(".AppleSystemUIFont", 13, QFont.Weight.DemiBold))
        whl.addWidget(wn)
        whl.addStretch()
        sbl.addWidget(ws_hdr)

        nav_area = QWidget()
        nal = QVBoxLayout(nav_area)
        nal.setContentsMargins(6, 8, 6, 8)
        nal.setSpacing(1)
        self.nav_items = [
            NavItem(ICON["check_muted"], ICON["check_active"], "콘텐츠 생성"),
            NavItem(ICON["bar_chart"],   ICON["bar_chart"],    "통계 분석"),
            NavItem(ICON["audio"],       ICON["audio"],        "오디오 채우기"),
            NavItem(ICON["text_lines"],  ICON["text_lines"],   "필드 채우기"),
        ]
        for i, nav in enumerate(self.nav_items):
            nav.clicked.connect(lambda _, idx=i: self._switch(idx))
            nal.addWidget(nav)
        nal.addStretch()
        sbl.addWidget(nav_area, 1)

        bot = QWidget()
        bot.setStyleSheet("border-top: 1px solid #ebebea;")
        bl = QVBoxLayout(bot)
        bl.setContentsMargins(6, 6, 6, 10)
        self.settings_nav = NavItem(ICON["gear"], ICON["gear"], "설정")
        self.settings_nav.clicked.connect(self.open_settings)
        bl.addWidget(self.settings_nav)
        sbl.addWidget(bot)
        root.addWidget(sidebar)

        # ── 메인
        main_area = QWidget()
        mal = QVBoxLayout(main_area)
        mal.setContentsMargins(0, 0, 0, 0)
        mal.setSpacing(0)

        topbar = QWidget()
        topbar.setFixedHeight(48)
        topbar.setStyleSheet("background: #ffffff; border-bottom: 1px solid #ebebea;")
        tbl = QHBoxLayout(topbar)
        tbl.setContentsMargins(24, 0, 20, 0)
        tbl.addWidget(make_svg_label(ICON["grid_outline"], 14))
        tbl.addSpacing(5)
        ws_lbl = QLabel("Anki Manager")
        ws_lbl.setStyleSheet("color:#c8c6c1; font-size:13px;")
        tbl.addWidget(ws_lbl)
        sep = QLabel("/")
        sep.setStyleSheet("color:#d8d6d1; font-size:13px;")
        tbl.addWidget(sep)
        self.breadcrumb = QLabel("콘텐츠 생성")
        self.breadcrumb.setFont(QFont(".AppleSystemUIFont", 13, QFont.Weight.Medium))
        tbl.addWidget(self.breadcrumb)
        tbl.addStretch()
        tbl.addWidget(GhostButton(ICON["clock"], "실행 이력"))
        mal.addWidget(topbar)

        self.stack = QStackedWidget()
        self.content_page = ContentPage()
        self.content_page.run_requested.connect(self._start_workflow)
        self.stats_page  = SimplePage(ICON["pg_stats"],  "통계 분석",    "Anki 덱의 학습 통계를 분석하고 리포트를 생성합니다.")
        self.audio_page  = SimplePage(ICON["pg_audio"],  "오디오 채우기","누락된 오디오 파일을 TTS로 자동 생성하여 채웁니다.")
        self.fields_page = SimplePage(ICON["pg_fields"], "필드 채우기",  "노트의 빈 필드를 AI로 자동 완성합니다.")
        
        self.stats_page.run_requested.connect(lambda: self._start_simple(self._run_stats, self.stats_page))
        self.audio_page.run_requested.connect(lambda: self._start_simple(self._run_audio, self.audio_page))
        self.fields_page.run_requested.connect(lambda: self._start_simple(self._run_fields, self.fields_page))

        self.stack.addWidget(self.content_page)
        self.stack.addWidget(self.stats_page)
        self.stack.addWidget(self.audio_page)
        self.stack.addWidget(self.fields_page)
        
        mal.addWidget(self.stack)
        root.addWidget(main_area)
        
        self._switch(0)

    def _switch(self, idx: int):
        for i, nav in enumerate(self.nav_items):
            nav.setActive(i == idx)
        self.stack.setCurrentIndex(idx)
        self.breadcrumb.setText(self._PAGE_TITLES[idx])

    def _start_workflow(self, source, url, num_s, num_v):
        pg = self.content_page
        pg.set_running(True)
        pg.log_box.clear()
        pg.update_progress(0)
        
        self.worker = WorkflowWorker(url, source, num_s, num_v)
        self.worker.inspection_requested.connect(self._handle_inspection)
        self.worker.workflow_finished.connect(lambda: pg.set_running(False))
        self.worker.progress_updated.connect(pg.update_progress)
        self.worker.log_added.connect(pg.append_log)
        self.worker.status_changed.connect(pg.update_status)
        self.worker.start()

    def _handle_inspection(self, data):
        self.content_page.append_log("✨ 검수 창이 열렸습니다.")
        dlg = InspectorDialog(self, data)
        if dlg.exec():
            self.content_page.append_log("✔ 검수 완료 — 작업 재개")
            self.worker.resume_from_inspection(dlg.get_modified_data())
        else:
            self.content_page.append_log("❌ 작업이 중단되었습니다.")
            self.worker.terminate()


    def _start_simple(self, func, page: SimplePage):
        page.set_running(True)
        page.log_box.clear()
        page.update_progress(0)
        
        self.worker = ScriptRunnerWorker(func)
        self.worker.task_finished.connect(lambda: page.set_running(False))
        self.worker.progress_updated.connect(page.update_progress)
        self.worker.log_added.connect(page.append_log)
        self.worker.status_changed.connect(page.update_status)
        self.worker.start()

    def _run_stats(self, pbar=None):
        if pbar: pbar.set_description("덱 통계 분석 중...")
        deck_stats_main(pbar=pbar)

    def _run_audio(self, pbar=None):
        if pbar: pbar.set_description("오디오 채우는 중...")
        AnkiTTSFiller.run_audio_addition(pbar=pbar, step_points=100)

    def _run_fields(self, pbar=None):
        if pbar: pbar.set_description("필드 채우는 중...")
        field_completor_main(pbar=pbar)

    def open_settings(self):
        try:
            from settings_dialog import SettingsDialog
            SettingsDialog(self).exec()
        except ImportError:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "알림", "settings_dialog.py가 없습니다.\n같은 폴더에 배치해주세요.")

# ─────────────────────────────────────────────────────────
#  진입점
# ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    
    if 'Fusion' in QStyleFactory.keys():
        app.setStyle('Fusion')
        
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor("#37352f"))
    pal.setColor(QPalette.ColorRole.Base,            QColor("#f7f7f5"))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor("#f0efec"))
    pal.setColor(QPalette.ColorRole.Text,            QColor("#37352f"))
    pal.setColor(QPalette.ColorRole.Button,          QColor("#f7f7f5"))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor("#37352f"))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor("#2c5fbc"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)
    
    window = AnkiPyQtApp()
    window.show()
    sys.exit(app.exec())
