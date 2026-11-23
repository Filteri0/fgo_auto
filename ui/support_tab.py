"""② 助戰：條件用文字 / 數字（OCR 比對），禮裝用圖片。在截圖上點一列會自動填入。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

import support as S
from support import SupportSpec
from vision import ROOT, imread

from . import theme
from .icons import ICON_SIZE, icon
from .widgets import ScreenView, Thumb

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
        self.rows: list = []
        self.sel_row = None
        self.ce_img = None          # 禮裝條件圖（目前的）
        self.match_result: dict = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ---- 左：截圖 ----
        left = QVBoxLayout()
        left.setSpacing(10)
        bar = QHBoxLayout()
        self.capture_btn = QPushButton(" 擷取模擬器畫面")
        self.open_btn = QPushButton(" 開啟截圖檔…")
        self.test_btn = QPushButton(" 測試比對")
        for b, ic in ((self.capture_btn, "camera"), (self.open_btn, "photo"), (self.test_btn, "check")):
            b.setIcon(icon(ic, theme.TEXT))
            b.setIconSize(ICON_SIZE)
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
        gl.setColumnStretch(1, 1)

        self.cb_player = QCheckBox("玩家名稱")
        self.player = QLineEdit()
        self.player.setPlaceholderText("例如 VOYOV")
        self.cb_servant = QCheckBox("從者")
        self.servant = QLineEdit()
        self.servant.setPlaceholderText("例如 摩根")
        self.cb_level = QCheckBox("從者等級至少")
        self.level = QSpinBox()
        self.level.setRange(1, 120)
        self.level.setPrefix("Lv. ")
        self.cb_np = QCheckBox("寶具等級至少")
        self.np = QSpinBox()
        self.np.setRange(1, 5)
        self.np.setPrefix("Lv. ")
        self.cb_ce = QCheckBox("禮裝")
        self.ce_thumb = Thumb(170, 34)
        self.cb_mlb = QCheckBox("禮裝滿破")
        self.mlb_state = QLabel("")
        self.mlb_state.setObjectName("muted")
        self.pairs = [(self.cb_player, self.player), (self.cb_servant, self.servant), (self.cb_level, self.level),
                      (self.cb_np, self.np), (self.cb_ce, self.ce_thumb), (self.cb_mlb, self.mlb_state)]
        for i, (cb, w) in enumerate(self.pairs):
            gl.addWidget(cb, i, 0)
            gl.addWidget(w, i, 1)
        tip = QLabel("文字用 OCR 讀，名字容許讀錯一個字；等級、寶具是「至少」。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        gl.addWidget(tip, len(self.pairs), 0, 1, 2)
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

        # ---- signals ----
        self.capture_btn.clicked.connect(self.capture)
        self.open_btn.clicked.connect(self.open_file)
        self.test_btn.clicked.connect(self.test_match)
        self.view.clicked.connect(self._clicked)
        for cb, _ in self.pairs:
            cb.toggled.connect(self._emit_changed)
        self.player.textChanged.connect(self._emit_changed)
        self.servant.textChanged.connect(self._emit_changed)
        self.level.valueChanged.connect(self._emit_changed)
        self.np.valueChanged.connect(self._emit_changed)
        self.class_tab.currentIndexChanged.connect(self._emit_changed)
        self.max_refresh.valueChanged.connect(self._emit_changed)

    # ---- 設定組 ↔ 介面 ----
    def _emit_changed(self, *_):
        self._refresh_enabled()
        self._update_summary()
        if not self._loading:
            self.changed.emit()

    def load(self, prof):
        self._loading = True
        s = prof.support
        self.player.setText(s.player)
        self.servant.setText(s.servant)
        self.level.setValue(s.min_level or 120)
        self.np.setValue(s.min_np or 5)
        self.ce_img = s.ce
        self.ce_thumb.set_bgr(s.ce)
        self.cb_player.setChecked(bool(s.player))
        self.cb_servant.setChecked(bool(s.servant))
        self.cb_level.setChecked(bool(s.min_level))
        self.cb_np.setChecked(bool(s.min_np))
        self.cb_ce.setChecked(s.ce is not None)
        self.cb_mlb.setChecked(s.mlb)
        self.mlb_state.setText("")
        self.class_tab.setCurrentIndex(max(0, self.class_tab.findData(s.class_tab)))
        self.max_refresh.setValue(prof.support_max_refresh)
        self.match_result = {}
        self._loading = False
        self._refresh_enabled()
        self._redraw()
        self._update_summary()

    def current_spec(self) -> SupportSpec:
        return SupportSpec(
            player=self.player.text().strip() if self.cb_player.isChecked() else "",
            servant=self.servant.text().strip() if self.cb_servant.isChecked() else "",
            min_level=self.level.value() if self.cb_level.isChecked() else 0,
            min_np=self.np.value() if self.cb_np.isChecked() else 0,
            ce=self.ce_img if self.cb_ce.isChecked() else None,
            mlb=self.cb_mlb.isChecked(),
            class_tab=self.class_tab.currentData(),
        )

    def apply(self, prof):
        prof.support = self.current_spec()
        prof.support_max_refresh = self.max_refresh.value()

    def _refresh_enabled(self):
        for cb, w in self.pairs[:4]:
            w.setEnabled(cb.isChecked())
        self.cb_ce.setEnabled(self.ce_img is not None)

    def _update_summary(self):
        self.summary.setText("目前條件：" + self.current_spec().describe())

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
        self.result_label.setText("")
        if not self.rows:
            self.hint.setText("這張截圖找不到支援列表（要在「支援選擇」畫面，而且沒有對話框擋住）。")
        else:
            self.hint.setText(f"找到 {len(self.rows)} 列完整的助戰。點想要的那一列，會自動填入讀到的名稱和等級。")
        self._redraw()

    def _clicked(self, x, y):
        for r in self.rows:
            if r.y + S.ROW_TOP + r.portrait_dy <= y <= r.y + S.ROW_BOTTOM + r.portrait_dy:
                self.select_row(r)
                return

    def select_row(self, row):
        """點一列：OCR 讀出文字填進條件（勾選狀態不變），禮裝換成這一列的。"""
        self.sel_row = row
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            info = S.read_row(self.shot, row)
        finally:
            self.unsetCursor()
        self._loading = True
        self.player.setText(info["player"])
        self.servant.setText(info["servant"])
        if info["level"]:
            self.level.setValue(min(120, info["level"]))
        if info["np"]:
            self.np.setValue(min(5, info["np"]))
        self.ce_img = S.crop_field(self.shot, row, "ce")
        self.ce_thumb.set_bgr(self.ce_img)
        self._loading = False
        mlb = S.mlb_score(self.shot, row) >= S.MLB_THRESHOLD
        self.mlb_state.setText("這一列：滿破" if mlb else "這一列：沒滿破 / 沒禮裝")
        lv = f"Lv.{info['level']}" if info["level"] else "等級讀不到"
        np_ = f"寶具 Lv.{info['np']}" if info["np"] else "寶具等級讀不到"
        self.hint.setText(f"這一列讀到：{info['player'] or '（玩家讀不到）'}　{info['servant'] or '（從者讀不到）'}"
                          f"　{lv}　{np_}。勾選要用的條件後按「測試比對」確認。")
        self._redraw()
        self._emit_changed()

    # ---- 測試比對 ----
    def test_match(self):
        if self.shot is None:
            QMessageBox.information(self, "測試比對", "先擷取或開啟一張支援選擇的截圖。")
            return
        spec = self.current_spec()
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            checks = {r: S.check_row(self.shot, r, spec, stop_early=False) for r in self.rows}
        finally:
            self.unsetCursor()
        self.match_result = {r: all(ok for _, ok, _ in c) for r, c in checks.items()}
        n = sum(self.match_result.values())
        lines = []
        for i, r in enumerate(self.rows, 1):
            c = checks[r]
            parts = "　".join(
                f"<span style='color:{theme.GREEN if ok else theme.RED}'>{k} {v}</span>" for k, ok, v in c)
            verdict = "符合" if self.match_result[r] else "不符"
            lines.append(f"第 {i} 列：{verdict}　{parts or '（沒有條件）'}")
        color = theme.GREEN if n else theme.RED
        self.result_label.setText(f"<span style='color:{color};font-weight:bold'>這張截圖有 {n} 列符合條件</span>"
                                  "<br>" + "<br>".join(lines))
        self._redraw()

    def _redraw(self):
        ov = []
        for r in self.rows:
            top, bottom = r.y + S.ROW_TOP + r.portrait_dy, r.y + S.ROW_BOTTOM + r.portrait_dy  # 沒簡介的列整體偏下
            box = (r.x + ROW_X[0], top + 4, r.x + ROW_X[1], bottom - 4)
            if r in self.match_result:
                ok = self.match_result[r]
                ov.append((box, theme.GREEN if ok else theme.RED, 3, "符合" if ok else ""))
            elif r == self.sel_row:
                ov.append((box, theme.ACCENT, 3, "已選取"))
            else:
                ov.append((box, theme.DIM, 1, ""))
        if self.sel_row is not None:
            for f in ("player", "servant", "np", "level", "ce", "mlb"):
                ov.append((S.field_box(self.sel_row, f), theme.ACCENT_TEXT, 1, ""))
        self.view.set_overlays(ov)
