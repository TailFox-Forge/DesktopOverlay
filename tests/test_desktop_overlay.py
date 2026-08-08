import importlib
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

import desktop_overlay as appmod


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def overlay_module(tmp_path, monkeypatch):
    mod = importlib.reload(appmod)
    portable_dir = tmp_path / "portable"
    local_dir = tmp_path / "local"
    portable_dir.mkdir()
    monkeypatch.setattr(mod, "APP_DIR", str(portable_dir))
    monkeypatch.setattr(mod, "PORTABLE_CONFIG_PATH", str(portable_dir / "config.json"))
    monkeypatch.setattr(mod, "LOCAL_CONFIG_PATH", str(local_dir / "DesktopOverlay" / "config.json"))
    monkeypatch.setattr(mod, "CONFIG_PATH", mod.PORTABLE_CONFIG_PATH)
    mod.CONFIG_NOTICES[:] = []
    return mod


def test_normalize_anchor_rejects_broken_values(overlay_module):
    mod = overlay_module
    bad_values = [
        "bad",
        [],
        {"screen": "s", "vy": 1},
        {"screen": "s", "hx": 9, "vy": 1},
        {"screen": "s", "hx": 1, "vy": "x"},
        {"screen": 7, "hx": 1, "vy": 1},
    ]
    assert all(mod.normalize_anchor(v) is None for v in bad_values)
    assert mod.normalize_anchor({"screen": "s", "hx": "1", "vy": 2}) == {
        "screen": "s",
        "hx": 1,
        "vy": 2,
    }


def test_config_falls_back_to_local_path_when_portable_write_fails(overlay_module, tmp_path):
    mod = overlay_module
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    mod.CONFIG_PATH = str(blocked / "config.json")

    mod.save_config({"x": 1})

    assert mod.CONFIG_PATH == mod.LOCAL_CONFIG_PATH
    assert json.loads((tmp_path / "local" / "DesktopOverlay" / "config.json").read_text())["x"] == 1
    assert "사용자 설정 폴더로 전환" in "\n".join(mod.consume_config_notices())


def test_outside_region_keeps_enclosed_area_outside_false(overlay_module):
    mod = overlay_module
    passable = np.ones((7, 7), dtype=bool)
    passable[2:5, 2] = False
    passable[2:5, 4] = False
    passable[2, 2:5] = False
    passable[4, 2:5] = False

    outside = mod.outside_region(passable)

    assert outside[0, 0]
    assert not outside[3, 3]


def test_transparent_border_is_preserved(overlay_module):
    mod = overlay_module
    rgba = np.zeros((5, 5, 4), dtype=np.uint8)
    rgba[1:4, 1:4, :3] = 255
    rgba[1:4, 1:4, 3] = 255

    result = mod.key_out(rgba, np.array([255, 255, 255], dtype=np.float32), 40, 30, True)

    assert np.array_equal(result, rgba)


def test_anchor_margin_and_click_behavior(qapp, overlay_module):
    mod = overlay_module
    cfg = dict(mod.DEFAULTS)
    cfg["click_through"] = False
    pet = mod.Pet(cfg)
    pet.resize(100, 100)
    screen = qapp.primaryScreen()

    try:
        pet.snap_to(screen, 2, 2)
        pos_before = pet.pos()
        pet.set_margin(40)
        assert pet.cfg["anchor"] is not None
        assert pet.pos() != pos_before

        anchor = dict(pet.cfg["anchor"])
        local = QtCore.QPointF(5, 5)
        global_pos = QtCore.QPointF(pet.mapToGlobal(QtCore.QPoint(5, 5)))
        pet.mousePressEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress, local, global_pos,
            QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier))
        pet.mouseReleaseEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease, local, global_pos,
            QtCore.Qt.LeftButton, QtCore.Qt.NoButton, QtCore.Qt.NoModifier))
        assert pet.cfg["anchor"] == anchor

        pet.mousePressEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonPress, local, global_pos,
            QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier))
        moved = QtCore.QPointF(
            global_pos.x() + QtWidgets.QApplication.startDragDistance() + 5,
            global_pos.y() + QtWidgets.QApplication.startDragDistance() + 5,
        )
        pet.mouseMoveEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove, local, moved,
            QtCore.Qt.NoButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier))
        pet.mouseReleaseEvent(QtGui.QMouseEvent(
            QtCore.QEvent.MouseButtonRelease, local, moved,
            QtCore.Qt.LeftButton, QtCore.Qt.NoButton, QtCore.Qt.NoModifier))
        assert pet.cfg["anchor"] is None
    finally:
        pet.close()
