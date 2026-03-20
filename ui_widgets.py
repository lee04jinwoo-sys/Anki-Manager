from PyQt6.QtWidgets import QLabel, QFrame, QPushButton
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import QSize

from ui_icons import ICON, svg_icon

# ─────────────────────────────────────────────────────────
#  커스텀 위젯
# ─────────────────────────────────────────────────────────

class SectionLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text.upper(), parent)
        self.setFont(QFont(".AppleSystemUIFont", 10, QFont.Weight.Medium))
        self.setStyleSheet("color: #b5b3ae; letter-spacing: 0.7px; background: transparent;")


class ThinDivider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet("background: #ebebea; border: none;")


class NavItem(QPushButton):
    def __init__(self, svg_m: str, svg_a: str, label: str, parent=None):
        super().__init__(parent)
        self._svg_m, self._svg_a, self._label = svg_m, svg_a, label
        self._active = False
        self.setFixedHeight(32)
        self._refresh()

    def setActive(self, v: bool):
        self._active = v
        self._refresh()

    def _refresh(self):
        self.setIcon(svg_icon(self._svg_a if self._active else self._svg_m, 16))
        self.setIconSize(QSize(16, 16))
        self.setText(f"  {self._label}")
        if self._active:
            self.setStyleSheet("""QPushButton {
                background: #ebebea; color: #37352f; border: none; border-radius: 6px;
                font-size: 13.5px; font-weight: 500; padding: 0 10px; text-align: left;
            }""")
        else:
            self.setStyleSheet("""QPushButton {
                background: transparent; color: #91918e; border: none; border-radius: 6px;
                font-size: 13.5px; font-weight: 400; padding: 0 10px; text-align: left;
            }
            QPushButton:hover { background: #efefed; color: #37352f; }""")


class SourceChip(QPushButton):
    def __init__(self, svg_m: str, svg_a: str, label: str, parent=None):
        super().__init__(parent)
        self._svg_m, self._svg_a, self._label = svg_m, svg_a, label
        self._active = False
        self.setFixedHeight(30)
        self._refresh()

    def setActive(self, v: bool):
        self._active = v
        self._refresh()

    def _refresh(self):
        self.setIcon(svg_icon(self._svg_a if self._active else self._svg_m, 13))
        self.setIconSize(QSize(13, 13))
        self.setText(f"  {self._label}")
        if self._active:
            self.setStyleSheet("""QPushButton {
                background: #e8f0fe; border: 1px solid #b3cdfb; border-radius: 15px;
                color: #2c5fbc; font-size: 13px; font-weight: 600; padding: 0 13px; text-align: left;
            }""")
        else:
            self.setStyleSheet("""QPushButton {
                background: #ffffff; border: 1px solid #e3e1dc; border-radius: 15px;
                color: #91918e; font-size: 13px; font-weight: 500; padding: 0 13px; text-align: left;
            }
            QPushButton:hover { background: #f7f7f5; color: #37352f; border-color: #d3d1cc; }""")


class GhostButton(QPushButton):
    def __init__(self, svg_str: str, label: str, parent=None):
        super().__init__(parent)
        self.setIcon(svg_icon(svg_str, 14))
        self.setIconSize(QSize(14, 14))
        self.setText(f"  {label}")
        self.setFixedHeight(30)
        self.setStyleSheet("""QPushButton {
            background: transparent; color: #91918e; border: 1px solid #e3e1dc;
            border-radius: 6px; font-size: 13px; font-weight: 400; padding: 0 11px; text-align: left;
        }
        QPushButton:hover { background: #f7f7f5; color: #37352f; border-color: #d3d1cc; }""")


class RunButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._set_idle()

    def _set_idle(self):
        self.setIcon(svg_icon(ICON["play_white"], 13))
        self.setIconSize(QSize(13, 13))
        self.setText("  시작")
        self.setStyleSheet("""QPushButton {
            background: #37352f; color: #ffffff; border: none; border-radius: 8px;
            font-size: 14px; font-weight: 600; padding: 0 20px;
        }
        QPushButton:hover { background: #1e1d1b; }
        QPushButton:pressed { background: #111110; }""")

    def setEnabled(self, v: bool):
        super().setEnabled(v)
        if not v:
            self.setIcon(QIcon())
            self.setText("처리 중...")
            self.setStyleSheet("""QPushButton {
                background: #efefed; color: #c8c6c1; border: none;
                border-radius: 8px; font-size: 14px; font-weight: 600; padding: 0 20px;
            }""")
        else:
            self._set_idle()

