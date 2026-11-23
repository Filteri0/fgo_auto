"""主視窗：左側導覽列 + 頂部列（設定組、連線狀態）+ 四個頁面。"""
import copy
import os
import shutil
import sys

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QButtonGroup, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

import profile_store
from profile_store import DEFAULT_PROFILE, Profile, create_default, list_profiles, new_profile_key, profile_dir
from vision import ROOT

from . import theme
from .farm_tab import STATE_ZH, FarmTab
from .icons import ICON_SIZE, icon
from .script_tab import ScriptTab
from .support_tab import SupportTab
from .widgets import BotRunner

PAGES = [("farm", "周回", "repeat"), ("support", "助戰", "users"), ("script", "戰鬥腳本", "list"),
         ("settings", "設定", "settings")]


class SettingsPage(QWidget):
    """④ 設定：模擬器連線、資料夾。"""

    def __init__(self, serial: str):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)  # 跟其他頁對齊
        root.setSpacing(14)

        g = QGroupBox("模擬器連線")
        gl = QGridLayout(g)
        gl.setHorizontalSpacing(12)
        gl.addWidget(QLabel("ADB 位址"), 0, 0)
        self.serial = QLineEdit(serial)
        self.serial.setFixedWidth(220)
        gl.addWidget(self.serial, 0, 1)
        self.conn_btn = QPushButton(" 測試連線")
        self.conn_btn.setIcon(icon("refresh", theme.TEXT))
        self.conn_btn.setIconSize(ICON_SIZE)
        gl.addWidget(self.conn_btn, 0, 2)
        gl.setColumnStretch(3, 1)
        hint = QLabel("MuMu 預設是 127.0.0.1:16384。解析度要設成 1280×720。")
        hint.setObjectName("muted")
        gl.addWidget(hint, 1, 0, 1, 4)
        self.result = QLabel("")
        gl.addWidget(self.result, 2, 0, 1, 4)
        root.addWidget(g)

        g2 = QGroupBox("資料夾")
        g2l = QHBoxLayout(g2)
        self.logs_btn = QPushButton(" 開啟 logs（停止時的截圖）")
        self.prof_btn = QPushButton(" 開啟設定組資料夾")
        for b in (self.logs_btn, self.prof_btn):
            b.setIcon(icon("folder", theme.TEXT))
            b.setIconSize(ICON_SIZE)
            g2l.addWidget(b)
        g2l.addStretch(1)
        root.addWidget(g2)
        root.addStretch(1)

        self.logs_btn.clicked.connect(lambda: _open_folder(ROOT / "logs"))
        self.prof_btn.clicked.connect(lambda: _open_folder(profile_store.PROFILES_DIR))


