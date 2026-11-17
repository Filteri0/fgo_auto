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
    margin: int = 20


# 同一個狀態可以出現多次（不同版型），任一組全部符合就算
STATES: list[tuple[str, list[Check]]] = [
    ("apple_confirm",   [Check("apple_confirm_title")]),    # 黃金果實版型
    ("apple_confirm",   [Check("apple_confirm2_title")]),   # 白銀/青銅/赤銅版型（有數量滑桿）
    ("cc_detail",       [Check("cc_close_btn"), Check("cc_title")]),  # 指令紋章詳細頁
    ("cc_detail",       [Check("cc_close_btn"), Check("ce_title")]),  # 概念禮裝詳細頁（掉羈絆禮裝時出現）
    ("wipe_out",        [Check("wipe_title"), Check("retreat_btn")]),  # 全滅「接關」視窗
    # 列表更新的兩種對話框：疊在支援選擇上，右上「支援選擇」還看得到，要排在 support_select 前面
    ("refresh_confirm", [Check("refresh_title"), Check("refresh_confirm_text")]),   # 確定要更新嗎？
    ("refresh_cooldown", [Check("refresh_title"), Check("refresh_cooldown_text")]), # 無法連續進行操作
    ("ap_recover",      [Check("ap_recover_title")]),
    ("continue_sortie", [Check("continue_title")]),
    ("skill_target",    [Check("skill_target_title")]),
    ("card_select",     [Check("card_back_btn")]),  # 右下「返回」；BATTLE SPEED 在亮背景關卡會認不出
    ("battle_command",  [Check("battle_menu")]),
    ("support_select",  [Check("support_title")]),
    ("party_confirm",   [Check("party_title"), Check("quest_start_btn")]),
    ("result_next",     [Check("next_btn")]),
    ("result_tap",      [Check("tap_screen", margin=60)]),  # 掉紋章時字的位置比較低
    ("quest_select",    [Check("quest_close_btn"), Check("menu_btn")]),
]


def score(img: np.ndarray, check: Check) -> float:
    return match(img, check.template, SPECS[check.template][1], check.margin, binary=check.binary)[0]


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
