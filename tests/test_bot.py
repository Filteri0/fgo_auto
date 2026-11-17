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


def act(bot, d, clock, max_steps=8):
    """一直 step（每次過 0.6 秒）直到 bot 點了東西：模擬等畫面穩定的那幾張截圖。"""
    before = len(d.taps)
    for _ in range(max_steps):
        bot.step()
        if len(d.taps) > before:
            return
        clock.t += 0.6
    raise AssertionError("等了很多張截圖都沒有動作")


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
def test_support_already_on_berserker_picks_voyov_morgan():
    bot, d, _ = make("support_select")  # 狂職頁籤已經是選中的
    bot.step()
    assert near(d.taps[0], 388, 300)    # 第一列摩根，不是第二列的婁希


def test_support_switches_class_tab_and_verifies():
    bot, d, clock = make("support_select_rider")  # 停在騎職頁籤
    bot.step()
    assert d.taps == [(565, 128)]
    clock.t += 0.5
    bot.step()
    assert len(d.taps) == 1             # 冷卻中，等列表換好
    clock.t += 2
    bot.step()                          # 模擬器卡住、點擊沒生效：畫面還是騎職 → 再點
    assert d.taps == [(565, 128), (565, 128)] and d.swipes == []
    d.screen = "support_select"         # 這次切成功了
    clock.t += 2
    bot.step()
    assert near(d.taps[2], 388, 300)


def test_support_gives_up_if_tab_never_switches(tmp_path, monkeypatch):
    bot, d, clock = make("support_select_rider")
    monkeypatch.setattr(bot, "_save_debug", lambda tag: tmp_path / f"{tag}.png")
    with pytest.raises(Stop):
        for _ in range(10):
            bot.step()
            clock.t += 2
    assert d.taps.count((565, 128)) == 5 and d.swipes == []


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
    bot, d, clock = make("battle_command_w2")
    bot.step()
    assert d.taps == []                         # 第一張：先等 UI 連續穩定
    act(bot, d, clock)
    assert d.taps == [(1140, 600)] and bot.last_wave == 2


def test_battle_waits_while_ui_fading_in(monkeypatch):
    monkeypatch.setattr("battle.ui_ready", lambda img: False)  # 技能列 / Attack 還沒淡入
    bot, d, clock = make("battle_command_w1", script=SCRIPT)
    for _ in range(10):
        bot.step()
        clock.t += 0.6
    assert d.taps == [] and bot.queue is None   # 不判斷技能、不跳過任何東西


@pytest.mark.parametrize("screen", ["card_select", "card_select_2"])
def test_card_select_taps_three_cards_once(screen):
    bot, d, clock = make(screen)
    act(bot, d, clock)
    clock.t += 0.5
    bot.step()  # 冷卻中不能再點，否則會取消已選的卡
    assert len(d.taps) == 3


def test_card_select_waits_for_cards_to_settle():
    bot, d, clock = make("card_select")
    bot.step()
    assert d.taps == []        # 只看到一張，還不知道卡片是不是在飛
    clock.t += 0.6
    d.screen = "card_select_2"  # 下一張卡色不同 = 還在動畫
    bot.step()
    assert d.taps == []
    clock.t += 0.6
    bot.step()                 # 連續兩張一樣 = 落定
    assert d.taps == [(130, 500), (385, 500), (640, 500)]  # card_select_2 是 B B B A A


def test_card_select_gives_up_waiting_after_timeout(monkeypatch):
    seq = iter(["card_select", "card_select_2"] * 10)
    bot, d, clock = make("card_select")
    for _ in range(8):         # 一直在變（不穩定），4 秒後照最新的卡色出卡
        d.screen = next(seq)
        bot.step()
        clock.t += 0.6
    assert len(d.taps) == 3


def test_card_select_prefers_buster():
    bot, d, clock = make("card_select")  # A B B Q Q
    act(bot, d, clock)
    assert d.taps == [(385, 500), (640, 500), (130, 500)]


def test_card_select_np_first():
    bot, d, clock = make("card_select")
    bot.np_to_fire = [2]
    act(bot, d, clock)
    assert d.taps == [(645, 200), (385, 500), (640, 500)]  # 寶具 + 兩張紅卡


def test_card_select_tops_up_if_still_there():
    bot, d, clock = make("card_select")
    bot.np_to_fire = [1]       # 假設判斷錯，寶具卡其實點不到
    act(bot, d, clock)
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

    act(bot, d, clock)
    assert d.taps[-1] == (392, 578)            # s2-1
    skills.cooling.add((2, 1)); clock.t += 2
    act(bot, d, clock)
    assert d.taps[-1] == (251, 578)            # s1-3
    skills.cooling.add((1, 3)); clock.t += 2
    act(bot, d, clock)
    assert d.taps[-1] == (1195, 305)           # 打開御主技能選單
    d.screen = "master_skill"; clock.t += 2
    act(bot, d, clock)
    assert d.taps[-1] == (910, 312)            # 御主技能 1
    d.screen = "battle_command_w1"; clock.t += 2
    act(bot, d, clock)
    assert d.taps[-1] == (1140, 600)           # 腳本跑完 → Attack
    assert bot.np_to_fire == [2]
    d.screen = "card_select"
    act(bot, d, clock)
    assert d.taps[-3:] == [(645, 200), (385, 500), (640, 500)]  # 寶具 + 兩張紅卡
    assert len(d.taps) == 8                    # 沒有多點任何東西


