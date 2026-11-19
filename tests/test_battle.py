"""battle.py：腳本解析與畫面判斷（用真截圖）。"""
import pytest

import battle
from battle import Action, parse_action, parse_script
from vision import ROOT, imread


def shot(name):
    return imread(ROOT / "screenshots" / f"{name}.png")


# ---------- 腳本解析 ----------
@pytest.mark.parametrize("text,expected", [
    ("s2-1", Action("skill", 2, 1)),
    ("s2-3>1", Action("skill", 2, 3, 1)),
    (" S1-2 ", Action("skill", 1, 2)),
    ("m1", Action("master", None, 1)),
    ("m3>2", Action("master", None, 3, 2)),
    ("np3", Action("np", 3)),
])
def test_parse_action(text, expected):
    assert parse_action(text) == expected


@pytest.mark.parametrize("text", ["s4-1", "s1-4", "m4", "np0", "s1", "attack", ""])
def test_parse_action_rejects(text):
    with pytest.raises(ValueError):
        parse_action(text)


def test_parse_script_requires_np_last():
    with pytest.raises(ValueError):
        parse_script({"1": ["np2", "s1-1"]})


def test_default_profile_script():
    from profile_store import Profile, profile_dir
    script = Profile.load(profile_dir("default")).to_config().script
    assert [str(a) for a in script[1]] == ["s2-1", "s1-3", "m1", "np2"]
    assert set(script) == {1, 2, 3}


# ---------- 畫面判斷 ----------
# 截圖上看得到「剩餘 N」的就是冷卻中
@pytest.mark.parametrize("name,cooling", [
    ("battle_command_w1", set()),
    ("battle_command_w2", {(1, 3), (2, 1)}),
    ("battle_command_w3", {(2, 1), (2, 3), (3, 1), (3, 3)}),
])
def test_skill_ready(name, cooling):
    img = shot(name)
    for s in (1, 2, 3):
        for i in (1, 2, 3):
            assert battle.skill_ready(img, s, i) == ((s, i) not in cooling), (s, i)


@pytest.mark.parametrize("name,ready", [
    ("battle_command_w1", [False, False, False]),   # 30 / 80 / 70
    ("battle_command_w2", [False, False, False]),   # 45 / 0 / 80
    ("battle_command_w3", [False, False, False]),   # 50 / 0 / 17
    ("skill_target", [False, False, True]),         # 45 / 0 / 110
])
def test_np_ready(name, ready):
    img = shot(name)
    assert [battle.np_ready(img, s) for s in (1, 2, 3)] == ready


@pytest.mark.parametrize("name,ready", [
    ("battle_command_w1", True), ("battle_command_w2", True), ("battle_command_w3", True),
    ("master_skill", True),
    ("battle_ui_fading", False),   # 實機：技能列還沒出現，9 個技能全被誤判成冷卻
])
def test_ui_ready(name, ready):
    assert battle.ui_ready(shot(name)) == ready


def test_flying_cards_differ_from_settled():
    a = battle.card_area_signature(shot("card_flying"))
    b = battle.card_area_signature(shot("card_select"))
    assert float(abs(a - b).mean()) > 15


def test_master_menu():
    assert battle.master_menu_open(shot("master_skill"))
    assert not battle.master_menu_open(shot("battle_command_w1"))
    assert all(battle.master_skill_ready(shot("master_skill"), i) for i in (1, 2, 3))


@pytest.mark.parametrize("name,colors", [("card_select", "ABBQQ"), ("card_select_2", "BBBAA")])
def test_card_colors(name, colors):
    assert "".join(battle.card_colors(shot(name))) == colors


def test_rank_cards():
    assert battle.rank_cards(list("ABBQQ"), "BAQ") == [1, 2, 0, 3, 4]
    assert battle.rank_cards(list("ABBQQ"), "QAB") == [3, 4, 0, 1, 2]
