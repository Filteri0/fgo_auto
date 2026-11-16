"""用假裝置回放截圖，檢查 bot 在每個畫面點了哪裡。不需要開模擬器。"""
import pytest

from bot import Bot, Config, Stop
from vision import ROOT, imread

_imgs = {}


def shot(name):
    if name not in _imgs:
        _imgs[name] = imread(ROOT / "screenshots" / f"{name}.png")
    return _imgs[name]


class FakeDevice:
    def __init__(self, screen):
        self.screen = screen
        self.taps: list[tuple[int, int]] = []
        self.swipes: list[tuple] = []

    def screenshot(self):
        return shot(self.screen)

    def tap(self, x, y):
        self.taps.append((x, y))

    def swipe(self, *args):
        self.swipes.append(args)


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(screen, **cfg):
    d, clock = FakeDevice(screen), FakeClock()
    return Bot(d, Config(**cfg), clock=clock, sleep=lambda s: None), d, clock


def near(tap, x, y, tol=25):
    return abs(tap[0] - x) <= tol and abs(tap[1] - y) <= tol


# ---------- 吃蘋果 ----------
def test_ap_recover_taps_first_allowed_apple():
    bot, d, _ = make("ap_recover", apples=["silver", "gold"], max_apples=5)
    bot.step()
    assert len(d.taps) == 1 and near(d.taps[0], 640, 470)  # 白銀那一列


def test_ap_recover_scrolls_when_apple_not_visible():
    bot, d, _ = make("ap_recover", apples=["bronze"], max_apples=5)
    bot.step()
    assert d.taps == [] and len(d.swipes) == 1


def test_ap_recover_finds_bronze_after_scroll():
    bot, d, _ = make("ap_recover_scroll", apples=["bronze"], max_apples=5)
    bot.step()
    assert near(d.taps[0], 640, 347)


def test_ap_recover_never_taps_saint_quartz_row():
    for apples in (["gold"], ["silver"], ["gold", "silver", "bronze", "copper"]):
        bot, d, _ = make("ap_recover", apples=apples, max_apples=5)
        bot.step()
        assert all(not (118 <= y <= 240) for _, y in d.taps)  # 聖晶石那列


def test_ap_recover_stops_at_apple_limit():
    bot, d, _ = make("ap_recover", max_apples=0)
    with pytest.raises(Stop):
        bot.step()
    assert near(d.taps[0], 640, 616)  # 關閉


def test_apple_confirm_gold_ok():
    bot, d, _ = make("apple_confirm", apples=["gold"], max_apples=1)
    bot.step()
    assert near(d.taps[0], 840, 565) and bot.apples_used == 1


def test_apple_confirm_silver_ok():
    bot, d, _ = make("apple_confirm_silver", apples=["silver"], max_apples=1)
    bot.step()
    assert near(d.taps[0], 840, 582) and bot.apples_used == 1


@pytest.mark.parametrize("screen,apples", [("apple_confirm", ["silver"]), ("apple_confirm_silver", ["bronze"])])
def test_apple_confirm_wrong_apple_cancels(screen, apples):
    bot, d, _ = make(screen, apples=apples, max_apples=5)
    with pytest.raises(Stop):
        bot.step()
    assert near(d.taps[0], 440, 570, tol=30) and bot.apples_used == 0


def test_apple_confirm_not_double_counted():
    bot, d, clock = make("apple_confirm", apples=["gold"], max_apples=5)
    bot.step()
    clock.t += 0.5
    bot.step()               # 冷卻中：不動作
    clock.t += 2
    bot.step()               # 畫面還在：重點一次，但不重算
    assert len(d.taps) == 2 and bot.apples_used == 1


# ---------- 助戰 ----------
def test_support_switches_class_tab_then_picks_voyov_morgan():
    bot, d, clock = make("support_select")
    bot.step()
    assert d.taps == [(565, 128)]      # 先切狂職頁籤
    clock.t += 0.5
    bot.step()
    assert len(d.taps) == 1            # 冷卻中，等列表換好
    clock.t += 2
    bot.step()
    assert near(d.taps[1], 388, 300)   # 第一列摩根，不是第二列的婁希


