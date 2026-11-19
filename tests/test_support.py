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
    ("refresh_confirm", []),                  # 對話框蓋住列表
])
def test_find_rows(name, rows):
    assert [y for _, y in S.find_rows(shot(name))] == rows


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
    ("support_select_rider", [False, True]),    # 第一列沒裝禮裝；第二列星星位置比較低
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
