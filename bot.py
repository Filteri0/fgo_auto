"""周回主迴圈：截圖 → 辨識狀態 → 做一個動作 → 重來。

每個狀態只做「一個」動作就回到迴圈重新截圖，不在同一個狀態裡串好幾步，
這樣網路卡頓或動畫變慢時，下一輪看到的仍是真實畫面。
"""
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2

import battle
import support as sup
from battle import Action, CARD_POS, MASTER_BTN, MASTER_SKILL_POS, NP_CARD_POS, SKILL_POS, TARGET_POS
from states import detect_state, detect_wave
from support import SupportSpec
from templates import SPECS
from vision import ROOT, imwrite, match

APPLES = ("gold", "silver", "bronze", "copper")  # 聖晶石刻意不在這裡，程式沒有任何吃石頭的路徑
APPLE_ZH = {"gold": "黃金果實", "silver": "白銀果實", "bronze": "青銅果實", "copper": "赤銅果實"}

# 固定座標（1280x720）
ATTACK = (1140, 600)
# 認不出畫面時點這裡：右上「BATTLE n/3」資訊欄，各畫面都沒有按鈕。
# 換過的位置：(1240,330) 是戰鬥的御主技能按鈕；(40,300) 是禮裝 / 紋章詳細頁的「標記」按鈕。
SAFE_TAP = (900, 30)
SKILL_CONFIRM_WAIT = 3.0          # 點技能後等這麼久，技能還亮著才判定沒點到
UI_READY_FRAMES = 2               # 戰鬥指令 UI 要連續幾張截圖都完整才動作
NP_MIN_FRAMES = 4                 # NP 滿的「>>」會閃：要開的寶具還沒看到滿，最少看這麼多張再放棄
CARD_STABLE_DIFF = 15             # 選卡區連續兩張縮圖的平均差異低於這個 = 卡片落定
CARD_MAX_WAIT = 4.0               # 卡片一直判斷不穩定時，最多等這麼久就照最新的卡色出卡
APPLE_LIST = (300, 100, 440, 575)  # AP恢復視窗裡果實圖示所在的直條
SUPPORT_LIST = (230, 170, 830, 720)  # 用來判斷列表捲到底的區域
# 支援選擇上方的職階頁籤（目前只有狂職的位置在實機確認過）
CLASS_TABS = {
    "all": (92, 128), "saber": (160, 128), "archer": (228, 128), "lancer": (295, 128),
    "rider": (362, 128), "caster": (430, 128), "assassin": (497, 128), "berserker": (565, 128),
    "extra": (632, 128), "mix": (698, 128),
}
CLASS_TAB_MAX_TRIES = 5
REFRESH_BTN = (930, 128)          # 支援選擇右上「列表更新」
REFRESH_SETTLE = 2.0              # 列表更新後等列表載入
LIST_BOTTOM_DIFF = 3              # 捲動前後列表縮圖差異低於這個 = 已經捲到底


