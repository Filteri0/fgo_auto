"""周回主迴圈：截圖 → 辨識狀態 → 做一個動作 → 重來。

每個狀態只做「一個」動作就回到迴圈重新截圖，不在同一個狀態裡串好幾步，
這樣網路卡頓或動畫變慢時，下一輪看到的仍是真實畫面。
"""
import time
from dataclasses import dataclass, field
from pathlib import Path

import battle
from battle import Action, CARD_POS, MASTER_BTN, MASTER_SKILL_POS, NP_CARD_POS, SKILL_POS, TARGET_POS
from states import detect_state, detect_wave
from templates import SPECS
from vision import ROOT, imwrite, match, match_all

APPLES = ("gold", "silver", "bronze", "copper")  # 聖晶石刻意不在這裡，程式沒有任何吃石頭的路徑
APPLE_ZH = {"gold": "黃金果實", "silver": "白銀果實", "bronze": "青銅果實", "copper": "赤銅果實"}

# 固定座標（1280x720）
ATTACK = (1140, 600)
SAFE_TAP = (40, 300)              # 認不出畫面時點這裡：左側中間在各畫面都是空白（右側會點到御主技能）
SKILL_CONFIRM_WAIT = 3.0          # 點技能後等這麼久，技能還亮著才判定沒點到
APPLE_LIST = (300, 100, 440, 575)  # AP恢復視窗裡果實圖示所在的直條
SUPPORT_LIST = (230, 170, 830, 720)
SUPPORT_SERVANT_OFFSET = (87, 88)  # 從玩家名字中心到從者名字中心的偏移
# 支援選擇上方的職階頁籤（目前只有狂職的位置在實機確認過）
CLASS_TABS = {
    "all": (92, 128), "saber": (160, 128), "archer": (228, 128), "lancer": (295, 128),
    "rider": (362, 128), "caster": (430, 128), "assassin": (497, 128), "berserker": (565, 128),
    "extra": (632, 128), "mix": (698, 128),
}


class Stop(Exception):
    """正常或異常的停止，訊息會印給使用者。"""


