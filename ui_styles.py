STYLESHEET = """
QMainWindow, QDialog { background-color: #ffffff; }
QWidget {
    font-family: "Pretendard", ".AppleSystemUIFont", -apple-system,
                 BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    color: #37352f; font-size: 14px; background-color: transparent;
}
QLabel { color: #37352f; background: transparent; }
QLineEdit {
    background-color: #f7f7f5; border: 1.5px solid transparent;
    border-radius: 7px; padding: 9px 13px; color: #37352f; font-size: 14px;
    selection-background-color: #dbeafe;
}
QLineEdit:hover { background-color: #f0efec; }
QLineEdit:focus { background-color: #ffffff; border: 1.5px solid #b3cdfb; }
QLineEdit:disabled { background-color: #f7f7f5; color: #c8c6c1; }
QPushButton {
    background-color: #37352f; color: #ffffff; border: none;
    border-radius: 7px; padding: 9px 18px; font-size: 14px; font-weight: 600;
}
QPushButton:hover { background-color: #1e1d1b; }
QPushButton:pressed { background-color: #111110; }
QPushButton:disabled { background-color: #efefed; color: #c8c6c1; }
QProgressBar {
    border: none; border-radius: 2px; background-color: #f0efec;
    height: 4px; color: transparent; font-size: 1px;
}
QProgressBar::chunk { background-color: #37352f; border-radius: 2px; }
QTextEdit {
    background-color: #fafaf9; border: 1px solid #ebebea; border-radius: 8px;
    padding: 12px 14px; color: #37352f;
    font-family: "JetBrains Mono","Fira Code","SF Mono",Menlo,"Courier New",monospace;
    font-size: 12.5px; selection-background-color: #dbeafe;
}
QScrollBar:vertical { background: transparent; width: 5px; margin: 0; }
QScrollBar::handle:vertical { background: #d8d6d1; border-radius: 2px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #b5b3ae; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 5px; background: transparent; }
QScrollBar::handle:horizontal { background: #d8d6d1; border-radius: 2px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QCheckBox { spacing: 10px; color: #37352f; font-size: 13px; }
QCheckBox::indicator {
    width: 15px; height: 15px; border-radius: 4px;
    border: 1.5px solid #d8d6d1; background: #ffffff;
}
QCheckBox::indicator:hover { border-color: #b3cdfb; }
QCheckBox::indicator:checked { background-color: #2c5fbc; border-color: #2c5fbc; }
"""