def test_next_skill_judged_on_fresh_frame(monkeypatch):
    """技能 A 確認施放後，不能在同一張截圖上判斷技能 B（施放動畫會讓整排變暗）。"""
    skills = Skills()
    monkeypatch.setattr("battle.skill_ready", skills)
    bot, d, clock = make("battle_command_w1", script=parse_script({"3": ["s1-1", "s1-2", "s1-3", "np1"]}))
    bot.cur_wave = 3
    monkeypatch.setattr("bot.detect_wave", lambda img: 3)
    act(bot, d, clock)
    assert d.taps[-1] == (73, 578)             # s1-1
    skills.cooling |= {(1, 1), (1, 2), (1, 3)}  # 施放動畫中：整排看起來都暗
    clock.t += 2
    bot.step(); clock.t += 0.6
    bot.step()                                 # 確認 s1-1 完成 → 這張不判斷下一個
    skills.cooling = {(1, 1)}                  # 動畫結束，s1-2、s1-3 其實可用
    act(bot, d, clock)
    assert d.taps[-1] == (163, 578)            # s1-2 沒被跳過
    skills.cooling.add((1, 2)); clock.t += 2
    act(bot, d, clock)
    assert d.taps[-1] == (251, 578)            # s1-3 也沒被跳過


def test_skill_on_cooldown_is_skipped(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills(cooling={(2, 1)}))
    bot, d, clock = make("battle_command_w1", script=SCRIPT)
    act(bot, d, clock)
    assert d.taps == [(251, 578)]              # s2-1 冷卻中，直接做 s1-3


def test_skill_retapped_if_not_cast(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills())
    bot, d, clock = make("battle_command_w1", script=SCRIPT)
    act(bot, d, clock)
    clock.t += 1.6
    bot.step(); clock.t += 0.6
    bot.step()                                 # 還沒到 3 秒：等
    assert d.taps == [(392, 578)]
    clock.t += 2
    act(bot, d, clock)                         # 超過 3 秒還亮著：重點
    assert d.taps == [(392, 578), (392, 578)]


def test_skill_target_defaults_to_wave_np_servant(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills())
    bot, d, clock = make("battle_command_w2", script=SCRIPT)
    act(bot, d, clock)
    assert d.taps[-1] == (710, 578)            # s3-1
    d.screen = "skill_target"                  # 跳出選目標（截圖剛好是第 2 波）
    bot.step()
    assert d.taps[-1] == (960, 390)            # 給第 2 波開寶具的 3 號位


def test_explicit_target(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills())
    bot, d, clock = make("battle_command_w2", script=parse_script({"2": ["s3-1>1", "np3"]}))
    act(bot, d, clock)
    d.screen = "skill_target"
    bot.step()
    assert d.taps[-1] == (320, 390)


def test_fallback_turn_attacks_directly(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills())
    monkeypatch.setattr("battle.np_ready", lambda img, s: s in (1, 3))
    bot, d, clock = make("battle_command_w1", script=SCRIPT)
    bot.cur_wave = 1
    bot.scripted_waves.add(1)                  # 第 1 波腳本已經跑過（寶具沒打死）
    act(bot, d, clock)
    assert d.taps == [(1140, 600)] and bot.np_to_fire == [1, 3]


def test_blinking_np_arrow_still_fires(monkeypatch):
    """實機：NP 滿的箭頭會閃，連續截圖會是 滿 → 不滿 → 滿。按 Attack 那張剛好是暗的也要放寶具。"""
    frames = iter([True, False, False, False, False, False, False, False])
    monkeypatch.setattr("battle.skill_ready", Skills(cooling={(2, 1), (1, 3)}))
    monkeypatch.setattr("battle.np_ready", lambda img, s: s == 2 and next(frames))
    bot, d, clock = make("battle_command_w1", script=parse_script({"1": ["s2-1", "s1-3", "np2"]}))
    act(bot, d, clock)
    assert d.taps == [(1140, 600)] and bot.np_to_fire == [2]


def test_fallback_turn_catches_blinking_np(monkeypatch):
    """實機：補刀回合 3 號位 NP 滿，但前兩張剛好拍到箭頭暗的瞬間 → 曾經漏放寶具。"""
    frames = iter([False, False, True] + [False] * 10)
    monkeypatch.setattr("battle.skill_ready", Skills())
    monkeypatch.setattr("battle.np_ready", lambda img, s: s == 3 and next(frames))
    bot, d, clock = make("battle_command_w1", script=SCRIPT)
    bot.cur_wave = 1
    bot.scripted_waves.add(1)                  # 補刀回合
    act(bot, d, clock)
    assert d.taps == [(1140, 600)] and bot.np_to_fire == [3]


def test_waits_extra_frames_for_planned_np(monkeypatch):
    seen = iter([False, False, True] + [False] * 10)  # 第 3 張才拍到亮的箭頭
    monkeypatch.setattr("battle.skill_ready", Skills(cooling={(2, 1), (1, 3)}))
    monkeypatch.setattr("battle.np_ready", lambda img, s: s == 2 and next(seen))
    bot, d, clock = make("battle_command_w1", script=parse_script({"1": ["s2-1", "s1-3", "np2"]}))
    act(bot, d, clock)
    assert bot.np_to_fire == [2]


def test_planned_np_not_ready_falls_back_to_cards(monkeypatch):
    monkeypatch.setattr("battle.skill_ready", Skills(cooling={(2, 1), (1, 3)}))
    monkeypatch.setattr("battle.np_ready", lambda img, s: False)
    bot, d, clock = make("battle_command_w1", script=parse_script({"1": ["s2-1", "s1-3", "np2"]}))
    act(bot, d, clock)
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
