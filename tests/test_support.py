"""support.py：支援列定位、欄位比對、滿破判斷（用真截圖）。"""
import pytest

import support as S
from vision import ROOT, imread


def shot(name):
    return imread(ROOT / "screenshots" / f"{name}.png")


@pytest.mark.parametrize("name,rows", [
    ("support_select", [301, 501]),           # 第三列只露出一半，不算
    ("support_select_no_voyov", [310, 510]),
    ("support_select_cutoff", [331, 531]),
    ("support_select_rider", [335, 535]),
    ("support_no_comment", [407, 607]),
    ("refresh_confirm", []),                  # 對話框蓋住列表
])
def test_find_rows(name, rows):
    assert [r.y for r in S.find_rows(shot(name))] == rows


@pytest.mark.parametrize("name,comment", [
    ("support_select", [True, True]),         # VOYOV：有個人簡介「哭阿沒QP」
    ("support_select_no_voyov", [True, True]),
    ("support_select_rider", [False, False]),  # 幻夢星光、紅之寧靜：沒有簡介
    ("support_no_comment", [False, False]),    # 呼噗噗.：沒有簡介（實機切圖歪掉的那張）
])
def test_row_layout(name, comment):
    assert [r.has_comment for r in S.find_rows(shot(name))] == comment


def test_no_comment_row_fields_are_aligned():
    """沒有簡介的列：玩家名稱框要框到名字（不是上面的空白）。名字是深色字，框內要有夠多深色像素。"""
    img = shot("support_no_comment")
    crop = S.crop_field(img, S.find_rows(img)[0], "player")
    assert (crop.mean(axis=2) < 120).mean() > 0.05


# ---------- OCR 讀取 ----------
# 實機截圖每一列應該讀到的值：(玩家, 從者, 等級, 寶具等級)
EXPECTED_ROWS = {
    "support_select": [("VOYOV", "摩根", 120, 5), ("VOYOV", "婁希", 100, 2)],
    "support_select_no_voyov": [("JetSet", "阿周那〔Alter〕", 100, 3), ("JetSet", "摩根", 110, 5)],
    "support_select_rider": [("幻夢星光", "司馬懿〔萊涅絲〕", 83, 2), ("紅之寧靜", "弗朗西斯·德雷克", 90, 3)],
    "support_no_comment": [("呼噗噗", "摩根", 120, 5), ("呼噗噗", "伊吹童子", 100, 3)],
    "support_voyov_heracles": [("VOYOV", "摩根", 120, 5), ("VOYOV", "赫拉克勒斯", 90, 4)],
}


@pytest.mark.parametrize("name", EXPECTED_ROWS)
def test_read_row(name):
    import ocr
    img = shot(name)
    got = [S.read_row(img, r) for r in S.find_rows(img)]
    for g, (player, servant, level, np_lv) in zip(got, EXPECTED_ROWS[name], strict=True):
        assert ocr.same_name(g["player"], player), g
        assert ocr.same_name(g["servant"], servant), g
        assert g["level"] == level, g
        assert g["np"] == np_lv, g


def test_ocr_parsers():
    import ocr
    assert ocr.parse_level("Lv.120/120") == 120
    assert ocr.parse_level("Lv100/100") == 100
    assert ocr.parse_level("Lv.,83/90") == 83
    assert ocr.parse_level("") is None
    assert ocr.parse_np_level("早已無法抵達的理想鄉 Lv.5") == 5
    assert ocr.parse_np_level("射殺百頭Lv.4") == 4
    assert ocr.norm("呼噗噗，") == ocr.norm("呼噗噗")
    assert ocr.same_name("阿周那〔Alter〕", "阿周那(Alter)")
    assert not ocr.same_name("摩根", "婁希")


# ---------- 條件比對 ----------
MORGAN_120_NP5 = S.SupportSpec(servant="摩根", min_level=120, min_np=5)


