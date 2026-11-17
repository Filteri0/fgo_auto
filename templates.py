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
    "battle_speed":        ("card_select",    (1073, 80, 1197, 99)),  # 選卡畫面右上 BATTLE SPEED 字樣（背景亮時不可靠）
    "card_back_btn":       ("card_select",    (1150, 665, 1258, 700)),# 選卡畫面右下「返回」按鈕
    "attack_btn":          ("battle_command_w1", (1050, 570, 1235, 640)),  # Attack 字樣（會閃，只拿來點不拿來判斷）
    "battle_menu":         ("battle_command_w1", (1168, 188, 1224, 240)),  # 右上「戰鬥清單」
    "wave_1":              ("battle_command_w1", (880, 12, 900, 36)),
    "wave_2":              ("battle_command_w2", (880, 12, 900, 36)),
    "wave_3":              ("battle_command_w3", (880, 12, 900, 36)),
    # 結算
    "tap_screen":          ("result_exp",     (545, 628, 740, 668)),  # 「請點擊畫面」
    "next_btn":            ("result_drop",    (1045, 620, 1170, 665)),# 「下一步」
    "cc_close_btn":        ("Extra2",         (25, 28, 68, 52)),      # 紋章詳細頁左上「關閉」
    "cc_title":            ("Extra2",         (1063, 64, 1247, 86)),  # 紋章詳細頁右上「COMMAND CODE」
    "ce_title":            ("ce_detail",      (1163, 62, 1249, 88)),  # 概念禮裝詳細頁右上「概念禮裝」（例如羈絆禮裝）
    "continue_btn":        ("continue_sortie", (765, 560, 915, 605)), # 「連續出擊」
    "continue_close_btn":  ("continue_sortie", (405, 560, 480, 605)), # 「關閉」
    # 吃蘋果
    "apple_confirm2_title": ("apple_confirm_silver", (528, 55, 752, 92)),  # 「消耗果實恢復AP」（銀/銅版型）
    "confirm_ok_btn":      ("apple_confirm",  (790, 545, 890, 585)),  # 「確定」
    "confirm_cancel_btn":  ("apple_confirm",  (390, 545, 490, 585)),  # 「取消」
    "ap_close_btn":        ("ap_recover",     (605, 598, 675, 635)),  # AP恢復視窗「關閉」
    "apple_icon_gold":     ("ap_recover",     (325, 278, 425, 368)),
    "apple_icon_silver":   ("ap_recover",     (325, 425, 425, 515)),
    "apple_icon_bronze":   ("ap_recover_scroll", (325, 302, 425, 392)),
    "apple_icon_copper":   ("ap_recover_scroll", (325, 449, 425, 539)),
    "apple_name_gold":     ("apple_confirm",  (640, 200, 782, 236)),  # 金：確認視窗藍底「黃金果實」
    "apple_name_silver":   ("ap_recover_scroll", (458, 158, 570, 188)),  # 銀/銅：列表上的名稱
    "apple_name_bronze":   ("ap_recover_scroll", (458, 305, 570, 335)),
    "apple_name_copper":   ("ap_recover_scroll", (458, 452, 570, 482)),
    # 助戰列表更新
    "refresh_btn_ready":   ("support_select",   (893, 108, 967, 152)),  # 「列表更新」按鈕（冷卻中會變成倒數數字）
    "refresh_title":       ("refresh_confirm",  (567, 115, 715, 160)),  # 兩種對話框共用標題「列表更新」
    "refresh_confirm_text": ("refresh_confirm", (525, 343, 757, 376)),  # 「確定要更新嗎？」
    "refresh_yes_btn":     ("refresh_confirm",  (805, 545, 875, 585)),  # 「是」
    "refresh_cooldown_text": ("refresh_cooldown", (365, 310, 915, 345)),  # 「無法連續進行操作。」
    "refresh_close_btn":   ("refresh_cooldown", (595, 545, 685, 585)),  # 「關閉」
    # 助戰：VOYOV 的摩根
    "support_player_voyov":   ("support_select", (240, 195, 362, 230)),
    "support_servant_morgan": ("support_select", (362, 286, 414, 314)),
    # 戰鬥
    "skill_target_close":  ("skill_target",   (1075, 135, 1120, 175)),
    "master_skill_icon1":  ("master_skill",   (877, 282, 943, 343)),  # 御主技能選單展開後的技能1圖示（換禮裝要重切）
    "wipe_title":          ("wipe_out",       (462, 205, 825, 235)),  # 「是否使用3劃令咒或1個聖晶石接關？」
    "retreat_btn":         ("wipe_out",       (295, 305, 365, 340)),  # 「撤退」
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
