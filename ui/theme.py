"""深色主題：近黑的鋅灰底 + 紫色重點色（側邊欄儀表板風格）。"""

# 底色（由深到淺）
BG_DEEP = "#0f0f12"     # 截圖檢視、輸入框
SIDEBAR = "#131316"
BG = "#18181b"          # 主內容區
CARD = "#1f1f23"
CARD_2 = "#26262b"      # 卡片裡的小方塊、清單項目
BORDER = "#2f2f35"
BORDER_STRONG = "#3f3f46"

TEXT = "#f4f4f5"
MUTED = "#a1a1aa"
DIM = "#71717a"

ACCENT = "#8b5cf6"
ACCENT_HOVER = "#9d74f7"
ACCENT_SOFT = "#2e2a45"  # 選取的導覽項、選取的清單項
ACCENT_TEXT = "#c4b5fd"

GREEN = "#4ade80"
RED = "#f87171"
AMBER = "#fbbf24"        # 御主技能
CORAL = "#fb8a72"        # 寶具

QSS = f"""
* {{
    font-family: "Microsoft JhengHei UI", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, QWidget#root, QWidget#content {{ background: {BG}; }}
QWidget {{ background: transparent; }}
QDialog, QMessageBox, QInputDialog {{ background: {CARD}; }}

/* ---- 側邊欄 ---- */
QFrame#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QLabel#logo {{ color: {ACCENT_TEXT}; font-size: 15pt; font-weight: bold; padding: 4px 6px; }}
QLabel#logoSub {{ color: {DIM}; font-size: 8.5pt; padding: 0 6px; }}
QPushButton#nav {{
    background: transparent; border: none; border-radius: 8px;
    color: {MUTED}; text-align: left; padding: 9px 12px; font-size: 10.5pt;
}}
QPushButton#nav:hover {{ background: #1c1c21; color: {TEXT}; }}
QPushButton#nav:checked {{ background: {ACCENT_SOFT}; color: {ACCENT_TEXT}; font-weight: bold; }}
QLabel#sideStatus {{ color: {MUTED}; font-size: 9pt; padding: 8px 10px;
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; }}

/* ---- 頂部列 ---- */
QLabel#pageTitle {{ font-size: 15pt; font-weight: bold; }}
QLabel#pill {{ border: 1px solid {BORDER}; border-radius: 11px; padding: 3px 11px; font-size: 9pt; background: {CARD}; }}

/* ---- 卡片（QGroupBox 的標題放在卡片裡面） ---- */
QGroupBox {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
    margin-top: 0; padding: 34px 14px 14px 14px;
}}
QGroupBox::title {{
    subcontrol-origin: padding; subcontrol-position: top left;
    left: 14px; top: 11px; color: {TEXT}; font-weight: bold; font-size: 10.5pt;
}}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px; }}

/* ---- 按鈕 ---- */
QPushButton {{
    background: {CARD_2}; border: 1px solid {BORDER_STRONG}; border-radius: 8px;
    padding: 6px 14px; min-height: 18px;
}}
QPushButton:hover {{ background: #303036; border-color: #52525b; }}
QPushButton:pressed {{ background: #222227; }}
QPushButton:disabled {{ color: #52525b; background: #1b1b1f; border-color: #27272a; }}
QPushButton#primary {{
    background: {ACCENT}; color: white; border: none; font-weight: bold; font-size: 11pt; padding: 9px 24px;
}}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: #3b3260; color: #8a83a8; }}
QPushButton#danger {{ background: #3a1f22; border: 1px solid #5c2b30; color: {RED}; font-weight: bold;
    font-size: 11pt; padding: 9px 24px; }}
QPushButton#danger:hover {{ background: #4a2529; }}
QPushButton#danger:disabled {{ background: #1b1b1f; border-color: #27272a; color: #52525b; }}
QPushButton#dirty {{ background: {ACCENT}; color: white; border: none; font-weight: bold; }}
QPushButton#dirty:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#icon {{ padding: 6px 8px; min-width: 18px; }}
QPushButton#skill {{ padding: 8px 4px; min-width: 64px; }}
QPushButton#skill:checked {{ background: {ACCENT_SOFT}; color: {ACCENT_TEXT}; border-color: {ACCENT}; font-weight: bold; }}
QPushButton#np {{ background: #3a2320; border-color: #5c3530; color: {CORAL}; font-weight: bold; }}
QPushButton#np:hover {{ background: #4a2b27; }}
QPushButton#master {{ background: #33291a; border-color: #574321; color: {AMBER}; }}
QPushButton#master:hover {{ background: #40331f; }}
QPushButton#flat {{ background: transparent; border: none; color: {MUTED}; padding: 4px 8px; }}
QPushButton#flat:hover {{ color: {ACCENT_TEXT}; }}
QPushButton::menu-indicator {{ image: none; width: 0; }}

/* ---- 輸入元件 ---- */
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QListWidget {{
    background: {BG_DEEP}; border: 1px solid {BORDER_STRONG}; border-radius: 8px; padding: 5px 8px;
    selection-background-color: #4c3d8a;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QListWidget:focus, QPlainTextEdit:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_SOFT}; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; }}
QPlainTextEdit {{ font-family: "Cascadia Mono", "Consolas", "Microsoft JhengHei UI"; font-size: 9.5pt; color: #d4d4d8; }}

QListWidget::item {{ padding: 7px 9px; margin: 2px 0; border-radius: 7px; background: {CARD_2}; }}
QListWidget::item:selected {{ background: {ACCENT_SOFT}; color: {TEXT}; }}
QListWidget::item:hover:!selected {{ background: #2c2c32; }}
QListWidget::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid #52525b; background: {BG_DEEP}; }}
QListWidget::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 17px; height: 17px; border-radius: 5px; border: 1px solid #52525b; background: {BG_DEEP}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox:disabled {{ color: #52525b; }}

QMenu {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT_SOFT}; color: {ACCENT_TEXT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}

/* ---- 文字 ---- */
QLabel#muted {{ color: {MUTED}; }}
QLabel#statValue {{ font-size: 18pt; font-weight: bold; }}
QLabel#statLabel {{ color: {MUTED}; font-size: 9pt; }}
QLabel#warn {{ color: {RED}; }}
QLabel#thumb {{ background: {BG_DEEP}; border: 1px solid {BORDER_STRONG}; border-radius: 6px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3f3f46; border-radius: 4px; min-height: 24px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #3f3f46; border-radius: 4px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QToolTip {{ background: {CARD_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
"""
