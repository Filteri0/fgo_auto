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
    """沒有簡介的列：用同一列切出來的圖比對自己要全部符合（欄位沒切歪）。"""
    img = shot("support_no_comment")
    row = S.find_rows(img)[0]  # 呼噗噗. 的摩根 Lv120
    spec = S.SupportSpec({k: S.crop_field(img, row, k) for k in ("player", "servant", "np", "level", "ce")},
                         mlb=True)
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == [True, False]
    # 玩家名稱框要框到名字（不是上面的空白）：名字是深色字，框內要有夠多深色像素
    crop = S.crop_field(img, row, "player")
    assert (crop.mean(axis=2) < 120).mean() > 0.05


def test_morgan_from_other_layout_matches_by_servant_np():
    """VOYOV（有簡介）切的「從者 + 寶具」條件，也能認出沒簡介那列的摩根。"""
    spec = _morgan_spec(fields=("servant", "np"))
    img = shot("support_no_comment")
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == [True, False]


def _morgan_spec(**kw):
    ref = shot("support_select")
    row = S.find_rows(ref)[0]
    fields = kw.pop("fields", ("player", "servant", "np", "level", "ce"))
    return S.SupportSpec({k: S.crop_field(ref, row, k) for k in fields}, **kw)


@pytest.mark.parametrize("name,expected", [
    ("support_select", [True, False]),          # VOYOV 摩根 ✓ / VOYOV 婁希
    ("support_select_no_voyov", [False, False]),  # JetSet 阿周那 / JetSet 摩根（等級、禮裝不同）
    ("support_select_cutoff", [False, False]),
    ("support_select_rider", [False, False]),
])
def test_full_spec_only_matches_exact_support(name, expected):
    img, spec = shot(name), _morgan_spec(mlb=True)
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == expected


def test_servant_and_np_only_matches_any_players_morgan():
    """只勾「從者 + 寶具」：JetSet 的摩根也可以。"""
    spec = _morgan_spec(fields=("servant", "np"))
    img = shot("support_select_no_voyov")
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == [False, True]


def test_ce_matches_across_servants():
    """禮裝條件跨從者：清山主師的 Caster 帶了同一張活動禮裝。"""
    spec = _morgan_spec(fields=("ce",))
    img = shot("support_select_cutoff")
    assert [S.row_matches(img, r, spec) for r in S.find_rows(img)] == [True, False]


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
    spec = _morgan_spec(fields=("servant", "ce"), mlb=True, class_tab="caster")
    data = spec.save(tmp_path)
    back = S.SupportSpec.load(tmp_path, data)
    assert set(back.templates) == {"servant", "ce"} and back.mlb and back.class_tab == "caster"
    img = shot("support_select")
    assert S.row_matches(img, S.find_rows(img)[0], back)
