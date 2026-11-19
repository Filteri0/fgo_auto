"""③ 戰鬥腳本：點技能格把動作加到某一波，拖曳排序。"""
from itertools import permutations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
                               QVBoxLayout, QWidget)

from battle import parse_action

from . import theme

CARD_ZH = {"B": "Buster", "A": "Arts", "Q": "Quick"}
PRIORITIES = ["".join(p) for p in permutations("BAQ")]


def describe(action: str, party: list[str]) -> str:
    a = parse_action(action)
    tgt = f"  →  {party[a.target - 1]}" if a.target else ""
    if a.kind == "skill":
        return f"{party[a.servant - 1]}　技能 {a.index}{tgt}"
    if a.kind == "master":
        return f"御主技能 {a.index}{tgt}"
    return f"{party[a.servant - 1]}　寶具"


def color_of(action: str) -> str:
    k = parse_action(action).kind
    return {"skill": theme.TEXT, "master": theme.PURPLE, "np": "#ff8f7a"}[k]


class ScriptTab(QWidget):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # ---- 隊伍名字 ----
        g_party = QGroupBox("隊伍（名字只用來顯示，方便看懂腳本）")
        pl = QHBoxLayout(g_party)
        self.party_edits = []
        for i in range(3):
            pl.addWidget(QLabel(f"{i + 1} 號位"))
            e = QLineEdit()
            e.setPlaceholderText(f"{i + 1}號位")
            e.textChanged.connect(self._party_changed)
            pl.addWidget(e, 1)
            self.party_edits.append(e)
        root.addWidget(g_party)

        body = QHBoxLayout()
        body.setSpacing(14)

        # ---- 左：技能格 ----
        g_pal = QGroupBox("點選加入動作")
        pal = QVBoxLayout(g_pal)
        wave_row = QHBoxLayout()
        wave_row.addWidget(QLabel("加到"))
        self.wave_group = QButtonGroup(self)
        for w in (1, 2, 3):
            b = QPushButton(f"第 {w} 波")
            b.setCheckable(True)
            b.setObjectName("skill")
            self.wave_group.addButton(b, w)
            wave_row.addWidget(b)
        self.wave_group.button(1).setChecked(True)
        pal.addLayout(wave_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self.headers = []
        for s in (1, 2, 3):
            h = QLabel()
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h.setStyleSheet(f"color:{theme.GOLD};font-weight:bold")
            self.headers.append(h)
            grid.addWidget(h, 0, s - 1)
            for i in (1, 2, 3):
                b = QPushButton(f"技能 {i}")
                b.setObjectName("skill")
                b.clicked.connect(lambda _=False, s=s, i=i, b=b: self._skill_menu(f"s{s}-{i}", b))
                grid.addWidget(b, i, s - 1)
            nb = QPushButton("寶具")
            nb.setObjectName("np")
            nb.clicked.connect(lambda _=False, s=s: self._add(f"np{s}"))
            grid.addWidget(nb, 4, s - 1)
        pal.addLayout(grid)
        ml = QLabel("御主技能")
        ml.setStyleSheet(f"color:{theme.PURPLE};font-weight:bold;margin-top:8px")
        pal.addWidget(ml)
        mrow = QHBoxLayout()
        for i in (1, 2, 3):
            b = QPushButton(f"技能 {i}")
            b.setObjectName("master")
            b.clicked.connect(lambda _=False, i=i, b=b: self._skill_menu(f"m{i}", b))
            mrow.addWidget(b)
        pal.addLayout(mrow)
        tip = QLabel("技能需要選目標時，會跳出選單讓你挑；選「自動」就給這一波要開寶具的人。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        pal.addWidget(tip)
        pal.addStretch(1)
        g_pal.setFixedWidth(360)
        body.addWidget(g_pal)

        # ---- 右：三波 ----
        self.lists: dict[int, QListWidget] = {}
        for w in (1, 2, 3):
            g = QGroupBox(f"第 {w} 波")
            gl = QVBoxLayout(g)
            lw = QListWidget()
            lw.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            lw.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            lw.model().rowsMoved.connect(self._emit_changed)
            lw.itemPressed.connect(lambda _=None, w=w: self.wave_group.button(w).setChecked(True))
            gl.addWidget(lw, 1)
            row = QHBoxLayout()
            d = QPushButton("刪除選取")
            d.clicked.connect(lambda _=False, w=w: self._delete(w))
            c = QPushButton("清空")
            c.setObjectName("flat")
            c.clicked.connect(lambda _=False, w=w: self._clear(w))
            row.addWidget(d)
            row.addStretch(1)
            row.addWidget(c)
            gl.addLayout(row)
            self.lists[w] = lw
            body.addWidget(g, 1)
        root.addLayout(body, 1)

        # ---- 底：其他 ----
        g_misc = QGroupBox("出卡與補刀")
        ml2 = QHBoxLayout(g_misc)
        ml2.addWidget(QLabel("普通卡優先順序"))
        self.priority = QComboBox()
        for p in PRIORITIES:
            self.priority.addItem(" > ".join(CARD_ZH[c] for c in p), p)
        self.priority.currentIndexChanged.connect(self._emit_changed)
        ml2.addWidget(self.priority)
        ml2.addSpacing(20)
        self.fallback = QCheckBox("腳本跑完還沒打死（補刀回合）：NP 滿就放寶具")
        self.fallback.toggled.connect(self._emit_changed)
        ml2.addWidget(self.fallback)
        ml2.addStretch(1)
        root.addWidget(g_misc)
        self.warn = QLabel("")
        self.warn.setObjectName("warn")
        root.addWidget(self.warn)

    # ---- 動作 ----
    def party(self) -> list[str]:
        return [e.text().strip() or f"{i + 1}號位" for i, e in enumerate(self.party_edits)]

    def _skill_menu(self, base: str, button):
        party = self.party()
        menu = QMenu(self)
        menu.addAction("自動（不指定目標）", lambda: self._add(base))
        menu.addSeparator()
        for t in (1, 2, 3):
            menu.addAction(f"目標：{party[t - 1]}", lambda t=t: self._add(f"{base}>{t}"))
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _make_item(self, action: str) -> QListWidgetItem:
        it = QListWidgetItem(describe(action, self.party()))
        it.setData(Qt.ItemDataRole.UserRole, action)
        it.setForeground(QColor(color_of(action)))
        it.setToolTip(action)
        return it

    def _add(self, action: str):
        w = self.wave_group.checkedId()
        lw = self.lists[w]
        pos = lw.count()
        if not action.startswith("np"):  # 技能放在寶具前面
            for i in range(lw.count()):
                if lw.item(i).data(Qt.ItemDataRole.UserRole).startswith("np"):
                    pos = i
                    break
        lw.insertItem(pos, self._make_item(action))
        self._emit_changed()

    def _delete(self, w):
        lw = self.lists[w]
        for it in lw.selectedItems():
            lw.takeItem(lw.row(it))
        self._emit_changed()

    def _clear(self, w):
        self.lists[w].clear()
        self._emit_changed()

    def _party_changed(self, *_):
        party = self.party()
        for h, name in zip(self.headers, party):
            h.setText(name)
        for lw in self.lists.values():
            for i in range(lw.count()):
                it = lw.item(i)
                it.setText(describe(it.data(Qt.ItemDataRole.UserRole), party))
        self._emit_changed()

    def _emit_changed(self, *_):
        self._validate()
        if not self._loading:
            self.changed.emit()

    def waves(self) -> dict[int, list[str]]:
        out = {}
        for w, lw in self.lists.items():
            acts = [lw.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lw.count())]
            if acts:
                out[w] = acts
        return out

    def _validate(self) -> bool:
        bad = []
        for w, acts in self.waves().items():
            kinds = ["np" if a.startswith("np") else "x" for a in acts]
            if "np" in kinds and "x" in kinds[kinds.index("np"):]:
                bad.append(f"第 {w} 波")
        self.warn.setText(("⚠ " + "、".join(bad) + "：寶具要排在所有技能後面") if bad else "")
        return not bad

    # ---- 設定組 ↔ 介面 ----
    def load(self, prof):
        self._loading = True
        for e, name in zip(self.party_edits, prof.party):
            e.setText(name)
        for w, lw in self.lists.items():
            lw.clear()
            for a in prof.waves.get(w, []):
                lw.addItem(self._make_item(a))
        self.priority.setCurrentIndex(max(0, self.priority.findData(prof.card_priority)))
        self.fallback.setChecked(prof.fallback_np)
        self._party_changed()
        self._loading = False
        self._validate()

    def apply(self, prof):
        prof.party = self.party()
        prof.waves = self.waves()
        prof.card_priority = self.priority.currentData()
        prof.fallback_np = self.fallback.isChecked()