def test_support_without_class_tab():
    bot, d, _ = make("support_select", support_class=None)
    bot.step()
    assert near(d.taps[0], 388, 300)


# ---------- 全滅 ----------
def test_wipe_out_stops_without_tapping(tmp_path, monkeypatch):
    bot, d, _ = make("wipe_out")
    monkeypatch.setattr(bot, "_save_debug", lambda tag: tmp_path / f"{tag}.png")
    with pytest.raises(Stop):
        bot.step()
    assert d.taps == []  # 絕不點使用令咒 / 使用聖晶石


# ---------- 戰鬥 ----------
def test_battle_taps_attack():
    bot, d, _ = make("battle_command_w2")
    bot.step()
    assert d.taps == [(1140, 600)] and bot.last_wave == 2


@pytest.mark.parametrize("screen", ["card_select", "card_select_2"])
def test_card_select_taps_three_cards_once(screen):
    bot, d, clock = make(screen)
    bot.step()
    clock.t += 0.5
    bot.step()  # 冷卻中不能再點，否則會取消已選的卡
    assert len(d.taps) == 3


def test_card_select_prefers_buster():
    bot, d, _ = make("card_select")  # A B B Q Q
    bot.step()
    assert d.taps == [(385, 500), (640, 500), (130, 500)]


def test_card_select_np_first():
    bot, d, _ = make("card_select")
    bot.np_to_fire = [2]
    bot.step()
    assert d.taps == [(645, 200), (385, 500), (640, 500)]  # 寶具 + 兩張紅卡


def test_card_select_tops_up_if_still_there():
    bot, d, clock = make("card_select")
    bot.np_to_fire = [1]       # 假設判斷錯，寶具卡其實點不到
    bot.step()
    clock.t += 2
    bot.step()                 # 還在選卡畫面 → 補一張還沒點過的
    assert d.taps[-1] == (130, 500) and len(d.taps) == 4


# ---------- 戰鬥腳本流程 ----------
from battle import parse_script  # noqa: E402

SCRIPT = parse_script({"1": ["s2-1", "s1-3", "m1", "np2"], "2": ["s3-1", "s2-3", "np3"]})


class Skills:
    """可控制的技能狀態：預設全部可用，casted 裡的視為已施放（變暗）。"""
    def __init__(self, cooling=()):
        self.cooling = set(cooling)

    def __call__(self, img, s, i):
        return (s, i) not in self.cooling


def test_wave1_script_full_flow(monkeypatch):
    skills = Skills()
    monkeypatch.setattr("battle.skill_ready", skills)
    monkeypatch.setattr("battle.np_ready", lambda img, s: s == 2)
    bot, d, clock = make("battle_command_w1", script=SCRIPT)

    bot.step()
    assert d.taps[-1] == (392, 578)            # s2-1
    skills.cooling.add((2, 1)); clock.t += 2
    bot.step()
    assert d.taps[-1] == (251, 578)            # s1-3
    skills.cooling.add((1, 3)); clock.t += 2
    bot.step()
    assert d.taps[-1] == (1195, 305)           # 打開御主技能選單
    d.screen = "master_skill"; clock.t += 2
    bot.step()
    assert d.taps[-1] == (910, 312)            # 御主技能 1
    d.screen = "battle_command_w1"; clock.t += 2
    bot.step()
    assert d.taps[-1] == (1140, 600)           # 腳本跑完 → Attack
    assert bot.np_to_fire == [2]
    d.screen = "card_select"
    bot.step()
    assert d.taps[-3:] == [(645, 200), (385, 500), (640, 500)]  # 寶具 + 兩張紅卡


