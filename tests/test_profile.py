"""設定組的存讀，以及 Bot 從外部停止。"""
import threading

import pytest

from bot import Bot
from profile_store import Profile, build_default


def test_builtin_default_profile():
    p = build_default()
    assert (p.support.player, p.support.servant) == ("VOYOV", "摩根")
    assert p.support.class_tab == "berserker"
    assert p.waves[2] == ["s3-1", "s3-3", "s2-3", "np3"]


def test_roundtrip(tmp_path):
    p = build_default()
    p.name, p.runs, p.max_apples, p.apples = "活動 90++", 40, 30, ["gold"]
    p.support.mlb, p.support.min_level, p.support.min_np = True, 120, 5
    p.waves[1] = ["s1-1>2", "m3", "np2"]
    p.save(tmp_path / "event")
    q = Profile.load(tmp_path / "event")
    assert (q.name, q.runs, q.max_apples, q.apples) == ("活動 90++", 40, 30, ["gold"])
    assert q.support.mlb and (q.support.player, q.support.servant) == ("VOYOV", "摩根")
    assert (q.support.min_level, q.support.min_np) == (120, 5)
    assert q.waves[1] == ["s1-1>2", "m3", "np2"]


def test_unlimited_runs_saved_as_zero(tmp_path):
    p = Profile(runs=None)
    p.save(tmp_path)
    assert Profile.load(tmp_path).runs is None


def test_removed_ce_image_is_deleted(tmp_path):
    import numpy as np
    p = build_default()
    p.support.ce = np.zeros((30, 90, 3), np.uint8)
    p.save(tmp_path)
    assert (tmp_path / "support_ce.png").exists()
    p.support.ce = None
    p.save(tmp_path)
    assert not (tmp_path / "support_ce.png").exists()
    assert Profile.load(tmp_path).support.ce is None


def test_bad_script_rejected(tmp_path):
    with pytest.raises(ValueError):
        Profile(waves={1: ["s9-9"]}).save(tmp_path)


def test_bot_stops_from_another_thread():
    class Dev:
        def screenshot(self):
            from vision import ROOT, imread
            return imread(ROOT / "screenshots" / "quest_select.png")  # 停在選關，一直等

    logs = []
    bot = Bot(Dev(), Profile().to_config(), logger=logs.append, sleep=lambda s: None)
    t = threading.Thread(target=bot.run)
    t.start()
    bot.stop()
    t.join(timeout=5)
    assert not t.is_alive()
    assert any("手動停止" in m for m in logs)
