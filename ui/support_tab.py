"""② 助戰：在支援列表截圖上點一列，勾選要比對的欄位。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

import support as S
from support import FIELD_ZH, SupportSpec
from vision import ROOT, imread

from . import theme
from .widgets import ScreenView, Thumb

FIELD_ORDER = ["player", "servant", "np", "level", "ce"]
FIELD_HINT = {
    "player": "只要這位玩家的",
    "servant": "只看從者是誰",
    "np": "寶具名稱 + 寶具等級（等於也限定了從者）",
    "level": "從者等級，例如 Lv.120/120",
    "ce": "帶的禮裝（不管從者是誰）",
}
CLASS_CHOICES = [("不切換頁籤", None), ("全職階", "all"), ("劍 Saber", "saber"), ("弓 Archer", "archer"),
                 ("槍 Lancer", "lancer"), ("騎 Rider", "rider"), ("術 Caster", "caster"),
                 ("殺 Assassin", "assassin"), ("狂 Berserker", "berserker"), ("特殊職階", "extra"),
                 ("混合 MIX", "mix")]
ROW_X = (-228, 929)  # 一列的左右緣（相對「從者」標籤中心）


class SupportTab(QWidget):
    changed = Signal()

    def __init__(self, get_serial):
        super().__init__()
        self.get_serial = get_serial
        self._loading = False
        self.shot = None
        self.rows: list[tuple[int, int]] = []
        self.sel_row = None
        self.templates: dict = {}   # 目前的條件圖（欄位 → 圖）
        self.candidate: dict = {}   # 選取那一列切出來的圖
        self.match_result: dict = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ---- 左：截圖 ----
        left = QVBoxLayout()
        left.setSpacing(10)
        bar = QHBoxLayout()
        self.capture_btn = QPushButton("擷取模擬器畫面")
        self.open_btn = QPushButton("開啟截圖檔…")
        self.test_btn = QPushButton("測試比對")
        bar.addWidget(self.capture_btn)
        bar.addWidget(self.open_btn)
        bar.addStretch(1)
        bar.addWidget(self.test_btn)
        left.addLayout(bar)
        self.hint = QLabel("先把遊戲停在「支援選擇」畫面，按「擷取模擬器畫面」，再點想要的助戰那一列。")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        left.addWidget(self.hint)
        self.view = ScreenView("還沒有截圖")
        left.addWidget(self.view, 1)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        left.addWidget(self.result_label)
        root.addLayout(left, 1)

        # ---- 右：條件 ----
        right = QVBoxLayout()
        right.setSpacing(12)
        g = QGroupBox("比對條件（勾選的都要符合）")
        gl = QGridLayout(g)
        gl.setVerticalSpacing(10)
        self.checks: dict[str, QCheckBox] = {}
        self.thumbs: dict[str, Thumb] = {}
        for i, f in enumerate(FIELD_ORDER):
            cb = QCheckBox(FIELD_ZH[f])
            cb.setToolTip(FIELD_HINT[f])
            th = Thumb(170, 34)
            self.checks[f], self.thumbs[f] = cb, th
            gl.addWidget(cb, i, 0)
            gl.addWidget(th, i, 1)
            cb.toggled.connect(self._toggled)
        i = len(FIELD_ORDER)
        self.mlb = QCheckBox(FIELD_ZH["mlb"])
        self.mlb.setToolTip("禮裝右下角要有滿破的星星標記")
        self.mlb_state = QLabel("")
        self.mlb_state.setObjectName("muted")
        gl.addWidget(self.mlb, i, 0)
        gl.addWidget(self.mlb_state, i, 1)
        self.mlb.toggled.connect(self._emit_changed)
        right.addWidget(g)

        g2 = QGroupBox("搜尋方式")
        g2l = QGridLayout(g2)
        g2l.addWidget(QLabel("職階頁籤"), 0, 0)
        self.class_tab = QComboBox()
        for name, key in CLASS_CHOICES:
            self.class_tab.addItem(name, key)
        g2l.addWidget(self.class_tab, 0, 1)
        g2l.addWidget(QLabel("找不到時列表更新"), 1, 0)
        self.max_refresh = QSpinBox()
        self.max_refresh.setRange(0, 200)
        self.max_refresh.setSuffix(" 次")
        g2l.addWidget(self.max_refresh, 1, 1)
        right.addWidget(g2)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("muted")
        right.addWidget(self.summary)
        right.addStretch(1)
        wrap = QWidget()
        wrap.setLayout(right)
        wrap.setFixedWidth(380)
        root.addWidget(wrap)

        self.capture_btn.clicked.connect(self.capture)
        self.open_btn.clicked.connect(self.open_file)
        self.test_btn.clicked.connect(self.test_match)
        self.view.clicked.connect(self._clicked)
        self.class_tab.currentIndexChanged.connect(self._emit_changed)
        self.max_refresh.valueChanged.connect(self._emit_changed)

    # ---- 設定組 ↔ 介面 ----
    def _emit_changed(self, *_):
        self._update_summary()
        if not self._loading:
            self.changed.emit()

    def load(self, prof):
        self._loading = True
        spec = prof.support
        self.templates = dict(spec.templates)
        self.candidate = {}
        self.match_result = {}
        for f in FIELD_ORDER:
            self.checks[f].setChecked(f in self.templates)
            self.thumbs[f].set_bgr(self.templates.get(f))
        self.mlb.setChecked(spec.mlb)
        idx = max(0, self.class_tab.findData(spec.class_tab))
        self.class_tab.setCurrentIndex(idx)
        self.max_refresh.setValue(prof.support_max_refresh)
        self._loading = False
        self._refresh_enabled()
        self._redraw()
        self._update_summary()

    def current_spec(self) -> SupportSpec:
        tpls = {f: self.templates[f] for f in FIELD_ORDER if self.checks[f].isChecked() and f in self.templates}
        return SupportSpec(tpls, self.mlb.isChecked(), self.class_tab.currentData())

    def apply(self, prof):
        prof.support = self.current_spec()
        prof.support_max_refresh = self.max_refresh.value()

    # ---- 截圖 ----
    def capture(self):
        from device import Device
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            img = Device(self.get_serial()).screenshot()
        except Exception as e:
            QMessageBox.warning(self, "擷取失敗", f"連不上模擬器：{e}")
            return
        finally:
            self.unsetCursor()
        self.set_shot(img)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "開啟截圖", str(ROOT / "screenshots"), "圖片 (*.png *.jpg)")
        if path:
            self.set_shot(imread(path))

    def set_shot(self, img):
        self.shot = img
        self.view.set_image(img)
        self.rows = S.find_rows(img)
        self.sel_row = None
        self.match_result = {}
        if not self.rows:
            self.hint.setText("這張截圖找不到支援列表（要在「支援選擇」畫面，而且沒有對話框擋住）。")
        else:
            self.hint.setText(f"找到 {len(self.rows)} 列完整的助戰。點想要的那一列，右邊會切出各欄位。")
        self._redraw()

    def _clicked(self, x, y):
        for r in self.rows:
            if r[1] + S.ROW_TOP <= y <= r[1] + S.ROW_BOTTOM:
                self.select_row(r)
                return

    def select_row(self, row):
        self.sel_row = row
        self.candidate = {f: S.crop_field(self.shot, row, f) for f in FIELD_ORDER}
        # 選了新的一列 = 要換成這個助戰：已勾選的欄位改用這一列的圖
        for f in FIELD_ORDER:
            if self.checks[f].isChecked() or f not in self.templates:
                self.templates[f] = self.candidate[f]
            self.thumbs[f].set_bgr(self.templates[f])
        mlb = S.mlb_score(self.shot, row) >= S.MLB_THRESHOLD
        self.mlb_state.setText("這一列：滿破" if mlb else "這一列：沒滿破 / 沒禮裝")
        self._refresh_enabled()
        self._redraw()
        self._emit_changed()

    def _toggled(self, on):
        if on:
            for f, cb in self.checks.items():
                if cb is self.sender() and f not in self.templates and f in self.candidate:
                    self.templates[f] = self.candidate[f]
                    self.thumbs[f].set_bgr(self.templates[f])
        self._emit_changed()

    def _refresh_enabled(self):
        for f in FIELD_ORDER:
            self.checks[f].setEnabled(f in self.templates or f in self.candidate)

    # ---- 測試比對 ----
    def test_match(self):
        if self.shot is None:
            QMessageBox.information(self, "測試比對", "先擷取或開啟一張支援選擇的截圖。")
            return
        spec = self.current_spec()
        self.match_result = {r: S.row_matches(self.shot, r, spec) for r in self.rows}
        n = sum(self.match_result.values())
        details = []
        for i, r in enumerate(self.rows, 1):
            sc = S.row_scores(self.shot, r, spec)
            bad = [f"{FIELD_ZH[k]} {v:.2f}" for k, v in sc.items()
                   if v < (S.MLB_THRESHOLD if k == "mlb" else S.THRESHOLD)]
            details.append(f"第 {i} 列：" + ("符合" if not bad else "不符：" + "、".join(bad)))
        color = theme.GREEN if n else theme.RED
        self.result_label.setText(f"<span style='color:{color};font-weight:bold'>"
                                  f"這張截圖有 {n} 列符合條件</span><br>" + "<br>".join(details))
        self._redraw()

    def _redraw(self):
        ov = []
        for r in self.rows:
            box = (r[0] + ROW_X[0], r[1] + S.ROW_TOP + 4, r[0] + ROW_X[1], r[1] + S.ROW_BOTTOM - 4)
            if r in self.match_result:
                ok = self.match_result[r]
                ov.append((box, theme.GREEN if ok else theme.RED, 3, "符合" if ok else ""))
            elif r == self.sel_row:
                ov.append((box, theme.GOLD, 3, "已選取"))
            else:
                ov.append((box, "#5b6b8f", 1, ""))
        if self.sel_row is not None:
            for f in FIELD_ORDER:
                ov.append((S.field_box(self.sel_row, f), theme.GOLD if self.checks[f].isChecked() else "#7a869e", 1, ""))
        self.view.set_overlays(ov)

    def _update_summary(self):
        self.summary.setText("目前條件：" + self.current_spec().describe())
