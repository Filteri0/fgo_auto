"""FGO 自動周回。

範例：
    uv run python main.py --runs 10 --apples gold,silver --max-apples 5
    uv run python main.py --max-apples 20          # 無限周回，最多吃 20 顆（預設先金後銀）
    uv run python main.py --script other.toml      # 換一份戰鬥腳本
"""
import argparse
import tomllib
from pathlib import Path

from battle import parse_script
from bot import APPLES, Bot, Config

DEFAULT_SCRIPT = Path(__file__).parent / "battle.toml"


def load_script(path: Path) -> dict:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return {
        "script": parse_script(data.get("waves", {})),
        "card_priority": data.get("card_priority", "BAQ").upper(),
        "fallback_np": bool(data.get("fallback_np", True)),
    }


def main():
    p = argparse.ArgumentParser(description="FGO 自動周回（台服 / MuMu 1280x720）")
    p.add_argument("--runs", type=int, default=None, help="要打幾場，不給 = 無限（直到 AP 和果實用完）")
    p.add_argument("--apples", default="gold,silver",
                   help=f"可以吃的果實與順序，逗號分隔：{','.join(APPLES)}。聖晶石永遠不會吃")
    p.add_argument("--max-apples", type=int, default=0, help="最多吃幾顆果實（預設 0 = 不吃）")
    p.add_argument("--script", type=Path, default=DEFAULT_SCRIPT,
                   help="戰鬥腳本（TOML），預設 battle.toml；檔案不存在就只會硬打")
    p.add_argument("--serial", default="127.0.0.1:16384", help="ADB 裝置位址")
    args = p.parse_args()

    battle_cfg = load_script(args.script) if args.script.exists() else {}
    if not battle_cfg:
        print(f"找不到戰鬥腳本 {args.script}，只會按 Attack 硬打")

    from device import Device  # 放這裡：只看 --help 時不用連模擬器

    config = Config(
        runs=args.runs,
        apples=[a.strip() for a in args.apples.split(",") if a.strip()],
        max_apples=args.max_apples,
        **battle_cfg,
    )
    Bot(Device(args.serial), config).run()


if __name__ == "__main__":
    main()
