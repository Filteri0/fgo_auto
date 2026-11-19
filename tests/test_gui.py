"""圖形介面：離屏建立視窗，檢查各分頁和設定組之間的讀寫。不開模擬器、不動到真的 profiles/。"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import pytest  # noqa: E402
from PySide6.QtCore import QSettings, Qt  # noqa: E402

import profile_store  # noqa: E402
from profile_store import Profile  # noqa: E402
from vision import ROOT, imread  # noqa: E402


@pytest.fixture
def win(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_store, "PROFILES_DIR", tmp_path / "profiles")
    from ui.app import MainWindow, make_app
    app = make_app([])
    w = MainWindow(QSettings(str(tmp_path / "gui.ini"), QSettings.Format.IniFormat))
    yield w
    w.dirty = False
    w.close()
    app.processEvents()


def test_opens_default_profile_clean(win):
    assert win.key == "default" and not win.dirty
    assert win.script.party() == ["迪亞馬特", "摩根", "摩根（助戰）"]
    assert win.support.checks["player"].isChecked() and win.support.checks["servant"].isChecked()
    assert not win.support.checks["ce"].isChecked()


def test_edit_marks_dirty_and_save_roundtrip(win, tmp_path):
    win.farm.runs.setValue(40)
    win.farm.max_apples.setValue(30)
    assert win.dirty
    assert win.save() and not win.dirty
    p = Profile.load(tmp_path / "profiles" / "default")
    assert p.runs == 40 and p.max_apples == 30


def test_apple_order_and_unchecked(win):
    lw = win.farm.apple_list
    lw.item(0).setCheckState(Qt.CheckState.Unchecked)  # 白銀不吃
    prof = win._collect()
    assert prof.apples == ["gold"]


def test_script_skill_inserted_before_np(win):
    win.script.wave_group.button(1).setChecked(True)
    win.script._add("s3-2>1")
    assert win.script.waves()[1] == ["s2-1", "s1-3", "m1", "s3-2>1", "np2"]
    item = win.script.lists[1].item(3)
    assert item.text() == "摩根（助戰）　技能 2  →  迪亞馬特"


def test_script_party_rename_updates_items(win):
    win.script.party_edits[0].setText("提亞馬特")
    assert win.script.lists[3].item(0).text().startswith("提亞馬特")
    assert win._collect().party[0] == "提亞馬特"


def test_script_warns_np_before_skill(win):
    lw = win.script.lists[1]
    lw.insertItem(0, win.script._make_item("np1"))
    win.script._emit_changed()
    assert "寶具要排在所有技能後面" in win.script.warn.text()


def test_support_pick_row_and_match(win):
    tab = win.support
    tab.set_shot(imread(ROOT / "screenshots" / "support_select_no_voyov.png"))
    assert len(tab.rows) == 2
    tab.select_row(tab.rows[1])            # JetSet 的摩根
    tab.checks["player"].setChecked(False)
    tab.checks["np"].setChecked(True)
    spec = tab.current_spec()
    assert set(spec.templates) == {"servant", "np"}
    tab.test_match()
    assert list(tab.match_result.values()) == [False, True]


def test_support_mlb_and_class_saved(win, tmp_path):
    win.support.mlb.setChecked(True)
    win.support.class_tab.setCurrentIndex(win.support.class_tab.findData("caster"))
    assert win.save()
    p = Profile.load(tmp_path / "profiles" / "default")
    assert p.support.mlb and p.support.class_tab == "caster"


def test_new_and_duplicate_profile(win, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("火種本", True)))
    win.new_profile()
    assert win.prof.name == "火種本" and win.profile_box.count() == 2
    assert win.script.waves() == {}
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("火種本 複本", True)))
    win.duplicate_profile()
    assert win.profile_box.count() == 3 and win.prof.name == "火種本 複本"
