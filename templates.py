"""模板定義：名稱 → (來源截圖, 切割區域 x1,y1,x2,y2)。

執行 `uv run python templates.py` 會從 screenshots/ 重新切出 templates/*.png。
偵測時也用同一個 box 當搜尋位置，所以改座標只要改這裡。
"""
from vision import ROOT, TEMPLATE_DIR, imread, imwrite

SPECS: dict[str, tuple[str, tuple[int, int, int, int]]] = {
    # 對話框類
    "apple_confirm_title": ("apple_confirm", (545, 275, 735, 320)),   # 「是否執行？」
    "ap_recover_title":    ("ap_recover",    (585, 38, 695, 68)),     # 「AP恢復」
    "continue_title":      ("continue_sortie", (470, 95, 810, 135)),  # 「是否連續進行同一任務？」
    # 出擊前
    "support_title":       ("support_select", (1040, 12, 1270, 62)),  # 「支援選擇」
    "party_title":         ("party_confirm",  (1045, 12, 1270, 62)),  # 「隊伍確認」
    "quest_start_btn":     ("party_confirm",  (1095, 645, 1260, 700)),# 「任務開始」
    "quest_close_btn":     ("quest_select",   (75, 20, 145, 65)),     # 左上「關閉」
    "menu_btn":            ("quest_select",   (1135, 635, 1235, 675)),# 右下「MENU」
    # 戰鬥
    "skill_target_title":  ("skill_target",   (565, 170, 715, 212)),  # 「請選擇對象」
    "battle_speed":        ("card_select",    (1073, 80, 1197, 99)),  # 選卡畫面右上 BATTLE SPEED 字樣
    "attack_btn":          ("battle_command_w1", (1050, 570, 1235, 640)),  # Attack 字樣（會閃，只拿來點不拿來判斷）
    "battle_menu":         ("battle_command_w1", (1168, 188, 1224, 240)),  # 右上「戰鬥清單」
    "wave_1":              ("battle_command_w1", (880, 12, 900, 36)),
    "wave_2":              ("battle_command_w2", (880, 12, 900, 36)),
    "wave_3":              ("battle_command_w3", (880, 12, 900, 36)),
    # 結算
    "tap_screen":          ("result_exp",     (545, 628, 740, 668)),  # 「請點擊畫面」
    "next_btn":            ("result_drop",    (1045, 620, 1170, 665)),# 「下一步」
}


def build():
    TEMPLATE_DIR.mkdir(exist_ok=True)
    cache = {}
    for name, (src, (x1, y1, x2, y2)) in SPECS.items():
        if src not in cache:
            cache[src] = imread(ROOT / "screenshots" / f"{src}.png")
        imwrite(TEMPLATE_DIR / f"{name}.png", cache[src][y1:y2, x1:x2])
        print(f"{name:22s} <- {src} {(x1, y1, x2, y2)}")


if __name__ == "__main__":
    build()
