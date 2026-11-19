"""深色主題，重點色用金色。"""

GOLD = "#e3b95b"
GOLD_DIM = "#8a6f35"
BG = "#121722"
PANEL = "#1a2130"
PANEL_2 = "#222b3d"
BORDER = "#2c3750"
TEXT = "#e7eaf0"
MUTED = "#8d97aa"
GREEN = "#4cc38a"
RED = "#e0605a"
BLUE = "#5b9cf0"
PURPLE = "#b48cf2"

QSS = f"""
* {{
    font-family: "Microsoft JhengHei UI", "Segoe UI", sans-serif;
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ background: transparent; }}
QDialog, QMenu, QMessageBox, QInputDialog {{ background: {PANEL}; }}

QTabWidget::pane {{
    border: 1px solid {BORDER}; border-radius: 10px; background: {PANEL}; top: -1px;
}}
QTabBar::tab {{
    background: {BG}; color: {MUTED}; padding: 9px 22px; margin-right: 4px;
    border: 1px solid {BORDER}; border-bottom: none;
    border-top-left-radius: 9px; border-top-right-radius: 9px;
    font-size: 10.5pt;
}}
QTabBar::tab:selected {{ background: {PANEL}; color: {GOLD}; font-weight: bold; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

QGroupBox {{
    background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 10px;
    margin-top: 16px; padding: 14px 12px 12px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: {GOLD}; font-weight: bold; font-size: 10.5pt;
}}

QPushButton {{
    background: #2a3550; border: 1px solid #3a4868; border-radius: 7px;
    padding: 6px 14px; min-height: 18px;
}}
QPushButton:hover {{ background: #33416a; border-color: #4a5c88; }}
QPushButton:pressed {{ background: #24304a; }}
QPushButton:disabled {{ color: #5a6478; background: #1f2738; border-color: #2a3346; }}
QPushButton#primary {{
    background: {GOLD}; color: #1d1608; border: none; font-weight: bold; font-size: 11pt;
    padding: 9px 26px;
}}
QPushButton#primary:hover {{ background: #f0c96c; }}
QPushButton#primary:disabled {{ background: {GOLD_DIM}; color: #3a2f18; }}
QPushButton#danger {{ background: #8e3a37; border: none; font-weight: bold; padding: 9px 26px; font-size: 11pt; }}
QPushButton#danger:hover {{ background: #a8463f; }}
QPushButton#danger:disabled {{ background: #3a2727; color: #6b5555; }}
QPushButton#skill {{ padding: 7px 4px; min-width: 64px; }}
QPushButton#skill:checked {{ background: {GOLD}; color: #1d1608; border-color: {GOLD}; font-weight: bold; }}
QPushButton#np {{ background: #5a2a30; border-color: #7a3a40; font-weight: bold; }}
QPushButton#np:hover {{ background: #6e343b; }}
QPushButton#master {{ background: #3c2f5e; border-color: #54417f; }}
QPushButton#master:hover {{ background: #4a3a73; }}
QPushButton#flat {{ background: transparent; border: none; color: {MUTED}; padding: 4px 8px; }}
QPushButton#flat:hover {{ color: {GOLD}; }}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QListWidget {{
    background: #0e121a; border: 1px solid #303c56; border-radius: 7px; padding: 5px 7px;
    selection-background-color: #3b4c74;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QListWidget:focus {{ border-color: {GOLD_DIM}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {BORDER}; selection-background-color: #34405c; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; }}
QPlainTextEdit {{ font-family: "Cascadia Mono", "Consolas", "Microsoft JhengHei UI"; font-size: 9.5pt; }}

QListWidget::item {{ padding: 7px 8px; margin: 2px 0; border-radius: 6px; background: #19202e; }}
QListWidget::item:selected {{ background: #34405c; color: {TEXT}; }}
QListWidget::item:hover:!selected {{ background: #222b3d; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 17px; height: 17px; border-radius: 4px; border: 1px solid #45547a; background: #0e121a; }}
QCheckBox::indicator:checked {{ background: {GOLD}; border-color: {GOLD}; }}
QCheckBox:disabled {{ color: #5a6478; }}

QLabel#muted {{ color: {MUTED}; }}
QLabel#title {{ color: {GOLD}; font-size: 15pt; font-weight: bold; }}
QLabel#statValue {{ font-size: 16pt; font-weight: bold; color: {TEXT}; }}
QLabel#statLabel {{ color: {MUTED}; font-size: 9pt; }}
QLabel#badgeOk {{ color: {GREEN}; font-weight: bold; }}
QLabel#badgeBad {{ color: {RED}; font-weight: bold; }}
QLabel#warn {{ color: {RED}; }}
QLabel#thumb {{ background: #0e121a; border: 1px solid #303c56; border-radius: 5px; }}
QFrame#card {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#topbar {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #34405c; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
"""
