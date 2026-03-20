from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtSvg import QSvgRenderer


# ─────────────────────────────────────────────────────────
#  SVG 헬퍼
# ─────────────────────────────────────────────────────────

def svg_icon(svg_str: str, size: int = 16) -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg_str.encode()))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

def make_svg_label(svg_str: str, size: int = 16) -> QLabel:
    lbl = QLabel()
    renderer = QSvgRenderer(QByteArray(svg_str.encode()))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    lbl.setPixmap(pixmap)
    lbl.setFixedSize(size, size)
    return lbl

# ─────────────────────────────────────────────────────────
#  SVG 아이콘
# ─────────────────────────────────────────────────────────

ICON = {
    "grid": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="5" height="5" rx="1" fill="white" opacity="0.9"/><rect x="9" y="2" width="5" height="5" rx="1" fill="white" opacity="0.9"/><rect x="2" y="9" width="5" height="5" rx="1" fill="white" opacity="0.9"/><rect x="9" y="9" width="5" height="5" rx="1" fill="white" opacity="0.4"/></svg>',
    "grid_outline": '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="5" height="5" rx="1" stroke="#c8c6c1" stroke-width="1.4"/><rect x="9" y="2" width="5" height="5" rx="1" stroke="#c8c6c1" stroke-width="1.4"/><rect x="2" y="9" width="5" height="5" rx="1" stroke="#c8c6c1" stroke-width="1.4"/><rect x="9" y="9" width="5" height="5" rx="1" stroke="#c8c6c1" stroke-width="1.4"/></svg>',
    "check_active": '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 8L6.5 11.5L13 4.5" stroke="#37352f" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "check_muted":  '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 8L6.5 11.5L13 4.5" stroke="#a8a6a1" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "bar_chart":    '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="9" width="3" height="5" rx="1" stroke="#a8a6a1" stroke-width="1.4"/><rect x="6.5" y="6" width="3" height="8" rx="1" stroke="#a8a6a1" stroke-width="1.4"/><rect x="11" y="3" width="3" height="11" rx="1" stroke="#a8a6a1" stroke-width="1.4"/></svg>',
    "audio":        '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 5.5h2.5l3-3v11l-3-3H2V5.5z" stroke="#a8a6a1" stroke-width="1.4" stroke-linejoin="round"/><path d="M11 5c1.5 1 1.5 5 0 6" stroke="#a8a6a1" stroke-width="1.4" stroke-linecap="round"/><path d="M13 3.5c2.5 2 2.5 7 0 9" stroke="#a8a6a1" stroke-width="1.4" stroke-linecap="round"/></svg>',
    "text_lines":   '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 4h10M3 8h7M3 12h5" stroke="#a8a6a1" stroke-width="1.4" stroke-linecap="round"/><circle cx="13" cy="11.5" r="2" stroke="#a8a6a1" stroke-width="1.3"/><path d="M14.5 13L15.5 14" stroke="#a8a6a1" stroke-width="1.3" stroke-linecap="round"/></svg>',
    "gear":         '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="8" cy="8" r="2" stroke="#a8a6a1" stroke-width="1.4"/><path d="M8 1.5v1.8M8 12.7v1.8M1.5 8h1.8M12.7 8h1.8M3.4 3.4l1.3 1.3M11.3 11.3l1.3 1.3M3.4 12.6l1.3-1.3M11.3 4.7l1.3-1.3" stroke="#a8a6a1" stroke-width="1.4" stroke-linecap="round"/></svg>',
    "clock":        '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="8" cy="8" r="5.5" stroke="#a8a6a1" stroke-width="1.4"/><path d="M8 5.5v3l1.5 1.5" stroke="#a8a6a1" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "play_white":   '<svg width="13" height="13" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 2.5l9 4.5-9 4.5V2.5z" fill="white"/></svg>',
    "youtube_m":    '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="12" height="12" rx="2.5" stroke="#a8a6a1" stroke-width="1.4"/><path d="M6.5 10.5l5-2.5-5-2.5v5z" fill="#a8a6a1"/></svg>',
    "youtube_a":    '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="2" width="12" height="12" rx="2.5" stroke="#2c5fbc" stroke-width="1.4"/><path d="M6.5 10.5l5-2.5-5-2.5v5z" fill="#2c5fbc"/></svg>',
    "notion_m":     '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="10" height="10" rx="2" stroke="#a8a6a1" stroke-width="1.4"/><path d="M6 6.5h4M6 9.5h2.5" stroke="#a8a6a1" stroke-width="1.3" stroke-linecap="round"/></svg>',
    "notion_a":     '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="3" width="10" height="10" rx="2" stroke="#2c5fbc" stroke-width="1.4"/><path d="M6 6.5h4M6 9.5h2.5" stroke="#2c5fbc" stroke-width="1.3" stroke-linecap="round"/></svg>',
    "bulb_m":       '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="8" cy="7" r="4" stroke="#a8a6a1" stroke-width="1.4"/><path d="M6 13h4M8 11v2" stroke="#a8a6a1" stroke-width="1.4" stroke-linecap="round"/></svg>',
    "bulb_a":       '<svg width="13" height="13" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="8" cy="7" r="4" stroke="#2c5fbc" stroke-width="1.4"/><path d="M6 13h4M8 11v2" stroke="#2c5fbc" stroke-width="1.4" stroke-linecap="round"/></svg>',
    "pg_content":   '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="28" height="28" rx="7" fill="#f0efec"/><path d="M9 14l4 4L19 9" stroke="#37352f" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "pg_stats":     '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="28" height="28" rx="7" fill="#f0efec"/><rect x="7" y="17" width="4" height="6" rx="1" stroke="#37352f" stroke-width="1.6"/><rect x="12" y="13" width="4" height="10" rx="1" stroke="#37352f" stroke-width="1.6"/><rect x="17" y="9" width="4" height="14" rx="1" stroke="#37352f" stroke-width="1.6"/></svg>',
    "pg_audio": '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="28" height="28" rx="7" fill="#f0efec"/><path d="M6 10.5h4l5-5v17l-5-5H6V10.5z" stroke="#37352f" stroke-width="1.6" stroke-linejoin="round"/><path d="M18 9.5c2.5 1.8 2.5 8.2 0 10" stroke="#37352f" stroke-width="1.6" stroke-linecap="round"/><path d="M21 7c3.5 3 3.5 11 0 14" stroke="#37352f" stroke-width="1.6" stroke-linecap="round"/></svg>',    "pg_fields":    '<svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="28" height="28" rx="7" fill="#f0efec"/><path d="M8 10h12M8 14h9M8 18h6" stroke="#37352f" stroke-width="1.6" stroke-linecap="round"/></svg>',
}
