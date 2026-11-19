"""FGO 自動周回（命令列版）。設定都在設定組裡，參數可以臨時覆蓋。

範例：
    uv run python main.py                              # 用預設設定組
    uv run python main.py --profile default --runs 10 --max-apples 5
    uv run python main.py --list                       # 列出所有設定組

圖形介面：uv run python gui.py
"""
import argparse

from bot import APPLES, Bot
from profile_store import DEFAULT_PROFILE, Profile, create_default, list_profiles, profile_dir


def main():
    p = argparse.ArgumentParser(description="FGO 自動周回（台服 / MuMu 1280x720）")
    p.add_argument("--profile", default=DEFAULT_PROFILE, help="設定組資料夾名稱（profiles/ 底下）")
    p.add_argument("--list", action="store_true", help="列出所有設定組")
    p.add_argument("--runs", type=int, help="覆蓋場數，0 = 無限")
    p.add_argument("--apples", help=f"覆蓋可以吃的果實與順序，逗號分隔：{','.join(APPLES)}")
    p.add_argument("--max-apples", type=int, help="覆蓋最多吃幾顆果實")
    p.add_argument("--serial", default="127.0.0.1:16384", help="ADB 裝置位址")
    args = p.parse_args()

    if not profile_dir(DEFAULT_PROFILE).exists():
        create_default()
    if args.list:
        for key, name in list_profiles():
            print(f"{key:20s} {name}")
        return

    prof = Profile.load(profile_dir(args.profile))
    if args.runs is not None:
        prof.runs = args.runs or None
    if args.apples:
        prof.apples = [a.strip() for a in args.apples.split(",") if a.strip()]
    if args.max_apples is not None:
        prof.max_apples = args.max_apples
    print(f"設定組：{prof.name}　助戰條件：{prof.support.describe()}")

    from device import Device  # 放這裡：只看 --help / --list 時不用連模擬器

    Bot(Device(args.serial), prof.to_config()).run()


if __name__ == "__main__":
    main()
