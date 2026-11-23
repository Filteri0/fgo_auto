"""線條圖示（自己畫的 SVG，不另外裝圖示套件）。"""
from PySide6.QtCore import QByteArray, QSize
from PySide6.QtGui import QIcon, QPixmap

from . import theme

# 24x24 viewBox，線條風格
PATHS = {
    "repeat": "M4 12v-3a3 3 0 0 1 3-3h13m-3-3l3 3l-3 3M20 12v3a3 3 0 0 1-3 3H4m3 3l-3-3l3-3",
    "users": ("M9 7m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"
              "M16 3.13a4 4 0 0 1 0 7.75M21 21v-2a4 4 0 0 0-3-3.85"),
    "list": "M9 6h11M9 12h11M9 18h11M5 6v.01M5 12v.01M5 18v.01",
    "settings": "M4 6h8M16 6h4M14 4v4M4 12h2M10 12h10M8 10v4M4 18h11M19 18h1M17 16v4",
    "camera": ("M5 7h1a2 2 0 0 0 2-2a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1a2 2 0 0 0 2 2h1a2 2 0 0 1 2 2v9"
               "a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2M12 13m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0"),
    "folder": "M5 4h4l3 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2",
    "check": "M5 12l5 5L20 7",
    "refresh": "M20 11a8.1 8.1 0 0 0-15.5-2m-.5-4v4h4M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4",
    "save": "M6 4h10l4 4v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2M12 14m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M14 4v4H8V4",
    "dots": ("M5 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0"
             "M19 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0-2 0"),
    "trash": "M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3",
    "photo": ("M15 8h.01M3 6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z"
              "M3 16l5-5c.93-.9 2.07-.9 3 0l5 5M14 14l1-1c.93-.9 2.07-.9 3 0l3 3"),
}
FILLED = {
    "play": "M7 4v16l13-8z",
    "stop": "M6 6h12v12H6z",
}


def icon(name: str, color: str = theme.MUTED, size: int = 18) -> QIcon:
    if name in FILLED:
        body = f'<path d="{FILLED[name]}" fill="{color}" stroke="{color}" stroke-width="1.5" stroke-linejoin="round"/>'
    else:
        body = (f'<path d="{PATHS[name]}" fill="none" stroke="{color}" stroke-width="2" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
    px = size * 3  # 高解析度，縮小時比較銳利
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 24 24">'
           f'{body}</svg>')
    pix = QPixmap()
    pix.loadFromData(QByteArray(svg.encode()), "SVG")
    ic = QIcon(pix)
    return ic


ICON_SIZE = QSize(18, 18)