@pytest.mark.parametrize("name,expected", [
    ("support_select", [True, False]),           # VOYOV 摩根 ✓ / VOYOV 婁希
    ("support_select_no_voyov", [False, False]),  # JetSet 的摩根只有 110
    ("support_no_comment", [True, False]),       # 呼噗噗. 的摩根 120 寶具 5（不限玩家）
    ("support_voyov_heracles", [True, False]),   # 實機：圖片比對時等級只有 0.58 而選不到的那張
    ("support_select_rider", [False, False]),
])
def test_morgan_120_np5_any_player(name, expected):
    img = shot(name)
    assert [S.row_matches(img, r, MORGAN_120_NP5) for r in S.find_rows(img)] == expected


def test_player_condition():
    spec = S.SupportSpec(player="VOYOV", servant="摩根")
    img = shot("support_no_comment")  # 呼噗噗. 的摩根：玩家不符
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == [False, False]
    img = shot("support_select")
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == [True, False]


def test_level_is_at_least():
    """「等級至少 100」：100、110、120 都可以。"""
    spec = S.SupportSpec(servant="摩根", min_level=100)
    img = shot("support_select_no_voyov")
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == [False, True]  # JetSet 摩根 110


def test_ce_matches_across_servants():
    """禮裝條件跨從者：清山主師的 Caster 帶了跟 VOYOV 摩根同一張活動禮裝。"""
    ref = shot("support_select")
    spec = S.SupportSpec(ce=S.crop_field(ref, S.find_rows(ref)[0], "ce"))
    img = shot("support_select_cutoff")
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == [True, False]


def test_check_row_details_for_gui():
    img = shot("support_select_no_voyov")
    detail = S.check_row(img, S.find_rows(img)[1], MORGAN_120_NP5, stop_early=False)
    assert [(k, ok) for k, ok, _ in detail] == [("從者", True), ("等級", False), ("寶具", True)]
    assert detail[1][2] == "Lv.110"


@pytest.mark.parametrize("name,mlb", [
    ("support_select", [True, True]),
    ("support_select_no_voyov", [True, True]),
    ("support_select_cutoff", [True, False]),   # 第二列（VOYOV 的阿爾托莉亞）禮裝沒滿破
    ("support_select_rider", [False, True]),    # 第一列沒裝禮裝；第二列是沒簡介版型（星星較低）
    ("support_no_comment", [True, True]),       # 第二列禮裝背景也是黃綠色，分數較低（0.66）但仍要認得
])
def test_mlb(name, mlb):
    img = shot(name)
    assert [S.mlb_score(img, r) >= S.MLB_THRESHOLD for r in S.find_rows(img)] == mlb


def test_empty_spec_matches_first_row():
    img = shot("support_select_rider")
    assert S.row_matches(img, S.find_rows(img)[0], S.SupportSpec())


def test_spec_save_load_roundtrip(tmp_path):
    ref = shot("support_select")
    spec = S.SupportSpec(player="VOYOV", servant="摩根", min_level=120, min_np=5,
                         ce=S.crop_field(ref, S.find_rows(ref)[0], "ce"), mlb=True, class_tab="caster")
    back = S.SupportSpec.load(tmp_path, spec.save(tmp_path))
    assert (back.player, back.servant, back.min_level, back.min_np, back.mlb, back.class_tab) ==         ("VOYOV", "摩根", 120, 5, True, "caster")
    assert back.ce is not None and S.row_matches(ref, S.find_rows(ref)[0], back)


def test_old_format_converted_by_ocr(tmp_path):
    """舊版設定組存的是每個欄位的圖：載入時用 OCR 轉成文字 / 數字。"""
    from vision import imwrite
    img = shot("support_voyov_heracles")
    row = S.find_rows(img)[0]
    files = {}
    for k in ("servant", "np", "level"):
        imwrite(tmp_path / f"support_{k}.png", S.crop_field(img, row, k))
        files[k] = f"support_{k}.png"
    spec = S.SupportSpec.load(tmp_path, {"fields": files, "mlb": False, "class_tab": "berserker"})
    assert (spec.player, spec.servant, spec.min_level, spec.min_np) == ("", "摩根", 120, 5)