def test_skill_on_cooldown_is_skipped(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills(cooling={(2, 1)}))
    bot, d, _ = make("battle_command_w1", script=SCRIPT)
    bot.step()
    assert d.taps == [(251, 578)]              # s2-1 冷卻中，直接做 s1-3


def test_skill_retapped_if_not_cast(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills())
    bot, d, clock = make("battle_command_w1", script=SCRIPT)
    bot.step()
    clock.t += 2
    bot.step()                                 # 還沒到 3 秒：等
    assert d.taps == [(392, 578)]
    clock.t += 2
    bot.step()                                 # 超過 3 秒還亮著：重點
    assert d.taps == [(392, 578), (392, 578)]


def test_skill_target_defaults_to_wave_np_servant(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills())
    bot, d, clock = make("battle_command_w2", script=SCRIPT)
    bot.step()
    assert d.taps[-1] == (710, 578)            # s3-1
    d.screen = "skill_target"                  # 跳出選目標（截圖剛好是第 2 波）
    bot.step()
    assert d.taps[-1] == (960, 390)            # 給第 2 波開寶具的 3 號位


def test_explicit_target(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills())
    bot, d, _ = make("battle_command_w2", script=parse_script({"2": ["s3-1>1", "np3"]}))
    bot.step()
    d.screen = "skill_target"
    bot.step()
    assert d.taps[-1] == (320, 390)


def test_fallback_turn_attacks_directly(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills())
    monkeypatch.setattr("battle.np_ready", lambda img, s: s in (1, 3))
    bot, d, _ = make("battle_command_w1", script=SCRIPT)
    bot.cur_wave = 1
    bot.scripted_waves.add(1)                  # 第 1 波腳本已經跑過（寶具沒打死）
    bot.step()
    assert d.taps == [(1140, 600)] and bot.np_to_fire == [1, 3]


def test_planned_np_not_ready_falls_back_to_cards(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills(cooling={(2, 1), (1, 3)}))
    monkeypatch.setattr("battle.np_ready", lambda img, s: False)
    bot, d, _ = make("battle_command_w1", script=parse_script({"1": ["s2-1", "s1-3", "np2"]}))
    bot.step()
    assert d.taps == [(1140, 600)] and bot.np_to_fire == []


def test_unexpected_skill_target_closes():
    bot, d, _ = make("skill_target")
    bot.step()
    assert near(d.taps[0], 1097, 155)


# ---------- 結算 ----------
def test_result_tap_on_text_not_card():
    bot, d, _ = make("Extra")
    bot.step()
    assert near(d.taps[0], 640, 690, tol=30)


def test_cc_detail_closes():
    bot, d, _ = make("Extra2")
    bot.step()
    assert near(d.taps[0], 46, 40)


def test_continue_sortie_continues():
    bot, d, _ = make("continue_sortie", runs=None)
    bot.step()
    assert near(d.taps[0], 840, 582) and bot.runs_done == 1


def test_continue_sortie_stops_at_run_limit():
    bot, d, _ = make("continue_sortie", runs=1)
    with pytest.raises(Stop):
        bot.step()
    assert near(d.taps[0], 442, 582)


def test_continue_sortie_counted_once():
    bot, d, clock = make("continue_sortie", runs=None)
    for _ in range(3):
        bot.step()
        clock.t += 2
    assert bot.runs_done == 1 and len(d.taps) == 3


# ---------- 認不出畫面 ----------
def test_unknown_taps_then_times_out(tmp_path, monkeypatch):
    bot, d, clock = make("test", unknown_tap_after=5, unknown_timeout=120)
    monkeypatch.setattr(bot, "_save_debug", lambda tag: tmp_path / f"{tag}.png")
    bot.step()
    clock.t += 6
    bot.step()
    assert d.taps == [(40, 300)]
    clock.t += 200
    with pytest.raises(Stop):
        bot.step()


def test_quest_select_waits_without_tapping():
    bot, d, clock = make("quest_select")
    for _ in range(3):
        bot.step()
        clock.t += 200
    assert d.taps == []
