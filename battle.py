"""戰鬥相關：腳本解析、技能 / NP / 卡色判斷、選卡。座標一律以 1280x720 為準。

腳本動作語法：
    s2-1      2 號位的技能 1
    s2-3>1    2 號位的技能 3，目標 1 號位
    m1        御主技能 1（m1>2 = 目標 2 號位）
    np2       2 號位放寶具
"""
import re
from dataclasses import dataclass

import cv2
import numpy as np

from templates import SPECS
from vision import match

# 技能圖示中心：SKILL_POS[從者位置][技能編號]
SKILL_POS = {
    1: {1: (73, 578), 2: (163, 578), 3: (251, 578)},
    2: {1: (392, 578), 2: (480, 578), 3: (568, 578)},
    3: {1: (710, 578), 2: (798, 578), 3: (886, 578)},
}
MASTER_BTN = (1195, 305)
MASTER_SKILL_POS = {1: (910, 312), 2: (997, 312), 3: (1083, 312)}
TARGET_POS = {1: (320, 390), 2: (640, 390), 3: (960, 390)}     # 「請選擇對象」畫面
NP_CARD_POS = {1: (430, 200), 2: (645, 200), 3: (860, 200)}    # 選卡畫面上方寶具卡（1、3 號為推算）
CARD_POS = [(130, 500), (385, 500), (640, 500), (900, 500), (1155, 500)]
NP_ARROW_X = {1: 293, 2: 611, 3: 929}  # NP 條右端「>>」，NP >= 100% 時會變亮白

SKILL_READY_V = 150   # 技能圖示亮度：可用 187~240，冷卻 93~108
NP_READY_GRAY = 95    # 「>>」平均亮度（戰鬥指令畫面）：未滿 <= 81，滿 113


@dataclass(frozen=True)
class Action:
    kind: str                 # "skill" / "master" / "np"
    servant: int | None       # skill / np 用：從者位置 1~3
    index: int | None = None  # skill / master 用：技能編號 1~3
    target: int | None = None

    def __str__(self):
        if self.kind == "np":
            return f"np{self.servant}"
        base = f"s{self.servant}-{self.index}" if self.kind == "skill" else f"m{self.index}"
        return base + (f">{self.target}" if self.target else "")


_RE_SKILL = re.compile(r"^s([123])-([123])(?:>([123]))?$")
_RE_MASTER = re.compile(r"^m([123])(?:>([123]))?$")
_RE_NP = re.compile(r"^np([123])$")


def parse_action(text: str) -> Action:
    t = text.strip().lower().replace(" ", "")
    if m := _RE_SKILL.match(t):
        return Action("skill", int(m[1]), int(m[2]), int(m[3]) if m[3] else None)
    if m := _RE_MASTER.match(t):
        return Action("master", None, int(m[1]), int(m[2]) if m[2] else None)
    if m := _RE_NP.match(t):
        return Action("np", int(m[1]))
    raise ValueError(f"看不懂的腳本動作：{text!r}（格式：s2-1、s2-3>1、m1、m1>2、np2）")


def parse_script(waves: dict) -> dict[int, list[Action]]:
    """{"1": ["s2-1", "np2"], ...} → {1: [Action, ...]}，並檢查寶具要放在技能之後。"""
    script = {}
    for key, actions in waves.items():
        wave = int(key)
        if wave not in (1, 2, 3):
            raise ValueError(f"波次只能是 1~3：{key}")
        parsed = [parse_action(a) for a in actions]
        kinds = [a.kind for a in parsed]
        if "np" in kinds and any(k != "np" for k in kinds[kinds.index("np"):]):
            raise ValueError(f"第 {wave} 波：寶具（npX）要寫在所有技能後面")
        script[wave] = parsed
    return script


# ---------- 畫面判斷 ----------
def ui_ready(img) -> bool:
    """戰鬥指令 UI 是否完整出現：Attack 按鈕藍色約 42%，淡入中 / 技能動畫中為 0。

    「戰鬥清單」比技能列和 Attack 早出現，只看它的話會在技能列還沒淡入時就判斷，
    把所有技能都誤判成冷卻中。
    """
    hsv = cv2.cvtColor(img[545:655, 1065:1225], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return float(((h >= 90) & (h <= 110) & (s > 150) & (v > 200)).mean()) > 0.2


def card_area_signature(img) -> np.ndarray:
    """指令卡區域的縮圖，用來判斷卡片是否已經落定（連續兩張差不多 = 動畫結束）。"""
    gray = cv2.cvtColor(img[380:640, 0:1280], cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (160, 32), interpolation=cv2.INTER_AREA).astype(np.int16)


def skill_ready(img, servant: int, index: int) -> bool:
    x, y = SKILL_POS[servant][index]
    v = cv2.cvtColor(img[y - 25:y + 25, x - 25:x + 25], cv2.COLOR_BGR2HSV)[..., 2]
    return float(v.mean()) > SKILL_READY_V


def master_skill_ready(img, index: int) -> bool:
    x, y = MASTER_SKILL_POS[index]
    v = cv2.cvtColor(img[y - 25:y + 25, x - 25:x + 25], cv2.COLOR_BGR2HSV)[..., 2]
    return float(v.mean()) > SKILL_READY_V


def master_menu_open(img) -> bool:
    return match(img, "master_skill_icon1", SPECS["master_skill_icon1"][1], 10)[0] >= 0.85


def np_ready(img, servant: int) -> bool:
    """只在戰鬥指令畫面使用（選卡畫面整體較暗，門檻不同）。"""
    x = NP_ARROW_X[servant]
    gray = cv2.cvtColor(img[675:689, x:x + 18], cv2.COLOR_BGR2GRAY)
    return float(gray.mean()) > NP_READY_GRAY


def card_colors(img) -> list[str]:
    """五張指令卡的顏色：'B'uster / 'A'rts / 'Q'uick。"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    out = []
    for x, _ in CARD_POS:
        r = hsv[440:610, x - 70:x + 70]
        h, s, v = r[..., 0], r[..., 1], r[..., 2]
        vivid = (s > 120) & (v > 100)
        counts = {
            "B": int((((h < 8) | (h > 170)) & vivid).sum()),
            "A": int(((h >= 95) & (h <= 130) & vivid).sum()),
            "Q": int(((h >= 40) & (h <= 85) & vivid).sum()),
        }
        out.append(max(counts, key=counts.get))
    return out


def rank_cards(colors: list[str], priority: str = "BAQ") -> list[int]:
    """依卡色優先順序排出普通卡的索引（0~4），同色維持原本左到右的順序。"""
    return sorted(range(len(colors)), key=lambda i: (priority.index(colors[i]), i))
