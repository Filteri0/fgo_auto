"""主視窗：設定組管理 + 三個分頁 + 開始 / 停止。"""
import copy
import shutil
import sys

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from profile_store import (DEFAULT_PROFILE, Profile, create_default, list_profiles, new_profile_key,
                           profile_dir)

from . import theme
from .farm_tab import STATE_ZH, FarmTab
from .script_tab import ScriptTab
from .support_tab import SupportTab
from .widgets import BotRunner


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None):
        super().__init__()
        self.settings = settings or QSettings("fgo_auto", "gui")
        self.key: str | None = None
        self.prof: Profile | None = None
        self.dirty = False
        self.runner = BotRunner()
        self.resize(1360, 860)
        self.setMinimumSize(1180, 760)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(12)

        # ---- 頂部列 ----
        top = QFrame()
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(14, 10, 14, 10)
        tl.setSpacing(8)
        title = QLabel("FGO 自動周回")
        title.setObjectName("title")
        tl.addWidget(title)
        tl.addSpacing(16)
        tl.addWidget(QLabel("設定組"))
        self.profile_box = QComboBox()
        self.profile_box.setMinimumWidth(240)
        tl.addWidget(self.profile_box)
        self.save_btn = QPushButton("儲存")
        self.new_btn = QPushButton("新增")
        self.dup_btn = QPushButton("另存新的")
        self.rename_btn = QPushButton("重新命名")
        self.del_btn = QPushButton("刪除")
        self.del_btn.setObjectName("flat")
        for b in (self.save_btn, self.new_btn, self.dup_btn, self.rename_btn, self.del_btn):
            tl.addWidget(b)
        tl.addStretch(1)
        tl.addWidget(QLabel("模擬器 ADB"))
        self.serial = QLineEdit(self.settings.value("serial", "127.0.0.1:16384"))
        self.serial.setFixedWidth(150)
        tl.addWidget(self.serial)
        self.conn_btn = QPushButton("測試連線")
        tl.addWidget(self.conn_btn)
        self.conn_state = QLabel("")
        tl.addWidget(self.conn_state)
        lay.addWidget(top)

        # ---- 分頁 ----
        self.tabs = QTabWidget()
        self.farm = FarmTab()
        self.support = SupportTab(lambda: self.serial.text().strip())
        self.script = ScriptTab()
        self.tabs.addTab(self.farm, "①  周回")
        self.tabs.addTab(self.support, "②  助戰")
        self.tabs.addTab(self.script, "③  戰鬥腳本")
        lay.addWidget(self.tabs, 1)

        # ---- signals ----
        for tab in (self.farm, self.support, self.script):
            tab.changed.connect(self._mark_dirty)
        self.profile_box.activated.connect(self._switch_profile)
        self.save_btn.clicked.connect(self.save)
        self.new_btn.clicked.connect(self.new_profile)
        self.dup_btn.clicked.connect(self.duplicate_profile)
        self.rename_btn.clicked.connect(self.rename_profile)
        self.del_btn.clicked.connect(self.delete_profile)
        self.conn_btn.clicked.connect(self.test_connection)
        self.serial.editingFinished.connect(lambda: self.settings.setValue("serial", self.serial.text().strip()))
        self.farm.start_requested.connect(self.start)
        self.farm.stop_requested.connect(self.stop)
        self.runner.log.connect(self.farm.append_log)
        self.runner.finished.connect(self._finished)

        if not profile_dir(DEFAULT_PROFILE).exists():
            create_default()
        self._reload_profiles(self.settings.value("profile", DEFAULT_PROFILE))

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
        self.save_btn.setText("儲存 ●" if dirty else "儲存")
        self.save_btn.setObjectName("primary" if dirty else "")
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
        self.conn_state.setText("連線中…")
        QApplication.processEvents()
        try:
            img = Device(self.serial.text().strip()).screenshot()
            state = detect_state(img)
        except Exception as e:
            self.conn_state.setObjectName("badgeBad")
            self.conn_state.setText("連不上")
            self.conn_state.setToolTip(str(e))
        else:
            self.conn_state.setObjectName("badgeOk")
            self.conn_state.setText(f"已連線：{STATE_ZH.get(state, state)}")
            self.conn_state.setToolTip("")
            self.farm.preview.set_image(img)
        self.conn_state.style().unpolish(self.conn_state)
        self.conn_state.style().polish(self.conn_state)

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
        for w in (self.profile_box, self.new_btn, self.dup_btn, self.rename_btn, self.del_btn, self.save_btn,
                  self.serial, self.conn_btn):
            w.setEnabled(not running)
        self.support.setEnabled(not running)
        self.script.setEnabled(not running)

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