def _open_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 —— 只開本機資料夾


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings("fgo_auto", "gui")
        self.key: str | None = None
        self.prof: Profile | None = None
        self.dirty = False
        self.runner = BotRunner()
        self.resize(1400, 880)
        self.setMinimumSize(1200, 760)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- 左側導覽列 ----
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(190)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 18, 12, 14)
        sl.setSpacing(4)
        logo = QLabel("FGO Auto")
        logo.setObjectName("logo")
        sub = QLabel("自動周回工具")
        sub.setObjectName("logoSub")
        sl.addWidget(logo)
        sl.addWidget(sub)
        sl.addSpacing(18)
        self.nav = QButtonGroup(self)
        self.nav_buttons: dict[str, QPushButton] = {}
        for i, (key, label, ic) in enumerate(PAGES):
            b = QPushButton(f"  {label}")
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setIconSize(ICON_SIZE)
            b.setProperty("icon_name", ic)
            self.nav.addButton(b, i)
            self.nav_buttons[key] = b
            sl.addWidget(b)
        sl.addStretch(1)
        self.side_status = QLabel("待命中")
        self.side_status.setObjectName("sideStatus")
        self.side_status.setWordWrap(True)
        sl.addWidget(self.side_status)
        outer.addWidget(side)

        # ---- 右側內容 ----
        content = QWidget()
        content.setObjectName("content")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(22, 16, 22, 18)
        cl.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.page_title = QLabel("")
        self.page_title.setObjectName("pageTitle")
        top.addWidget(self.page_title)
        top.addStretch(1)
        top.addWidget(QLabel("設定組"))
        self.profile_box = QComboBox()
        self.profile_box.setMinimumWidth(230)
        top.addWidget(self.profile_box)
        self.save_btn = QPushButton(" 儲存")
        self.save_btn.setIconSize(ICON_SIZE)
        top.addWidget(self.save_btn)
        self.more_btn = QPushButton()
        self.more_btn.setObjectName("icon")
        self.more_btn.setIcon(icon("dots", theme.TEXT))
        self.more_btn.setIconSize(ICON_SIZE)
        self.more_btn.setToolTip("新增 / 另存 / 重新命名 / 刪除設定組")
        menu = QMenu(self)
        menu.addAction("新增設定組…", self.new_profile)
        menu.addAction("另存成新的設定組…", self.duplicate_profile)
        menu.addAction("重新命名…", self.rename_profile)
        menu.addSeparator()
        menu.addAction("刪除這個設定組", self.delete_profile)
        self.more_btn.setMenu(menu)
        top.addWidget(self.more_btn)
        top.addSpacing(8)
        self.conn_pill = QLabel("")
        self.conn_pill.setObjectName("pill")
        top.addWidget(self.conn_pill)
        cl.addLayout(top)

        self.stack = QStackedWidget()
        self.farm = FarmTab()
        self.settings_page = SettingsPage(self.settings.value("serial", "127.0.0.1:16384"))
        self.serial = self.settings_page.serial
        self.conn_btn = self.settings_page.conn_btn
        self.support = SupportTab(lambda: self.serial.text().strip())
        self.script = ScriptTab()
        for w in (self.farm, self.support, self.script, self.settings_page):
            self.stack.addWidget(w)
        cl.addWidget(self.stack, 1)
        outer.addWidget(content, 1)

        # ---- signals ----
        self.nav.idClicked.connect(self.show_page)
        for tab in (self.farm, self.support, self.script):
            tab.changed.connect(self._mark_dirty)
        self.profile_box.activated.connect(self._switch_profile)
        self.save_btn.clicked.connect(self.save)
        self.conn_btn.clicked.connect(self.test_connection)
        self.serial.editingFinished.connect(lambda: self.settings.setValue("serial", self.serial.text().strip()))
        self.farm.start_requested.connect(self.start)
        self.farm.stop_requested.connect(self.stop)
        self.runner.log.connect(self.farm.append_log)
        self.runner.finished.connect(self._finished)
        self.side_timer = QTimer(self)
        self.side_timer.timeout.connect(self._update_side_status)

        self._set_conn("idle")
        if not profile_dir(DEFAULT_PROFILE).exists():
            create_default()
        self._reload_profiles(self.settings.value("profile", DEFAULT_PROFILE))
        self.show_page(0)

    # ---- 導覽 ----
    def show_page(self, idx: int):
        self.stack.setCurrentIndex(idx)
        self.page_title.setText(PAGES[idx][1])
        for i, (_, _, ic) in enumerate(PAGES):
            b = self.nav.button(i)
            b.setChecked(i == idx)
            b.setIcon(icon(ic, theme.ACCENT_TEXT if i == idx else theme.MUTED))

    def _set_conn(self, state: str, text: str = ""):
        color, label = {
            "idle": (theme.DIM, "未測試連線"),
            "ok": (theme.GREEN, text or "已連線"),
            "bad": (theme.RED, "連不上模擬器"),
            "running": (theme.ACCENT_TEXT, "周回中"),
        }[state]
        self.conn_pill.setText(f"<span style='color:{color}'>●</span>&nbsp; {label}")

    # ---- 設定組 ----
    def _reload_profiles(self, select: str | None = None):
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        for key, name in list_profiles():
            self.profile_box.addItem(name, key)
        self.profile_box.blockSignals(False)
        idx = self.profile_box.findData(select)
        self.profile_box.setCurrentIndex(max(0, idx))
        self._load(self.profile_box.currentData())

    def _load(self, key: str):
        try:
            prof = Profile.load(profile_dir(key))
        except Exception as e:
            QMessageBox.warning(self, "讀取失敗", f"設定組「{key}」讀取失敗：{e}")
            return
        self.key, self.prof = key, prof
        for tab in (self.farm, self.support, self.script):
            tab.load(prof)
        self.settings.setValue("profile", key)
        self._set_dirty(False)

    def _collect(self) -> Profile:
        prof = copy.deepcopy(self.prof)
        for tab in (self.farm, self.support, self.script):
            tab.apply(prof)
        return prof

    def _mark_dirty(self):
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool):
        self.dirty = dirty
        name = self.prof.name if self.prof else ""
        self.setWindowTitle(f"FGO 自動周回 — {name}{'  ●未儲存' if dirty else ''}")
        self.save_btn.setText(" 儲存 ●" if dirty else " 儲存")
        self.save_btn.setObjectName("dirty" if dirty else "")
        self.save_btn.setIcon(icon("save", "white" if dirty else theme.TEXT))
        self.save_btn.style().unpolish(self.save_btn)
        self.save_btn.style().polish(self.save_btn)

    def save(self) -> bool:
        prof = self._collect()
        try:
            prof.save(profile_dir(self.key))
        except ValueError as e:
            QMessageBox.warning(self, "無法儲存", str(e))
            return False
        self.prof = prof
        self._set_dirty(False)
        self.farm.append_log(f"已儲存設定組「{prof.name}」")
        return True

    def _confirm_discard(self) -> bool:
        """有未儲存的修改時問一下。回傳 False = 取消動作。"""
        if not self.dirty:
            return True
        r = QMessageBox.question(self, "還沒儲存", f"「{self.prof.name}」有修改還沒儲存，要先儲存嗎？",
                                 QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                                 | QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            return self.save()
        return r == QMessageBox.StandardButton.Discard

    def _switch_profile(self, idx: int):
        key = self.profile_box.itemData(idx)
        if key == self.key:
            return
        if not self._confirm_discard():
            self.profile_box.setCurrentIndex(self.profile_box.findData(self.key))
            return
        self._load(key)

    def new_profile(self):
        if not self._confirm_discard():
            return
        name, ok = QInputDialog.getText(self, "新增設定組", "名稱（例如：火種本、活動 90++）：")
        if not ok or not name.strip():
            return
        key = new_profile_key()
        Profile(name=name.strip()).save(profile_dir(key))
        self._reload_profiles(key)

    def duplicate_profile(self):
        name, ok = QInputDialog.getText(self, "另存新的設定組", "新設定組的名稱：", text=f"{self.prof.name} 複本")
        if not ok or not name.strip():
            return
        prof = self._collect()
        prof.name = name.strip()
        key = new_profile_key()
        try:
            prof.save(profile_dir(key))
        except ValueError as e:
            QMessageBox.warning(self, "無法儲存", str(e))
            return
        self.dirty = False
        self._reload_profiles(key)

    def rename_profile(self):
        name, ok = QInputDialog.getText(self, "重新命名", "新的名稱：", text=self.prof.name)
        if ok and name.strip():
            self.prof.name = name.strip()
            self._mark_dirty()
            self.profile_box.setItemText(self.profile_box.currentIndex(), self.prof.name)

    def delete_profile(self):
        if self.profile_box.count() <= 1:
            QMessageBox.information(self, "刪除設定組", "至少要留一個設定組。")
            return
        r = QMessageBox.warning(self, "刪除設定組", f"確定要刪除「{self.prof.name}」？\n裡面的助戰條件圖也會一起刪掉，無法復原。",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        shutil.rmtree(profile_dir(self.key))
        self.dirty = False
        self._reload_profiles()

    # ---- 連線 / 執行 ----
    def test_connection(self):
        from device import Device
        from states import detect_state
        self.settings_page.result.setText("連線中…")
        QApplication.processEvents()
        try:
            img = Device(self.serial.text().strip()).screenshot()
            state = detect_state(img)
        except Exception as e:
            self._set_conn("bad")
            self.settings_page.result.setText(f"<span style='color:{theme.RED}'>連不上模擬器：{e}</span>")
        else:
            label = STATE_ZH.get(state, state)
            self._set_conn("ok", f"已連線 · {label}")
            self.settings_page.result.setText(f"<span style='color:{theme.GREEN}'>已連線，遊戲目前在：{label}</span>")
            self.farm.preview.set_image(img)

    def start(self):
        prof = self._collect()
        try:
            prof.validate()
        except ValueError as e:
            QMessageBox.warning(self, "設定有問題", str(e))
            return
        if self.dirty and not self.save():
            return
        self.farm.log_view.clear()
        self.farm.append_log(f"設定組：{prof.name}　助戰條件：{prof.support.describe()}")
        self.runner.start(prof.to_config(), self.serial.text().strip())
        self._set_running(True)

    def stop(self):
        self.farm.append_log("停止中…（會做完目前這一步）")
        self.runner.stop()

    def _finished(self):
        self._set_running(False)

    def _set_running(self, running: bool):
        self.farm.set_running(running, self.runner)
        for w in (self.profile_box, self.save_btn, self.more_btn, self.serial, self.conn_btn):
            w.setEnabled(not running)
        self.support.setEnabled(not running)
        self.script.setEnabled(not running)
        if running:
            self._set_conn("running")
            self.side_timer.start(1000)
        else:
            self.side_timer.stop()
            self._set_conn("idle")
        self._update_side_status()

    def _update_side_status(self):
        bot = self.runner.bot
        if not self.runner.running or bot is None:
            self.side_status.setText("待命中")
            return
        s = bot.status()
        self.side_status.setText(f"<span style='color:{theme.ACCENT_TEXT}'>●</span> 周回中<br>"
                                 f"完成 {s['runs_done']} 場 · 蘋果 {s['apples_used']}")

    def closeEvent(self, e):
        if self.runner.running:
            r = QMessageBox.question(self, "周回中", "周回還在進行，要停止並關閉嗎？")
            if r != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            self.runner.stop()
        if not self._confirm_discard():
            e.ignore()
            return
        e.accept()


def make_app(argv=None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft JhengHei UI", 10))
    app.setStyleSheet(theme.QSS)
    return app


def main():
    app = make_app()
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
