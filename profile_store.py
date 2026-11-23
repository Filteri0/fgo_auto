"""設定組：一個關卡的周回設定（場數、蘋果、助戰條件、戰鬥腳本）存成一個資料夾。

    profiles/<資料夾>/profile.toml        設定
    profiles/<資料夾>/support_ce.png      助戰的禮裝條件圖（從支援列表切下來的）

命令列（main.py --profile）和圖形介面讀寫的是同一份。
"""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from battle import parse_script
from bot import APPLES, Config
from support import SupportSpec
from vision import ROOT

PROFILES_DIR = ROOT / "profiles"
DEFAULT_PROFILE = "default"


@dataclass
class Profile:
    name: str = "新設定組"
    runs: int | None = None                       # None = 無限
    apples: list[str] = field(default_factory=lambda: ["silver", "gold"])
    max_apples: int = 0
    support: SupportSpec = field(default_factory=SupportSpec)
    support_max_refresh: int = 20
    card_priority: str = "BAQ"
    fallback_np: bool = True
    waves: dict[int, list[str]] = field(default_factory=dict)  # 波次 → 動作字串（例如 "s2-1"）
    party: list[str] = field(default_factory=lambda: ["1號位", "2號位", "3號位"])  # 只用來顯示

    # ---- 轉成 Bot 用的設定 ----
    def to_config(self) -> Config:
        return Config(
            runs=self.runs, apples=list(self.apples), max_apples=self.max_apples,
            support=self.support, support_max_refresh=self.support_max_refresh,
            script=parse_script({str(k): v for k, v in self.waves.items()}),
            card_priority=self.card_priority, fallback_np=self.fallback_np,
        )

    def validate(self) -> None:
        """有錯就丟 ValueError（介面存檔前用來提示）。"""
        bad = [a for a in self.apples if a not in APPLES]
        if bad:
            raise ValueError(f"不認識的果實：{bad}")
        self.to_config()  # 會檢查腳本語法

    # ---- 存讀 ----
    def save(self, folder: Path) -> None:
        self.validate()
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("support_*.png"):  # 取消的條件不要留舊圖
            old.unlink()
        sup = self.support.save(folder)
        lines = [
            f"name = {_q(self.name)}",
            "",
            "[farm]",
            f"runs = {self.runs or 0}            # 0 = 無限",
            f"apples = {_list(self.apples)}   # 可以吃的果實與順序；聖晶石永遠不會吃",
            f"max_apples = {self.max_apples}",
            "",
            "[support]   # 空字串 / 0 = 不限",
            f"player = {_q(sup['player'])}        # 玩家名稱（OCR 比對，容許讀錯一個字）",
            f"servant = {_q(sup['servant'])}       # 從者名稱",
            f"min_level = {sup['min_level']}          # 從者等級至少",
            f"min_np = {sup['min_np']}             # 寶具等級至少",
            f"ce = {_q(sup['ce'])}            # 禮裝圖（同資料夾），空字串 = 不限",
            f"mlb = {_bool(sup['mlb'])}              # 禮裝要滿破",
            f"class_tab = {_q(sup['class_tab'])}   # 職階頁籤，空字串 = 不切換",
            f"max_refresh = {self.support_max_refresh}",
            "",
            "[battle]",
            f"card_priority = {_q(self.card_priority)}",
            f"fallback_np = {_bool(self.fallback_np)}",
            f"party = {_list(self.party)}   # 1~3 號位的名字（只用來顯示）",
            "",
            "[battle.waves]   # s2-1 = 2號位技能1；s2-3>1 = 目標1號位；m1 = 御主技能1；np2 = 2號位寶具",
            *[f"{w} = {_list(a)}" for w, a in sorted(self.waves.items())],
        ]
        (folder / "profile.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, folder: Path) -> "Profile":
        with open(folder / "profile.toml", "rb") as f:
            d = tomllib.load(f)
        farm, sup, bat = d.get("farm", {}), d.get("support", {}), d.get("battle", {})
        return cls(
            name=d.get("name", folder.name),
            runs=farm.get("runs") or None,
            apples=list(farm.get("apples", ["silver", "gold"])),
            max_apples=int(farm.get("max_apples", 0)),
            support=SupportSpec.load(folder, sup),
            support_max_refresh=int(sup.get("max_refresh", 20)),
            card_priority=str(bat.get("card_priority", "BAQ")).upper(),
            fallback_np=bool(bat.get("fallback_np", True)),
            waves={int(k): list(v) for k, v in bat.get("waves", {}).items()},
            party=(list(bat.get("party", [])) + ["1號位", "2號位", "3號位"])[:3] if bat.get("party")
            else ["1號位", "2號位", "3號位"],
        )


def list_profiles() -> list[tuple[str, str]]:
    """[(資料夾名, 顯示名稱)]"""
    out = []
    for p in sorted(PROFILES_DIR.glob("*/profile.toml")):
        try:
            out.append((p.parent.name, Profile.load(p.parent).name))
        except Exception:  # 壞掉的設定組不要讓整個清單掛掉
            out.append((p.parent.name, f"{p.parent.name}（讀取失敗）"))
    return out


def profile_dir(key: str) -> Path:
    return PROFILES_DIR / key


def new_profile_key() -> str:
    """新設定組的資料夾名稱（顯示名稱另外存在 profile.toml，可以用中文）。"""
    import time
    base = time.strftime("p%Y%m%d_%H%M%S")
    key, i = base, 2
    while profile_dir(key).exists():
        key, i = f"{base}_{i}", i + 1
    return key


def build_default() -> Profile:
    """內建的預設設定（VOYOV 的摩根 + 原本 battle.toml 的腳本），不讀也不寫檔案。

    測試用這個，不要讀 profiles/default：那份使用者會在介面裡改。
    """
    spec = SupportSpec(player="VOYOV", servant="摩根", class_tab="berserker")
    return Profile(
        name="預設（VOYOV 的摩根）",
        support=spec,
        waves={1: ["s2-1", "s1-3", "m1", "np2"], 2: ["s3-1", "s3-3", "s2-3", "np3"],
               3: ["s1-1", "s1-2", "s1-3", "np1"]},
        party=["迪亞馬特", "摩根", "摩根（助戰）"],
    )


def create_default() -> Profile:
    """第一次執行、還沒有任何設定組時，建立預設設定組。"""
    p = build_default()
    p.save(profile_dir(DEFAULT_PROFILE))
    return p


# ---- 小型 TOML 輸出（標準庫只有讀，沒有寫） ----
def _q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _list(items) -> str:
    return "[" + ", ".join(_q(i) for i in items) + "]"


def _bool(b: bool) -> str:
    return "true" if b else "false"




if __name__ == "__main__":
    create_default()
    print("已建立", profile_dir(DEFAULT_PROFILE))
