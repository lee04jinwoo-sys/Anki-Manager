from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QProgressBar, QTextEdit,
)
from PyQt6.QtCore import pyqtSignal, QDateTime
from PyQt6.QtGui import QFont, QIntValidator
from ui_widgets import (
    SectionLabel, RunButton, SourceChip
)
from ui_icons import ICON, make_svg_label

# ─────────────────────────────────────────────────────────
#  페이지 — 로그 공통 믹스인
# ─────────────────────────────────────────────────────────

def _append_log(log_box: QTextEdit, msg: str):
    msg = msg.strip()
    if not msg: return
    ts = QDateTime.currentDateTime().toString("hh:mm:ss")
    col = ("#c0392b" if msg.startswith("❌") else
           "#448361" if msg.startswith(("✔","🎉")) else
           "#b35900" if msg.startswith("⚠")       else
           "#2c5fbc" if msg.startswith(("→","ℹ")) else "#37352f")
    log_box.append(f'<span style="color:#d3d1cc;font-size:11px">{ts}</span>&nbsp;&nbsp;<span style="color:{col}">{msg}</span>')
    log_box.verticalScrollBar().setValue(log_box.verticalScrollBar().maximum())


def _build_status_log_block(parent_layout: QVBoxLayout):
    """상태바 + 로그 블록을 빌드하고 위젯 refs 반환"""
    sw = QWidget(); sw.setStyleSheet("background:transparent;"); sw.setVisible(False)
    sv = QVBoxLayout(sw); sv.setContentsMargins(0,0,0,0); sv.setSpacing(6)
    sr = QHBoxLayout()
    status_lbl = QLabel("대기 중"); status_lbl.setStyleSheet("color:#b5b3ae;font-size:13px;background:transparent;")
    pct_lbl    = QLabel("");        pct_lbl.setStyleSheet("color:#2c5fbc;font-size:13px;font-weight:600;background:transparent;")
    sr.addWidget(status_lbl); sr.addStretch(); sr.addWidget(pct_lbl)
    sv.addLayout(sr)
    pbar = QProgressBar(); pbar.setValue(0); pbar.setTextVisible(False); pbar.setFixedHeight(4)
    sv.addWidget(pbar)
    parent_layout.addWidget(sw)
    parent_layout.addSpacing(14)

    lw = QWidget(); lw.setStyleSheet("background:transparent;"); lw.setVisible(False)
    lv = QVBoxLayout(lw); lv.setContentsMargins(0,0,0,0); lv.setSpacing(7)
    lv.addWidget(SectionLabel("실행 로그"))
    log_box = QTextEdit(); log_box.setReadOnly(True); log_box.setMinimumHeight(180)
    lv.addWidget(log_box)
    parent_layout.addWidget(lw)

    return sw, status_lbl, pct_lbl, pbar, lw, log_box


# ─────────────────────────────────────────────────────────
#  ContentPage
# ─────────────────────────────────────────────────────────