def class_tab_selected(img, cls: str) -> bool:
    """被選中的職階頁籤有一圈藍色亮框：藍色像素約 17~20%，沒選中的 <= 2%。"""
    x, _ = CLASS_TABS[cls]
    hsv = cv2.cvtColor(img[100:158, x - 32:x + 32], cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return float(((h >= 95) & (h <= 125) & (s > 120) & (v > 150)).mean()) > 0.08


class Stop(Exception):
    """正常或異常的停止，訊息會印給使用者。"""


@dataclass
class Config:
    runs: int | None = None                 # None = 無限
    apples: list[str] = field(default_factory=lambda: ["gold", "silver"])
    max_apples: int = 0                      # 0 = 不吃
    support: SupportSpec = field(default_factory=SupportSpec)  # 指定助戰的條件（含職階頁籤）
    support_max_refresh: int = 20            # 找不到指定助戰時最多按幾次「列表更新」
    unknown_tap_after: float = 5.0
    unknown_timeout: float = 120.0
    support_max_scrolls: int = 15  # 捲到底會自動重刷，這只是保險上限（實機 5 次曾在差一列時就放棄）
    loop_delay: float = 0.5
    action_cooldown: float = 1.5  # 同一個畫面做完動作後，等這麼久才會再動作（避免動畫中重複點）
    # 戰鬥
    script: dict[int, list[Action]] = field(default_factory=dict)  # 波次 → 動作，見 battle.py
    card_priority: str = "BAQ"    # 普通卡顏色優先順序
    fallback_np: bool = True      # 補刀回合（腳本跑完還在同一波）NP 滿就放寶具


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class Bot:
    def __init__(self, device, config: Config, clock=time.monotonic, sleep=time.sleep, logger=None):
        bad = [a for a in config.apples if a not in APPLES]
        if bad:
            raise ValueError(f"不認識的果實：{bad}（可用：{', '.join(APPLES)}）")
        cls = config.support.class_tab
        if cls is not None and cls not in CLASS_TABS:
            raise ValueError(f"不認識的職階：{cls}（可用：{', '.join(CLASS_TABS)}）")
        if sorted(config.card_priority) != sorted("BAQ"):
            raise ValueError(f"card_priority 要是 B、A、Q 的排列：{config.card_priority!r}")
        self.d = device
        self.cfg = config
        self.clock = clock
        self.sleep = sleep
        self.log = logger or log           # 介面可以把 log 導到自己的視窗
        self.stop_event = threading.Event()  # 介面按「停止」時 set

        self.runs_done = 0
        self.apples_used = 0
        self.run_started = clock()
        self.last_state: str | None = None
        self.cur_state: str | None = None
        self.last_wave: int | None = None
        self.unknown_since: float | None = None
        self.last_unknown_tap = 0.0
        self.support_scrolls = 0
        self.class_tab_tries = 0
        self.support_refreshes = 0        # 這次選助戰按了幾次列表更新（選到人才歸零）
        self.last_refresh = -1e9
        self.support_list_sig = None      # 上次捲動前的列表縮圖，用來判斷捲到底
        self.support_still = 0            # 連續幾次捲動後畫面沒變（2 次才算到底，避免卡頓吃掉滑動）
        self.refresh_wait_logged = False
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
        self.np_seen: set[int] = set()          # 這回合任何一張就緒截圖看到 NP 滿的人
        self.np_frames = 0                      # 這回合看過幾張就緒截圖
        self.ui_ready_streak = 0
        self._reset_cards()

    def _reset_cards(self):
        self.card_order: list[int] | None = None   # None = 這次選卡畫面還沒出卡
        self.cards_clicked: set[int] = set()
        self.card_prev = None                       # (卡色, 縮圖) 上一張
        self.card_wait_start = self.clock()

    # ---------- 主迴圈 ----------
    def run(self) -> None:
        self.log(f"開始周回：場數={self.cfg.runs or '無限'}，果實={self.cfg.apples}，上限={self.cfg.max_apples}")
        try:
            while not self.stop_event.is_set():
                self.step()
                self.sleep(self.cfg.loop_delay)
            self.log("停止：手動停止")
        except Stop as e:
            self.log(f"停止：{e}")
        except KeyboardInterrupt:
            self.log("停止：手動停止（Ctrl+C）")
        self.log(f"總計：完成 {self.runs_done} 場，吃了 {self.apples_used} 顆果實")

    def stop(self) -> None:
        """從別的執行緒要求停止：目前這一步做完就停，不會中斷到一半。"""
        self.stop_event.set()

    def status(self) -> dict:
        """給介面顯示的即時狀態。"""
        return {"state": self.cur_state, "wave": self.cur_wave, "runs_done": self.runs_done,
                "runs": self.cfg.runs, "apples_used": self.apples_used, "max_apples": self.cfg.max_apples}

    def step(self) -> str | None:
        self.img = self.d.screenshot()
        state = detect_state(self.img)
        self.cur_state = state  # 這一輪實際辨識到的（None = 認不出），給介面顯示

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
        acted = getattr(self, f"on_{state}")()
        if acted is not False:  # 回傳 False = 畫面還沒準備好、這輪只是在等，不算動作
            self.last_action = now
        return state

    def _on_leave(self, old, new):
        if old == "support_select":
            self.support_scrolls = 0
            self.class_tab_tries = 0
            self.support_list_sig = None
            self.support_still = 0
        if old in ("ap_recover", "apple_confirm") and new not in ("ap_recover", "apple_confirm"):
            self.apple_scrolls = 0
            self.apple_tries.clear()
        if new != "quest_select":
            self.waiting_hint_shown = False
        if new in ("support_select", "party_confirm", "continue_sortie"):
            self._reset_battle()
        if new == "card_select":
            self._reset_cards()
        if old == "battle_command":
            self.ui_ready_streak = 0

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
            self.log("在選關畫面：請手動點進要周回的關卡（程式會等你）")
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
                self.log(f"{APPLE_ZH[apple]} 似乎用完了，改用下一種")
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
                self.log(f"吃了 {APPLE_ZH[apple]}（第 {self.apples_used}/{self.cfg.max_apples} 顆）")
        else:
            self.d.tap(*match(self.img, "confirm_cancel_btn", cancel_box, 0)[1])
            path = self._save_debug("apple_confirm")
            raise Stop(f"確認視窗的道具不是允許的果實（辨識={apple} {scores[apple]:.2f}），已取消。截圖：{path}")

    def on_support_select(self):
        spec = self.cfg.support
        cls = spec.class_tab
        if cls and not class_tab_selected(self.img, cls):
            # 頁籤沒切成功（例如模擬器卡頓吃掉點擊）就再點，確認切好了才找人
            if self.class_tab_tries >= CLASS_TAB_MAX_TRIES:
                path = self._save_debug("class_tab")
                raise Stop(f"點了 {self.class_tab_tries} 次都切不到 {cls} 頁籤，截圖：{path}")
            self.class_tab_tries += 1
            self.support_scrolls = 0  # 切頁籤後列表回到最上面
            self.d.tap(*CLASS_TABS[cls])
            return
        if self.clock() - self.last_refresh < REFRESH_SETTLE:
            return False  # 剛按完列表更新，等列表載入
        # 只看整列都在畫面內的（被切掉一半的列欄位不完整，捲下去再看）
        for row in sup.find_rows(self.img):
            if sup.row_matches(self.img, row, spec):
                self.log("選擇助戰" + (f"（列表更新了 {self.support_refreshes} 次）" if self.support_refreshes else ""))
                self.d.tap(*sup.tap_point(row))  # 點從者名字（點頭像會打開詳細資訊）
                self.support_refreshes = 0
                return

        # 找不到：先往下捲；捲到底（畫面沒變）或捲夠多次就按「列表更新」重刷
        sig = self._support_list_sig()
        unchanged = (self.support_list_sig is not None
                     and float(abs(sig - self.support_list_sig).mean()) < LIST_BOTTOM_DIFF)
        self.support_still = self.support_still + 1 if unchanged else 0
        at_bottom = self.support_still >= 2
        if not at_bottom and self.support_scrolls < self.cfg.support_max_scrolls:
            self.support_scrolls += 1
            self.support_list_sig = sig
            self.d.swipe(640, 600, 640, 250)
            return
        return self._refresh_support_list()

    def _support_list_sig(self):
        x1, y1, x2, y2 = SUPPORT_LIST
        gray = cv2.cvtColor(self.img[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, (60, 55), interpolation=cv2.INTER_AREA).astype("int16")

    def _refresh_support_list(self):
        if self.support_refreshes >= self.cfg.support_max_refresh:
            path = self._save_debug("support")
            raise Stop(f"列表更新了 {self.support_refreshes} 次都找不到指定助戰，截圖：{path}")
        if match(self.img, "refresh_btn_ready", SPECS["refresh_btn_ready"][1])[0] < 0.85:
            if not self.refresh_wait_logged:
                self.log("找不到指定助戰，等「列表更新」冷卻")
                self.refresh_wait_logged = True
            return False  # 按鈕還在倒數，先等
        self.support_refreshes += 1
        self.refresh_wait_logged = False
        self.log(f"找不到指定助戰，列表更新（第 {self.support_refreshes} 次）")
        self.d.tap(*REFRESH_BTN)

    def on_refresh_confirm(self):
        self._tap_template("refresh_yes_btn")
        self.last_refresh = self.clock()
        self.support_scrolls = 0
        self.support_list_sig = None
        self.support_still = 0

    def on_refresh_cooldown(self):
        self._tap_template("refresh_close_btn")  # 冷卻中：關掉提示，回到列表等冷卻

    def on_party_confirm(self):
        self._tap_template("quest_start_btn")

    # ---------- 戰鬥 ----------
    def on_battle_command(self):
        # 技能列和 Attack 完整出現（連續幾張）才判斷，避免淡入 / 技能動畫中把技能誤判成冷卻
        if not battle.ui_ready(self.img):
            self.ui_ready_streak = 0
            return False
        self.ui_ready_streak += 1
        # NP 滿的箭頭會閃爍，單張可能拍到暗的瞬間：同一回合 NP 只增不減，任一張看到滿就算
        self.np_seen.update(s for s in (1, 2, 3) if battle.np_ready(self.img, s))
        self.np_frames += 1
        if self.ui_ready_streak < UI_READY_FRAMES:
            return False

        wave = detect_wave(self.img) or self.cur_wave or 1
        if wave != self.cur_wave:
            if self.cur_wave is not None and wave < self.cur_wave:
                self._reset_battle()  # 波次倒退 = 新的一場
            self.log(f"第 {wave} 波")
            self.cur_wave = wave
            self.queue = None
            self.turn_np = None
        self.last_wave = wave
        result = self._run_script()
        if result is None:
            result = self._attack()
        self.ui_ready_streak = 0  # 動作（或確認完一個動作）後，等 UI 重新穩定再判斷下一步
        return result is not False

    # _run_script 回傳：True = 這輪點了東西；False = 這輪只是在等；None = 腳本做完，該按 Attack

    def _run_script(self) -> bool | None:
        """做本波腳本的下一個動作。"""
        wave = self.cur_wave
        if wave in self.scripted_waves or wave not in self.cfg.script:
            return None
        if self.queue is None:
            self.queue = [a for a in self.cfg.script[wave] if a.kind != "np"]
            self.log(f"第 {wave} 波腳本：{' '.join(map(str, self.cfg.script[wave]))}")
        if self.pending is not None:
            r = self._check_pending()
            if r is not None:
                return r
            # 上一個動作剛確認完成：這張截圖可能還帶著施放動畫，等新的穩定畫面再判斷下一個技能
            return False
        while self.queue:
            a = self.queue.pop(0)
            if a.kind == "skill":
                if not battle.skill_ready(self.img, a.servant, a.index):
                    self.log(f"{a} 冷卻中，跳過")
                    continue
                self._start(a)
                self.d.tap(*SKILL_POS[a.servant][a.index])
            else:
                self._start(a)
                self.d.tap(*MASTER_BTN)  # 先打開御主技能選單
            return True
        self.scripted_waves.add(wave)
        self.turn_np = [a.servant for a in self.cfg.script[wave] if a.kind == "np"]
        return None

    def _start(self, a: Action):
        self.pending, self.pending_time, self.pending_tries, self.master_tapped = a, self.clock(), 1, False

    def _retry_or_give_up(self, pos) -> bool | None:
        if self.clock() - self.pending_time < SKILL_CONFIRM_WAIT:
            return False  # 還在等動畫
        if self.pending_tries >= 3:
            self.log(f"{self.pending} 點了 3 次都沒反應，放棄")
            self.pending = None
            return None
        self.pending_tries += 1
        self.pending_time = self.clock()
        self.log(f"{self.pending} 好像沒點到，重點第 {self.pending_tries} 次")
        self.d.tap(*pos)
        return True

    def _check_pending(self) -> bool | None:
        """確認上一個動作生效了沒。回傳 None = 已完成（或放棄）；False = 還在等；True = 這輪點了東西。"""
        a = self.pending
        if a.kind == "skill":
            if not battle.skill_ready(self.img, a.servant, a.index):
                self.pending = None  # UI 完整時圖示變暗 = 已施放
                return None
            return self._retry_or_give_up(SKILL_POS[a.servant][a.index])

        # 御主技能
        if battle.master_menu_open(self.img):
            if self.master_tapped or not battle.master_skill_ready(self.img, a.index):
                self.log(f"{a} 沒有反應（可能冷卻中），關閉選單跳過")
                self.d.tap(*MASTER_BTN)
                self.pending = None
                return True
            self.d.tap(*MASTER_SKILL_POS[a.index])
            self.master_tapped = True
            self.pending_time = self.clock()
            return True
        if self.master_tapped:
            self.pending = None  # 點過技能、選單已收起 = 已施放
            return None
        return self._retry_or_give_up(MASTER_BTN)  # 選單沒打開，重點御主技能按鈕

    def _attack(self) -> bool:
        planned = self.turn_np if self.turn_np is not None else ([1, 2, 3] if self.cfg.fallback_np else [])
        if not set(planned) <= self.np_seen and self.np_frames < NP_MIN_FRAMES:
            # 腳本回合要開的、或補刀回合任何一個寶具還沒看到滿：多看幾張
            # （NP 滿的箭頭會閃，可能剛好都拍到暗的瞬間；實機補刀回合曾因此漏放寶具）
            return False
        self.np_to_fire = [s for s in planned if s in self.np_seen]
        if self.turn_np is not None:
            for s in self.turn_np:
                if s not in self.np_to_fire:
                    self.log(f"np{s} 的 NP 沒滿，這回合改打普通卡")
        self.d.tap(*ATTACK)
        self.np_seen, self.np_frames = set(), 0  # 下一回合重新累積
        return True

    def _default_target(self) -> int:
        if self.pending is not None and self.pending.target:
            return self.pending.target
        nps = [a.servant for a in self.cfg.script.get(self.cur_wave, []) if a.kind == "np"]
        return nps[0] if nps else 1  # 沒指定就給這一波要開寶具的人

    def on_card_select(self):
        if self.card_order is None:
            # 卡片剛出現時還在飛入 / 翻轉，卡色會讀錯：連續兩張卡色相同、畫面幾乎不動才出卡
            colors = battle.card_colors(self.img)
            sig = battle.card_area_signature(self.img)
            prev, self.card_prev = self.card_prev, (colors, sig)
            stable = (prev is not None and prev[0] == colors
                      and float(abs(prev[1] - sig).mean()) < CARD_STABLE_DIFF)
            if not stable:
                if self.clock() - self.card_wait_start < CARD_MAX_WAIT:
                    return False
                self.log("卡片一直沒有穩定，照目前的卡色出卡")
            self.card_order = battle.rank_cards(colors, self.cfg.card_priority)
            nps = self.np_to_fire[:3]
            for s in nps:  # 寶具放前面
                self.d.tap(*NP_CARD_POS[s])
            picks = self.card_order[:3 - len(nps)]
            for i in picks:
                self.d.tap(*CARD_POS[i])
            self.cards_clicked.update(picks)
            self.log(f"出卡：{' '.join([f'np{s}' for s in nps] + [f'卡{i + 1}' for i in picks])}")
            self.np_to_fire = []
            self.turn_np = None
            return
        # 冷卻後還停在選卡畫面：大概寶具卡沒選到（NP 判斷錯），補點一張還沒點過的卡
        rest = [i for i in self.card_order if i not in self.cards_clicked]
        if rest:
            path = self._save_debug("card_topup")  # 留證據：通常是寶具卡沒選到（NP 誤判？）
            self.log(f"選卡畫面還在，補點卡{rest[0] + 1}（截圖：{path.name}）")
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
        self.log(f"{self.pending} 目標 → {target} 號位")
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
            self.log(f"完成第 {self.runs_done} 場，耗時 {now - self.run_started:.0f} 秒")
            self.run_started = now
            self.last_wave = None
        if self.cfg.runs is not None and self.runs_done >= self.cfg.runs:
            self._tap_template("continue_close_btn")
            raise Stop(f"已完成 {self.runs_done} 場")
        self._tap_template("continue_btn")
