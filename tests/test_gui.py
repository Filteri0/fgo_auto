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
    t = win.support
    assert t.cb_player.isChecked() and t.player.text() == "VOYOV"
    assert t.cb_servant.isChecked() and t.servant.text() == "摩根"
    assert not t.cb_ce.isChecked() and not t.cb_level.isChecked()


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
    tab.select_row(tab.rows[1])            # JetSet 的摩根：OCR 自動填入
    assert tab.player.text() == "JetSet" and tab.servant.text() == "摩根"
    assert (tab.level.value(), tab.np.value()) == (110, 5)
    tab.cb_player.setChecked(False)        # 不限玩家
    tab.cb_np.setChecked(True)
    spec = tab.current_spec()
    assert (spec.player, spec.servant, spec.min_np, spec.min_level) == ("", "摩根", 5, 0)
    tab.test_match()
    assert list(tab.match_result.values()) == [False, True]
    assert "從者 摩根" in tab.result_label.text()


def test_support_level_condition_rejects_lower(win):
    tab = win.support
    tab.set_shot(imread(ROOT / "screenshots" / "support_select_no_voyov.png"))
    tab.cb_player.setChecked(False)
    tab.cb_level.setChecked(True)
    tab.level.setValue(120)                # JetSet 的摩根只有 110
    tab.test_match()
    assert list(tab.match_result.values()) == [False, False]


def test_support_mlb_and_class_saved(win, tmp_path):
    win.support.cb_mlb.setChecked(True)
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


# ---------- 程式圖示 ----------
def test_app_icon_sizes_and_sources():
    """小尺寸用「頭 + 角」、大尺寸用整張圖。"""
    from PySide6.QtGui import QPixmap
    from ui.app import LARGE_ICON_SIZES, SMALL_ICON_SIZES, app_icon, make_app
    make_app([])
    ic = app_icon()
    sizes = {s.width() for s in ic.availableSizes()}
    assert set(SMALL_ICON_SIZES) | set(LARGE_ICON_SIZES) <= sizes
    small = QPixmap(str(ROOT / "assets" / "icon_small.png")).scaled(32, 32).toImage()
    large = QPixmap(str(ROOT / "assets" / "icon_large.png")).scaled(32, 32).toImage()
    got = ic.pixmap(32, 32).toImage()
    diff = lambda a, b: sum(abs(a.pixelColor(x, y).red() - b.pixelColor(x, y).red())  # noqa: E731
                            for x in range(0, 32, 4) for y in range(0, 32, 4))
    assert diff(got, small) < diff(got, large)


def test_ico_file_has_all_sizes():
    from PySide6.QtGui import QImageReader
    r = QImageReader(str(ROOT / "assets" / "app.ico"))
    widths = []
    for i in range(r.imageCount()):
        r.jumpToImage(i)
        widths.append(r.read().width())
    assert widths == [16, 20, 24, 32, 40, 48, 64, 128, 256]