@dataclass
class Config:
    runs: int | None = None                 # None = 無限
    apples: list[str] = field(default_factory=lambda: ["gold", "silver"])
    max_apples: int = 0                      # 0 = 不吃
    support_player: str = "support_player_voyov"
    support_servant: str = "support_servant_morgan"
    support_class: str | None = "berserker"  # 進支援選擇先切到這個職階頁籤，None = 不切
    unknown_tap_after: float = 5.0
    unknown_timeout: float = 120.0
    support_max_scrolls: int = 5
    loop_delay: float = 0.5
    action_cooldown: float = 1.5  # 同一個畫面做完動作後，等這麼久才會再動作（避免動畫中重複點）
    # 戰鬥
    script: dict[int, list[Action]] = field(default_factory=dict)  # 波次 → 動作，見 battle.py
    card_priority: str = "BAQ"    # 普通卡顏色優先順序
    fallback_np: bool = True      # 補刀回合（腳本跑完還在同一波）NP 滿就放寶具


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class Bot:
    def __init__(self, device, config: Config, clock=time.monotonic, sleep=time.sleep):
        bad = [a for a in config.apples if a not in APPLES]
        if bad:
            raise ValueError(f"不認識的果實：{bad}（可用：{', '.join(APPLES)}）")
        if config.support_class is not None and config.support_class not in CLASS_TABS:
            raise ValueError(f"不認識的職階：{config.support_class}（可用：{', '.join(CLASS_TABS)}）")
        if sorted(config.card_priority) != sorted("BAQ"):
            raise ValueError(f"card_priority 要是 B、A、Q 的排列：{config.card_priority!r}")
        self.d = device
        self.cfg = config
        self.clock = clock
        self.sleep = sleep

        self.runs_done = 0
        self.apples_used = 0
        self.run_started = clock()
        self.last_state: str | None = None
        self.last_wave: int | None = None
        self.unknown_since: float | None = None
        self.last_unknown_tap = 0.0
        self.support_scrolls = 0
        self.apple_scrolls = 0
        self.apple_tries: dict[str, int] = {}
        self.dead_apples: set[str] = set()
        self.waiting_hint_shown = False
        self.img = None
        self.entered = False      # 這一輪是不是剛進入這個狀態（計數只在進入時做）
        self.last_action = -1e9
        self._reset_battle()

    def _reset_battle(self):
        """新的一場戰鬥開始前清掉戰鬥狀態。"""
        self.cur_wave: int | None = None
        self.scripted_waves: set[int] = set()   # 已經跑完腳本的波次
        self.queue: list[Action] | None = None  # 本波還沒做的技能 / 御主技能
        self.pending: Action | None = None      # 已經點了、還在確認有沒有生效的動作
        self.pending_time = 0.0
        self.pending_tries = 0
        self.master_tapped = False
        self.turn_np: list[int] | None = None   # 腳本回合要放的寶具；None = 補刀回合
        self.np_to_fire: list[int] = []         # 按 Attack 前判斷好、要在選卡時點的寶具
        self.card_order: list[int] = []
        self.cards_clicked: set[int] = set()

    # ---------- 主迴圈 ----------
    def run(self) -> None:
        log(f"開始周回：場數={self.cfg.runs or '無限'}，果實={self.cfg.apples}，上限={self.cfg.max_apples}")
        try:
            while True:
                self.step()
                self.sleep(self.cfg.loop_delay)
        except Stop as e:
            log(f"停止：{e}")
        except KeyboardInterrupt:
            log("手動停止（Ctrl+C）")
        log(f"總計：完成 {self.runs_done} 場，吃了 {self.apples_used} 顆果實")

    def step(self) -> str | None:
        self.img = self.d.screenshot()
        state = detect_state(self.img)

        if state is None:
            self._on_unknown()
            return None
        self.unknown_since = None

        now = self.clock()
        self.entered = state != self.last_state
        if self.entered:
            self._on_leave(self.last_state, state)
            self.last_state = state
        elif now - self.last_action < self.cfg.action_cooldown:
            return state  # 剛點過，畫面可能還在動畫，先不要重複點
        getattr(self, f"on_{state}")()
        self.last_action = now
        return state

    def _on_leave(self, old, new):
        if old == "support_select":
            self.support_scrolls = 0
        if old in ("ap_recover", "apple_confirm") and new not in ("ap_recover", "apple_confirm"):
            self.apple_scrolls = 0
            self.apple_tries.clear()
        if new != "quest_select":
            self.waiting_hint_shown = False
        if new in ("support_select", "party_confirm", "continue_sortie"):
            self._reset_battle()

    def _on_unknown(self):
        now = self.clock()
        if self.unknown_since is None:
            self.unknown_since = now
            self.last_unknown_tap = now
            return
        if now - self.unknown_since > self.cfg.unknown_timeout:
            path = self._save_debug("unknown")
            raise Stop(f"超過 {self.cfg.unknown_timeout:.0f} 秒認不出畫面，截圖存在 {path}")
        if now - self.last_unknown_tap > self.cfg.unknown_tap_after:
            self.d.tap(*SAFE_TAP)
            self.last_unknown_tap = now

    def _save_debug(self, tag: str) -> Path:
        out = ROOT / "logs"
        out.mkdir(exist_ok=True)
        path = out / f"{time.strftime('%Y%m%d_%H%M%S')}_{tag}.png"
        if self.img is not None:
            imwrite(path, self.img)
        return path

    def _tap_template(self, name: str, margin: int = 20):
        self.d.tap(*match(self.img, name, SPECS[name][1], margin)[1])

    # ---------- 各狀態 ----------
    def on_quest_select(self):
        if not self.waiting_hint_shown:
            log("在選關畫面：請手動點進要周回的關卡（程式會等你）")
            self.waiting_hint_shown = True

    def on_ap_recover(self):
        if self.apples_used >= self.cfg.max_apples:
            self._tap_template("ap_close_btn")
            raise Stop(f"AP 不足，已吃 {self.apples_used} 顆（上限 {self.cfg.max_apples}）")

        for apple in self.cfg.apples:
            if apple in self.dead_apples:
                continue
            score, (_, cy) = match(self.img, f"apple_icon_{apple}", APPLE_LIST, 0, color=True)
            if score < 0.9:
                continue
            tries = self.apple_tries.get(apple, 0)
            if tries >= 3:  # 點了 3 次都沒跳確認視窗，大概是用完了
                log(f"{APPLE_ZH[apple]} 似乎用完了，改用下一種")
                self.dead_apples.add(apple)
                continue
            self.apple_tries[apple] = tries + 1
            self.d.tap(640, cy)  # 點那一列的說明文字區
            return

        # 目前畫面上沒有想吃的果實：先往下捲，再往上捲，都沒有就停
        if self.apple_scrolls == 0:
            self.d.swipe(640, 450, 640, 200)
        elif self.apple_scrolls == 1:
            self.d.swipe(640, 200, 640, 500)
            self.d.swipe(640, 200, 640, 500)
        else:
            self._tap_template("ap_close_btn")
            raise Stop(f"找不到可以吃的果實（允許：{self.cfg.apples}）")
        self.apple_scrolls += 1

    def on_apple_confirm(self):
        # 判斷是哪種確認視窗，讀出要消耗的果實名稱
        if match(self.img, "apple_confirm_title", SPECS["apple_confirm_title"][1])[0] >= 0.85:
            scores = {"gold": match(self.img, "apple_name_gold", SPECS["apple_name_gold"][1], 15)[0]}
        else:
            box = (458, 123, 570, 153)
            scores = {a: match(self.img, f"apple_name_{a}", box, 15)[0] for a in ("silver", "bronze", "copper")}
        apple = max(scores, key=scores.get)

        ok_box, cancel_box = (700, 520, 980, 620), (300, 520, 580, 620)
        # 進入時才檢查上限並計數；冷卻後還停在這個視窗代表上次沒點到，只重點不重算
        allowed = self.apples_used < self.cfg.max_apples or not self.entered
        if scores[apple] >= 0.9 and apple in self.cfg.apples and allowed:
            self.d.tap(*match(self.img, "confirm_ok_btn", ok_box, 0)[1])
            if self.entered:
                self.apples_used += 1
                self.apple_tries.clear()
                log(f"吃了 {APPLE_ZH[apple]}（第 {self.apples_used}/{self.cfg.max_apples} 顆）")
        else:
            self.d.tap(*match(self.img, "confirm_cancel_btn", cancel_box, 0)[1])
            path = self._save_debug("apple_confirm")
            raise Stop(f"確認視窗的道具不是允許的果實（辨識={apple} {scores[apple]:.2f}），已取消。截圖：{path}")

    def on_support_select(self):
        if self.entered and self.cfg.support_class:
            self.d.tap(*CLASS_TABS[self.cfg.support_class])  # 先切職階頁籤，冷卻後再找人
            return
        for _, (px, py) in match_all(self.img, self.cfg.support_player, SUPPORT_LIST):
            cx, cy = px + SUPPORT_SERVANT_OFFSET[0], py + SUPPORT_SERVANT_OFFSET[1]
            if match(self.img, self.cfg.support_servant, (cx - 26, cy - 14, cx + 26, cy + 14), 10)[0] >= 0.85:
                log("選擇助戰")
                self.d.tap(cx, cy)  # 點從者名字（點頭像會打開詳細資訊）
                return
        if self.support_scrolls >= self.cfg.support_max_scrolls:
            path = self._save_debug("support")
            raise Stop(f"捲了 {self.support_scrolls} 次都找不到指定助戰，截圖：{path}")
        self.support_scrolls += 1
        self.d.swipe(640, 600, 640, 250)

    def on_party_confirm(self):
        self._tap_template("quest_start_btn")

    # ---------- 戰鬥 ----------
    def on_battle_command(self):
        wave = detect_wave(self.img) or self.cur_wave or 1
        if wave != self.cur_wave:
            if self.cur_wave is not None and wave < self.cur_wave:
                self._reset_battle()  # 波次倒退 = 新的一場
            log(f"第 {wave} 波")
            self.cur_wave = wave
            self.queue = None
            self.turn_np = None
        self.last_wave = wave
        if self._run_script():
            return
        self._attack()

    def _run_script(self) -> bool:
        """做本波腳本的下一個動作。回傳 True 代表這一輪已經動作（或在等動作生效）。"""
        wave = self.cur_wave
        if wave in self.scripted_waves or wave not in self.cfg.script:
            return False
        if self.queue is None:
            self.queue = [a for a in self.cfg.script[wave] if a.kind != "np"]
            log(f"第 {wave} 波腳本：{' '.join(map(str, self.cfg.script[wave]))}")
        if self.pending is not None and self._check_pending():
            return True
        while self.queue:
            a = self.queue.pop(0)
            if a.kind == "skill":
                if not battle.skill_ready(self.img, a.servant, a.index):
                    log(f"{a} 冷卻中，跳過")
                    continue
                self._start(a)
                self.d.tap(*SKILL_POS[a.servant][a.index])
            else:
                self._start(a)
                self.d.tap(*MASTER_BTN)  # 先打開御主技能選單
            return True
        self.scripted_waves.add(wave)
        self.turn_np = [a.servant for a in self.cfg.script[wave] if a.kind == "np"]
        return False

    def _start(self, a: Action):
        self.pending, self.pending_time, self.pending_tries, self.master_tapped = a, self.clock(), 1, False

    def _retry_or_give_up(self, pos) -> bool:
        if self.clock() - self.pending_time < SKILL_CONFIRM_WAIT:
            return True  # 還在等動畫
        if self.pending_tries >= 3:
            log(f"{self.pending} 點了 3 次都沒反應，放棄")
            self.pending = None
            return False
        self.pending_tries += 1
        self.pending_time = self.clock()
        self.d.tap(*pos)
        return True

    def _check_pending(self) -> bool:
        """確認上一個動作生效了沒。回傳 True 代表這一輪要繼續等或已重點。"""
        a = self.pending
        if a.kind == "skill":
            if not battle.skill_ready(self.img, a.servant, a.index):
                self.pending = None  # 圖示變暗 = 已施放
                return False
            return self._retry_or_give_up(SKILL_POS[a.servant][a.index])

        # 御主技能
        if battle.master_menu_open(self.img):
            if self.master_tapped or not battle.master_skill_ready(self.img, a.index):
                log(f"{a} 沒有反應（可能冷卻中），關閉選單跳過")
                self.d.tap(*MASTER_BTN)
                self.pending = None
                return True
            self.d.tap(*MASTER_SKILL_POS[a.index])
            self.master_tapped = True
            self.pending_time = self.clock()
            return True
        if self.master_tapped:
            self.pending = None  # 點過技能、選單已收起 = 已施放
            return False
        return self._retry_or_give_up(MASTER_BTN)  # 選單沒打開，重點御主技能按鈕

    def _attack(self):
        planned = self.turn_np if self.turn_np is not None else ([1, 2, 3] if self.cfg.fallback_np else [])
        self.np_to_fire = [s for s in planned if battle.np_ready(self.img, s)]
        if self.turn_np is not None:
            for s in self.turn_np:
                if s not in self.np_to_fire:
                    log(f"np{s} 的 NP 沒滿，這回合改打普通卡")
        self.d.tap(*ATTACK)

    def _default_target(self) -> int:
        if self.pending is not None and self.pending.target:
            return self.pending.target
        nps = [a.servant for a in self.cfg.script.get(self.cur_wave, []) if a.kind == "np"]
        return nps[0] if nps else 1  # 沒指定就給這一波要開寶具的人

    def on_card_select(self):
        if self.entered:
            self.cards_clicked = set()
            self.card_order = battle.rank_cards(battle.card_colors(self.img), self.cfg.card_priority)
            nps = self.np_to_fire[:3]
            for s in nps:  # 寶具放前面
                self.d.tap(*NP_CARD_POS[s])
            picks = self.card_order[:3 - len(nps)]
            for i in picks:
                self.d.tap(*CARD_POS[i])
            self.cards_clicked.update(picks)
            log(f"出卡：{' '.join([f'np{s}' for s in nps] + [f'卡{i + 1}' for i in picks])}")
            self.np_to_fire = []
            self.turn_np = None
            return
        # 冷卻後還停在選卡畫面：大概寶具卡沒選到（NP 判斷錯），補點一張還沒點過的卡
        rest = [i for i in self.card_order if i not in self.cards_clicked]
        if rest:
            log(f"選卡畫面還在，補點卡{rest[0] + 1}")
            self.d.tap(*CARD_POS[rest[0]])
            self.cards_clicked.add(rest[0])

    def on_wipe_out(self):
        # 全滅：什麼都不點（絕不使用令咒或聖晶石），交給使用者決定是否撤退
        path = self._save_debug("wipe_out")
        raise Stop(f"全滅了，畫面停在「接關」視窗，請自己決定是否撤退。截圖：{path}")

    def on_skill_target(self):
        if self.pending is None:  # 不是我們開的技能，關掉
            self._tap_template("skill_target_close")
            return
        target = self._default_target()
        log(f"{self.pending} 目標 → {target} 號位")
        self.d.tap(*TARGET_POS[target])
        self.pending_time = self.clock()  # 選完目標才開始放技能，重新計時

    def on_result_tap(self):
        self._tap_template("tap_screen", margin=60)  # 點「請點擊畫面」字上，不會點到掉落的紋章卡

    def on_result_next(self):
        self._tap_template("next_btn")

    def on_cc_detail(self):
        self._tap_template("cc_close_btn")

    def on_continue_sortie(self):
        if self.entered:
            self.runs_done += 1
            now = self.clock()
            log(f"完成第 {self.runs_done} 場，耗時 {now - self.run_started:.0f} 秒")
            self.run_started = now
            self.last_wave = None
        if self.cfg.runs is not None and self.runs_done >= self.cfg.runs:
            self._tap_template("continue_close_btn")
            raise Stop(f"已完成 {self.runs_done} 場")
        self._tap_template("continue_btn")
