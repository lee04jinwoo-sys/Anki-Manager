from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QCheckBox, QPushButton
)
from PyQt6.QtGui import QFont
from ui_widgets import ThinDivider

# ─────────────────────────────────────────────────────────
#  InspectorDialog
# ─────────────────────────────────────────────────────────

class InspectorDialog(QDialog):
    def __init__(self, parent, data):
        super().__init__(parent)
        self.setWindowTitle("최종 검수")
        self.resize(680, 560)
        self.setModal(True)
        self.checkboxes = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        t = QLabel("최종 검수")
        t.setFont(QFont(".AppleSystemUIFont", 17, QFont.Weight.Bold))
        t.setStyleSheet("color:#37352f;background:transparent;")
        hdr.addWidget(t); hdr.addStretch()
        s = QLabel("체크 해제 시 Anki에 추가되지 않습니다")
        s.setStyleSheet("color:#b5b3ae;font-size:13px;background:transparent;")
        hdr.addWidget(s)
        root.addLayout(hdr)
        root.addWidget(ThinDivider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;} QWidget{background:#ffffff;}")
        inner = QWidget(); inner.setStyleSheet("background:#ffffff;")
        iv = QVBoxLayout(inner); iv.setContentsMargins(0,8,0,8); iv.setSpacing(5)

        def sec_hdr(txt):
            lbl = QLabel(txt)
            lbl.setFont(QFont(".AppleSystemUIFont",11,QFont.Weight.Medium))
            lbl.setStyleSheet("color:#37352f;background:#f7f7f5;border-radius:5px;padding:5px 10px;")
            return lbl

        def item_card(html):
            card = QWidget()
            card.setStyleSheet("QWidget{background:#ffffff;border:1px solid #ebebea;border-radius:7px;} QWidget:hover{border-color:#d8d6d1;}")
            row = QHBoxLayout(card); row.setContentsMargins(12,9,12,9)
            cb = QCheckBox(); cb.setChecked(True)
            lbl = QLabel(html); lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#37352f;font-size:13px;background:transparent;border:none;")
            row.addWidget(cb); row.addWidget(lbl,1)
            return card, cb

        if data and data.get('sentences'):
            iv.addWidget(sec_hdr("📖  문장"))
            self.checkboxes['sentences'] = []
            for item in data['sentences']:
                c, cb = item_card(f"<b>{item.get('문장','')}</b><br><span style='color:#b5b3ae'>{item.get('해설','')}</span>")
                iv.addWidget(c); self.checkboxes['sentences'].append((cb, item))
            iv.addSpacing(6)

        if data and data.get('vocab'):
            iv.addWidget(sec_hdr("📚  어휘"))
            self.checkboxes['vocab'] = []
            for item in data['vocab']:
                desc = item.get('설명',''); sd = desc[:72]+'...' if len(desc)>72 else desc
                html = (f"<b>{item.get('단어','')}</b><span style='color:#91918e'>  {item.get('뜻','')}</span><br>"
                        f"<span style='color:#c8c6c1;font-size:12px'>{sd}</span>")
                c, cb = item_card(html)
                iv.addWidget(c); self.checkboxes['vocab'].append((cb, item))

        iv.addStretch(); scroll.setWidget(inner)
        root.addWidget(scroll)
        root.addWidget(ThinDivider())
        br = QHBoxLayout(); br.addStretch()
        ok = QPushButton("확인 및 계속"); ok.setFixedHeight(38); ok.setMinimumWidth(140)
        ok.clicked.connect(self.accept); br.addWidget(ok)
        root.addLayout(br)

    def get_modified_data(self):
        return {k: [item for cb,item in v if cb.isChecked()] for k,v in self.checkboxes.items()}
