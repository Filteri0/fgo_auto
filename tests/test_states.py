"""用 screenshots/ 裡的截圖驗證畫面辨識。新增截圖時把預期結果加進 EXPECTED。"""
import pytest

from states import detect_state, detect_wave
from vision import ROOT, imread

# 截圖檔名 → (預期狀態, 預期波次)
EXPECTED = {
    "quest_select":      ("quest_select", None),
    "ap_recover":        ("ap_recover", None),
    "apple_confirm":     ("apple_confirm", None),
    "support_select":    ("support_select", None),
    "party_confirm":     ("party_confirm", None),
    "battle_command_w1": ("battle_command", 1),
    "battle_command_w2": ("battle_command", 2),
    "battle_command_w3": ("battle_command", 3),
    "skill_target":      ("skill_target", None),
    "card_select":       ("card_select", None),
    "card_select_2":     ("card_select", None),  # 亮背景關卡：舊的 BATTLE SPEED 判斷會失敗
    "wipe_out":          ("wipe_out", None),
    "result_bond":       ("result_tap", None),
    "result_exp":        ("result_tap", None),
    "result_drop":       ("result_next", None),
    "result_drop2":      ("result_next", None),
    "continue_sortie":   ("continue_sortie", None),
    "ap_recover_scroll":    ("ap_recover", None),
    "apple_confirm_silver": ("apple_confirm", None),
    "result_bonds":      ("result_tap", None),
    "Extra":             ("result_tap", None),   # 掉指令紋章
    "Extra2":            ("cc_detail", None),    # 指令紋章詳細頁
    "test":              (None, None),  # 主選單：不屬於周回流程，應該認不出來
}


@pytest.mark.parametrize("shot", EXPECTED)
def test_detect_state(shot):
    img = imread(ROOT / "screenshots" / f"{shot}.png")
    assert detect_state(img) == EXPECTED[shot][0]


@pytest.mark.parametrize("shot", [s for s, (st, _) in EXPECTED.items() if st == "battle_command"])
def test_detect_wave(shot):
    img = imread(ROOT / "screenshots" / f"{shot}.png")
    assert detect_wave(img) == EXPECTED[shot][1]