class ContentPage(QWidget):
    run_requested = pyqtSignal(str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#ffffff;")
        root = QVBoxLayout(self)
        root.setContentsMargins(52, 40, 52, 32); root.setSpacing(0)

        # 타이틀
        tr = QHBoxLayout(); tr.setSpacing(10)
        tr.addWidget(make_svg_label(ICON["pg_content"], 28))
        t = QLabel("콘텐츠 생성")
        t.setFont(QFont(".AppleSystemUIFont", 26, QFont.Weight.Bold))
        t.setStyleSheet("color:#37352f;letter-spacing:-0.4px;background:transparent;")
        tr.addWidget(t); tr.addStretch()
        root.addLayout(tr)
        root.addSpacing(5)
        d = QLabel("YouTube, 웹페이지, Notion, 상황 설명으로 Anki 카드를 자동 생성합니다.")
        d.setStyleSheet("color:#b5b3ae;font-size:14px;background:transparent;")
        root.addWidget(d); root.addSpacing(28)

        # 소스 칩
        root.addWidget(SectionLabel("입력 소스")); root.addSpacing(8)
        cr = QHBoxLayout(); cr.setSpacing(6); cr.setContentsMargins(0,0,0,0)
        self.chip_url  = SourceChip(ICON["youtube_m"], ICON["youtube_a"], "YouTube / Web")
        self.chip_notion = SourceChip(ICON["notion_m"],  ICON["notion_a"],  "Notion")
        self.chip_sit  = SourceChip(ICON["bulb_m"],    ICON["bulb_a"],    "상황별 생성")
        self.chip_url.clicked.connect(lambda: self._sel("url"))
        self.chip_notion.clicked.connect(lambda: self._sel("notion"))
        self.chip_sit.clicked.connect(lambda: self._sel("situation"))
        cr.addWidget(self.chip_url); cr.addWidget(self.chip_notion); cr.addWidget(self.chip_sit); cr.addStretch()
        root.addLayout(cr); root.addSpacing(22)
        self._source = "url"; self.chip_url.setActive(True)

        # 입력 카드
        self.url_lbl = SectionLabel("URL"); root.addWidget(self.url_lbl); root.addSpacing(6)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("YouTube 영상 또는 웹페이지 주소를 입력하세요.")
        root.addWidget(self.url_input)

        self.count_w = QWidget(); self.count_w.setStyleSheet("background:transparent;border:none;")
        crl = QHBoxLayout(self.count_w); crl.setContentsMargins(0,0,0,0); crl.setSpacing(10)
        for lbl_txt, attr in [("문장 수","num_s"),("어휘 수","num_v")]:
            lb = QLabel(lbl_txt); lb.setStyleSheet("color:#91918e;font-size:13px;background:transparent;")
            crl.addWidget(lb)
            inp = QLineEdit(); inp.setValidator(QIntValidator(1,100)); inp.setPlaceholderText("10" if attr=="num_s" else "15"); inp.setFixedWidth(72)
            setattr(self, attr, inp); crl.addWidget(inp)
        crl.addStretch(); self.count_w.setVisible(False)
        root.addWidget(self.count_w)
        root.addSpacing(14)

        # 시작 버튼
        self.run_btn = RunButton(); self.run_btn.clicked.connect(self._on_run)
        root.addWidget(self.run_btn); root.addSpacing(20)

        # 상태 + 로그
        self._sw, self._status_lbl, self._pct_lbl, self.progress_bar, self._lw, self.log_box = \
            _build_status_log_block(root)
        root.addStretch()

    def _sel(self, src: str):
        self._source = src
        self.chip_url.setActive(src=="url"); self.chip_notion.setActive(src=="notion"); self.chip_sit.setActive(src=="situation")
        self.count_w.setVisible(src=="situation"); self.url_input.setEnabled(src!="notion")
        if src=="notion":   self.url_lbl.setText("URL (NOTION)"); self.url_input.setPlaceholderText("Notion 소스는 설정에서 구성됩니다.")
        elif src=="situation": self.url_lbl.setText("상황 설명"); self.url_input.setPlaceholderText("예: 식당에서 주문할 때, 회의에서 의견을 제시할 때")
        else:               self.url_lbl.setText("URL"); self.url_input.setPlaceholderText("YouTube 영상 또는 웹페이지 주소를 입력하세요.")

    def _on_run(self):
        if self._source in ("url","situation") and not self.url_input.text().strip():
            self._sw.setVisible(True); self._lw.setVisible(True)
            _append_log(self.log_box, "❌ 입력값을 채워주세요."); return
        self.run_requested.emit(self._source, self.url_input.text().strip(),
                                self.num_s.text().strip(), self.num_v.text().strip())

    def set_running(self, v: bool):
        self.run_btn.setEnabled(not v)
        self._sw.setVisible(True); self._lw.setVisible(True)
        if not v: self._pct_lbl.setText("100%")

    def append_log(self, msg): _append_log(self.log_box, msg)
    def update_status(self, msg): self._status_lbl.setText(msg)
    def update_progress(self, val):
        self.progress_bar.setValue(val); self._pct_lbl.setText(f"{val}%")


# ─────────────────────────────────────────────────────────
#  SimplePage (통계/오디오/필드)
# ─────────────────────────────────────────────────────────

class SimplePage(QWidget):
    run_requested = pyqtSignal()

    def __init__(self, pg_svg, title, desc, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#ffffff;")
        root = QVBoxLayout(self); root.setContentsMargins(52,40,52,32); root.setSpacing(0)
        tr = QHBoxLayout(); tr.setSpacing(10)
        tr.addWidget(make_svg_label(pg_svg, 28))
        t = QLabel(title); t.setFont(QFont(".AppleSystemUIFont",26,QFont.Weight.Bold))
        t.setStyleSheet("color:#37352f;letter-spacing:-0.4px;background:transparent;")
        tr.addWidget(t); tr.addStretch(); root.addLayout(tr)
        root.addSpacing(5)
        d = QLabel(desc); d.setStyleSheet("color:#b5b3ae;font-size:14px;background:transparent;")
        root.addWidget(d); root.addSpacing(28)
        self.run_btn = RunButton(); self.run_btn.clicked.connect(self.run_requested.emit)
        root.addWidget(self.run_btn); root.addSpacing(20)
        self._sw, self._status_lbl, self._pct_lbl, self.progress_bar, self._lw, self.log_box = \
            _build_status_log_block(root)
        root.addStretch()

    def set_running(self, v: bool):
        self.run_btn.setEnabled(not v)
        self._sw.setVisible(True); self._lw.setVisible(True)
        if not v: self._pct_lbl.setText("100%")

    def append_log(self, msg): _append_log(self.log_box, msg)
    def update_status(self, msg): self._status_lbl.setText(msg)
    def update_progress(self, val):
        self.progress_bar.setValue(val); self._pct_lbl.setText(f"{val}%")
