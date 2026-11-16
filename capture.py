"""互動式截圖工具：在遊戲切到想要的畫面後，輸入名稱按 Enter 存檔。

用法：
    uv run python capture.py

輸入：
    <名稱> + Enter  → 存成 screenshots/<名稱>.png（同名會自動加 _2、_3…）
    直接 Enter       → 用時間戳命名
    q + Enter        → 離開
"""
import time
from pathlib import Path

import cv2

from device import Device

OUT_DIR = Path(__file__).parent / "screenshots"

SUGGESTED = [
    "quest_select", "ap_recover", "support_select", "party_confirm",
    "battle_command_w1", "battle_command_w2", "battle_command_w3", "card_select",
    "result_bond", "result_exp", "result_drop", "friend_request",
    "continue_sortie", "wipe_out",
]


def unique_path(name: str) -> Path:
    path = OUT_DIR / f"{name}.png"
    i = 2
    while path.exists():
        path = OUT_DIR / f"{name}_{i}.png"
        i += 1
    return path


def main():
    OUT_DIR.mkdir(exist_ok=True)
    d = Device()
    print("建議名稱：", ", ".join(SUGGESTED))
    print("輸入名稱後按 Enter 截圖，直接 Enter 用時間戳，q 離開。\n")
    while True:
        try:
            name = input("名稱> ").strip().lstrip("﻿")
        except (EOFError, KeyboardInterrupt):
            break
        if name.lower() == "q":
            break
        name = name or time.strftime("%Y%m%d_%H%M%S")
        img = d.screenshot()
        path = unique_path(name)
        # cv2.imwrite 在 Windows 上遇到中文路徑會失敗，改用 imencode 再寫檔
        path.write_bytes(cv2.imencode(".png", img)[1].tobytes())
        print(f"  已存 {path.relative_to(OUT_DIR.parent)}  ({img.shape[1]}x{img.shape[0]})")


if __name__ == "__main__":
    main()
