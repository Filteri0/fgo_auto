"""畫面狀態辨識。

STATES 依「優先順序」排列：對話框會疊在其他畫面上（例如吃蘋果確認底下還看得到 AP恢復），
所以越上層的畫面要越先檢查。每個狀態列出的模板必須全部比對成功才算。
"""
from dataclasses import dataclass

import numpy as np

from templates import SPECS
from vision import match

THRESHOLD = 0.85


@dataclass(frozen=True)
class Check:
    template: str
    binary: int | None = None


STATES: list[tuple[str, list[Check]]] = [
    ("apple_confirm",   [Check("apple_confirm_title")]),
    ("ap_recover",      [Check("ap_recover_title")]),
    ("continue_sortie", [Check("continue_title")]),
    ("skill_target",    [Check("skill_target_title")]),
    ("card_select",     [Check("battle_speed", binary=200)]),
    ("battle_command",  [Check("battle_menu")]),
    ("support_select",  [Check("support_title")]),
    ("party_confirm",   [Check("party_title"), Check("quest_start_btn")]),
    ("result_next",     [Check("next_btn")]),
    ("result_tap",      [Check("tap_screen")]),
    ("quest_select",    [Check("quest_close_btn"), Check("menu_btn")]),
]


def score(img: np.ndarray, check: Check) -> float:
    return match(img, check.template, SPECS[check.template][1], binary=check.binary)[0]


def detect_state(img: np.ndarray, threshold: float = THRESHOLD) -> str | None:
    """回傳目前畫面的狀態名稱，認不出來回傳 None。"""
    for name, checks in STATES:
        if all(score(img, c) >= threshold for c in checks):
            return name
    return None


def detect_wave(img: np.ndarray, threshold: float = 0.7) -> int | None:
    """讀右上角 BATTLE n/3 的 n。取三個數字模板中分數最高的。"""
    scores = {n: match(img, f"wave_{n}", SPECS[f"wave_{n}"][1], margin=6, binary=200)[0] for n in (1, 2, 3)}
    best = max(scores, key=scores.get)
    return best if scores[best] >= threshold else None


if __name__ == "__main__":
    # 即時模式：連上模擬器，每次截圖印出辨識結果。Ctrl+C 離開。
    import time

    from device import Device

    d = Device()
    last = object()
    while True:
        img = d.screenshot()
        state = detect_state(img)
        wave = detect_wave(img) if state == "battle_command" else None
        cur = (state, wave)
        if cur != last:
            print(time.strftime("%H:%M:%S"), state, f"wave={wave}" if wave else "")
            last = cur
        time.sleep(0.5)
