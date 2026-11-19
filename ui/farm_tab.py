"""① 周回：場數、蘋果、開始 / 停止、即時狀態、畫面預覽、log。"""
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout,
                               QWidget)

from bot import APPLE_ZH, APPLES

from .widgets import ScreenView, stat_card

STATE_ZH = {
    None: "認不出畫面（動畫 / 讀取中）", "quest_select": "選關畫面（等你點進關卡）", "ap_recover": "AP 恢復",
    "apple_confirm": "吃蘋果確認", "support_select": "選擇助戰", "party_confirm": "隊伍確認",
    "battle_command": "戰鬥：下指令", "card_select": "戰鬥：選卡", "skill_target": "戰鬥：選技能目標",
    "result_tap": "結算", "result_next": "結算（下一步）", "continue_sortie": "連續出擊",
    "cc_detail": "紋章 / 禮裝詳細頁", "wipe_out": "全滅", "refresh_confirm": "列表更新確認",
    "refresh_cooldown": "列表更新冷卻中",
}


class FarmTab(QWidget):
    changed = Signal()
    start_requested = Signal()
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self._loading = False
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ---- 左欄：設定 + 開始 ----
        left = QVBoxLayout()
        left.setSpacing(12)

        g_runs = QGroupBox("周回")
        gl = QGridLayout(g_runs)
        gl.addWidget(QLabel("場數"), 0, 0)
        self.runs = QSpinBox()
        self.runs.setRange(0, 9999)
        self.runs.setSpecialValueText("無限")
        self.runs.setSuffix(" 場")
        gl.addWidget(self.runs, 0, 1)
        hint = QLabel("0 = 無限，直到 AP 和蘋果用完")
        hint.setObjectName("muted")
        gl.addWidget(hint, 1, 0, 1, 2)
        left.addWidget(g_runs)

        g_apple = QGroupBox("自動吃蘋果")
        al = QVBoxLayout(g_apple)
        row = QHBoxLayout()
        row.addWidget(QLabel("最多吃"))
        self.max_apples = QSpinBox()
        self.max_apples.setRange(0, 999)
        self.max_apples.setSuffix(" 顆")
        self.max_apples.setSpecialValueText("不吃")
        row.addWidget(self.max_apples, 1)
        al.addLayout(row)
        cap = QLabel("勾選可以吃的果實，拖曳調整優先順序（上面先吃）")
        cap.setObjectName("muted")
        cap.setWordWrap(True)
        al.addWidget(cap)
        self.apple_list = QListWidget()
        self.apple_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.apple_list.setFixedHeight(4 * 40 + 8)
        al.addWidget(self.apple_list)
        sq = QLabel("🔒 聖晶石永遠不會吃")
        sq.setObjectName("muted")
        al.addWidget(sq)
        left.addWidget(g_apple)

        left.addStretch(1)
        btns = QHBoxLayout()
        self.start_btn = QPushButton("▶  開始周回")
        self.start_btn.setObjectName("primary")
        self.stop_btn = QPushButton("■  停止")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        btns.addWidget(self.start_btn, 2)
        btns.addWidget(self.stop_btn, 1)
        left.addLayout(btns)
        root.addLayout(left, 0)

        # ---- 右欄：狀態 + 預覽 + log ----
        right = QVBoxLayout()
        right.setSpacing(12)
        stats = QHBoxLayout()
        stats.setSpacing(10)
        c1, self.v_runs = stat_card("完成場數")
        c2, self.v_apples = stat_card("已吃蘋果")
        c3, self.v_wave = stat_card("目前波次")
        c4, self.v_time = stat_card("已執行")
        for c in (c1, c2, c3, c4):
            stats.addWidget(c, 1)
        right.addLayout(stats)

        self.state_label = QLabel("尚未開始")
        self.state_label.setObjectName("muted")
        right.addWidget(self.state_label)

        self.preview = ScreenView("開始周回後這裡會顯示模擬器畫面")
        right.addWidget(self.preview, 3)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3000)
        self.log_view.setPlaceholderText("log 會顯示在這裡")
        right.addWidget(self.log_view, 2)
        root.addLayout(right, 1)

        # ---- signals ----
        self.runs.valueChanged.connect(self._emit_changed)
        self.max_apples.valueChanged.connect(self._emit_changed)
        self.apple_list.itemChanged.connect(self._emit_changed)
        self.apple_list.model().rowsMoved.connect(self._emit_changed)
        self.start_btn.clicked.connect(self.start_requested)
        self.stop_btn.clicked.connect(self.stop_requested)

        self.runner = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)

    # ---- 設定組 ↔ 介面 ----
    def _emit_changed(self, *_):
        if not self._loading:
            self.changed.emit()

    def load(self, prof):
        self._loading = True
        self.runs.setValue(prof.runs or 0)
        self.max_apples.setValue(prof.max_apples)
        self.apple_list.clear()
        order = list(prof.apples) + [a for a in APPLES if a not in prof.apples]
        for a in order:
            it = QListWidgetItem(APPLE_ZH[a])
            it.setData(Qt.ItemDataRole.UserRole, a)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsDragEnabled)
            it.setCheckState(Qt.CheckState.Checked if a in prof.apples else Qt.CheckState.Unchecked)
            self.apple_list.addItem(it)
        self._loading = False

    def apply(self, prof):
        prof.runs = self.runs.value() or None
        prof.max_apples = self.max_apples.value()
        prof.apples = [self.apple_list.item(i).data(Qt.ItemDataRole.UserRole)
                       for i in range(self.apple_list.count())
                       if self.apple_list.item(i).checkState() == Qt.CheckState.Checked]

    # ---- 執行狀態 ----
    def set_running(self, running: bool, runner=None):
        self.runner = runner if running else self.runner
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        for w in (self.runs, self.max_apples, self.apple_list):
            w.setEnabled(not running)
        if running:
            self.timer.start(500)
        else:
            self.timer.stop()
            self._refresh_status()
            self.state_label.setText("已停止")

    def append_log(self, line: str):
        self.log_view.appendPlainText(line)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _refresh_status(self):
        r = self.runner
        if r is None or r.bot is None:
            return
        s = r.bot.status()
        total = s["runs"]
        self.v_runs.setText(f"{s['runs_done']}" + (f" / {total}" if total else ""))
        self.v_apples.setText(f"{s['apples_used']} / {s['max_apples']}")
        self.v_wave.setText(f"{s['wave']} / 3" if s["wave"] and s["state"] in (
            "battle_command", "card_select", "skill_target") else "—")
        secs = int(time.monotonic() - r.started_at)
        self.v_time.setText(f"{secs // 3600:d}:{secs // 60 % 60:02d}:{secs % 60:02d}")
        if r.running:
            self.state_label.setText("目前畫面：" + STATE_ZH.get(s["state"], s["state"] or "—"))
        img = r.bot.img
        if img is not None:
            self.preview.set_image(img)
