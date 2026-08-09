import importlib
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

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


def test_load_config_normalizes_bad_values(overlay_module):
    mod = overlay_module
    with open(mod.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "x": "bad",
            "scale": "huge",
            "size": [1, 999999],
            "tolerance": -5,
            "opacity": 7,
            "bg_color": ["x", 999, -1],
            "anchor": {"screen": "s", "hx": 9, "vy": 1},
            "hotkeys": {"show": " Ctrl+F1 ", "bad": "Ctrl+F2"},
            "hotkeys_enabled": "yes",
        }, f)

    cfg = mod.load_config()

    assert cfg["x"] == mod.DEFAULTS["x"]
    assert cfg["scale"] == mod.DEFAULTS["scale"]
    assert cfg["size"] == [mod.MIN_SIZE, mod.MAX_SIZE]
    assert cfg["tolerance"] == 0
    assert cfg["opacity"] == 1.0
    assert cfg["bg_color"] == [255, 255, 0]
    assert cfg["anchor"] is None
    assert cfg["hotkeys"]["show"] == "Ctrl+F1"
    assert cfg["hotkeys_enabled"] is True
    assert "설정값 일부" in "\n".join(mod.consume_config_notices())


def test_load_config_rejects_unsafe_standalone_hotkeys(overlay_module):
    mod = overlay_module
    with open(mod.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "hotkeys": {
                "toggle_visible": "Space",
                "show": "Enter",
                "hide": "F1",
                "open_image": "Ctrl+O",
                "flip": "Tab",
                "click_through": "Num1",
            },
        }, f)

    cfg = mod.load_config()

    assert cfg["hotkeys"]["toggle_visible"] == ""
    assert cfg["hotkeys"]["show"] == ""
    assert cfg["hotkeys"]["hide"] == ""
    assert cfg["hotkeys"]["flip"] == ""
    assert cfg["hotkeys"]["open_image"] == "Ctrl+O"
    assert cfg["hotkeys"]["click_through"] == "Num1"
    assert mod.hotkey_to_windows("Space") is None
    assert mod.hotkey_to_windows("F1") is None
    assert mod.hotkey_to_windows("Num1") == (mod.MOD_NOREPEAT, 0x61)
    assert "설정값 일부" in "\n".join(mod.consume_config_notices())


def test_load_config_parses_string_bool_values(overlay_module):
    mod = overlay_module
    with open(mod.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "topmost": "false",
            "click_through": "0",
            "remove_bg": "off",
            "capturable": "yes",
            "flip": "1",
            "hotkeys_enabled": "no",
            "despill": "not-a-bool",
        }, f)

    cfg = mod.load_config()

    assert cfg["topmost"] is False
    assert cfg["click_through"] is False
    assert cfg["remove_bg"] is False
    assert cfg["capturable"] is True
    assert cfg["flip"] is True
    assert cfg["hotkeys_enabled"] is False
    assert cfg["despill"] is mod.DEFAULTS["despill"]
    assert "설정값 일부" in "\n".join(mod.consume_config_notices())


def test_save_config_replaces_file_atomically(overlay_module):
    mod = overlay_module

    mod.save_config({"x": 1})
    mod.save_config({"x": 2})

    assert json.loads(open(mod.CONFIG_PATH, encoding="utf-8").read())["x"] == 2
    assert not os.path.exists(mod.CONFIG_PATH + ".tmp")


def test_startup_shortcut_path_uses_windows_startup_folder(overlay_module, tmp_path, monkeypatch):
    mod = overlay_module
    monkeypatch.setattr(mod.os, "name", "nt")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

    assert mod.startup_shortcut_path().endswith(
        os.path.join(
            "Roaming",
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
            "Startup",
            "DesktopOverlay.lnk",
        )
    )


def test_create_startup_shortcut_builds_current_exe_link(overlay_module, tmp_path, monkeypatch):
    mod = overlay_module
    scripts = []
    exe = tmp_path / "Desktop_Overlay_Start.exe"
    exe.write_text("exe", encoding="utf-8")
    monkeypatch.setattr(mod.os, "name", "nt")
    monkeypatch.setattr(mod.sys, "frozen", True, raising=False)
    monkeypatch.setattr(mod.sys, "executable", str(exe))
    monkeypatch.setattr(mod, "APP_DIR", str(tmp_path))
    monkeypatch.setattr(mod, "run_powershell", lambda script: scripts.append(script) or "")
    shortcut = tmp_path / "Startup" / "DesktopOverlay.lnk"

    assert mod.create_startup_shortcut(str(shortcut)) == str(shortcut)

    script = scripts[0]
    assert "CreateShortcut" in script
    assert str(shortcut) in script
    assert str(exe) in script
    assert "$shortcut.TargetPath = $targetPath" in script
    assert "$shortcut.Save()" in script


def test_source_startup_uses_pythonw_when_available(overlay_module, tmp_path, monkeypatch):
    mod = overlay_module
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.write_text("python", encoding="utf-8")
    pythonw.write_text("pythonw", encoding="utf-8")
    monkeypatch.setattr(mod.os, "name", "nt")
    monkeypatch.setattr(mod.sys, "executable", str(python))
    monkeypatch.setattr(mod.sys, "frozen", False, raising=False)

    target, args, _working_dir = mod.current_startup_target()

    assert target == str(pythonw)
    assert "desktop_overlay.py" in args


def test_remove_startup_shortcut_deletes_link(overlay_module, tmp_path):
    mod = overlay_module
    shortcut = tmp_path / "DesktopOverlay.lnk"
    shortcut.write_text("link", encoding="utf-8")

    mod.remove_startup_shortcut(str(shortcut))

    assert not shortcut.exists()


def test_network_path_is_not_probed_on_startup(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    network_path = r"\\offline-server\share\overlay.gif"
    loaded = []

    def fake_exists(path):
        if str(path).startswith("\\\\"):
            raise AssertionError("network path was probed on UI thread")
        return False

    monkeypatch.setattr(mod.os.path, "exists", fake_exists)
    monkeypatch.setattr(mod.Pet, "load_image", lambda self, path: loaded.append(path))
    cfg = dict(mod.DEFAULTS)
    cfg["path"] = network_path

    pet = mod.Pet(cfg)

    try:
        assert loaded == [network_path]
        assert pet.need_image is None
    finally:
        pet.close()


def test_unc_saved_path_is_restored_when_startup_arg_is_missing(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    saved_path = r"\\nas\share\overlay.gif"
    missing_arg = "C:/missing.gif"
    loaded = []

    def fake_exists(path):
        if str(path).startswith("\\\\"):
            raise AssertionError("network path was probed on UI thread")
        return False

    monkeypatch.setattr(mod.os.path, "exists", fake_exists)
    monkeypatch.setattr(mod.Pet, "load_image", lambda self, path: loaded.append(path))
    cfg = dict(mod.DEFAULTS)
    cfg["path"] = saved_path
    cfg["_startup_missing_path"] = missing_arg

    pet = mod.Pet(cfg)

    try:
        assert loaded == [saved_path]
        assert pet.startup_restored_saved_path is True
        assert pet.startup_missing_path == missing_arg
        assert pet.need_image is None
    finally:
        pet.close()


def test_path_exists_without_network_probe_returns_unknown_for_unc(overlay_module, monkeypatch):
    mod = overlay_module

    monkeypatch.setattr(
        mod.os.path,
        "exists",
        lambda path: (_ for _ in ()).throw(AssertionError("network path was probed")))

    assert mod.path_exists_without_network_probe(r"\\offline-server\share\x.png") is None


def test_startup_argument_uses_non_blocking_network_path_policy(overlay_module, monkeypatch):
    mod = overlay_module
    network_path = r"\\offline-server\share\arg.gif"
    missing_path = "C:/missing.gif"

    def fake_exists(path):
        if str(path).startswith("\\\\"):
            raise AssertionError("network path was probed on UI thread")
        return False

    monkeypatch.setattr(mod.os.path, "exists", fake_exists)

    cfg = dict(mod.DEFAULTS)
    mod.apply_startup_path_argument(cfg, network_path)
    assert cfg["path"] == network_path
    assert "_startup_missing_path" not in cfg

    cfg = dict(mod.DEFAULTS)
    mod.apply_startup_path_argument(cfg, missing_path)
    assert cfg["_startup_missing_path"] == missing_path


def test_startup_state_only_checks_shortcut_existence(overlay_module, tmp_path, monkeypatch):
    mod = overlay_module
    startup = tmp_path / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True)
    (startup / "DesktopOverlay.lnk").write_text("old", encoding="utf-8")
    monkeypatch.setattr(mod.os, "name", "nt")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))

    state = mod.startup_state()

    assert state["supported"]
    assert state["exists"]
    assert state["matches"]


def test_startup_worker_reports_create_result(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    monkeypatch.setattr(mod, "create_startup_shortcut", lambda: r"C:\Startup\DesktopOverlay.lnk")
    worker = mod.StartupWorker(3, True)
    results = []
    failures = []
    worker.finished.connect(lambda job_id, enabled, path: results.append((job_id, enabled, path)))
    worker.failed.connect(lambda job_id, enabled, message: failures.append((job_id, enabled, message)))

    worker.run()

    assert results == [(3, True, r"C:\Startup\DesktopOverlay.lnk")]
    assert failures == []


def test_shutdown_uses_short_startup_worker_wait(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    monkeypatch.setattr(mod, "save_config", lambda cfg: None)

    class FakeThread:
        def __init__(self):
            self.quit_called = False
            self.wait_timeouts = []

        def quit(self):
            self.quit_called = True

        def wait(self, timeout_ms):
            self.wait_timeouts.append(timeout_ms)
            return True

    cfg = dict(mod.DEFAULTS)
    pet = mod.Pet(cfg)
    startup_thread = FakeThread()
    update_thread = FakeThread()

    try:
        pet._startup_workers = [(object(), startup_thread)]
        pet._update_workers = [(object(), update_thread)]

        pet.shutdown()

        assert startup_thread.quit_called
        assert startup_thread.wait_timeouts == [mod.STARTUP_SHUTDOWN_WAIT_MS]
        assert update_thread.wait_timeouts == [
            (mod.UPDATE_CHECK_TIMEOUT_SEC + 2) * 1000
        ]
    finally:
        pet.close()


def test_shutdown_abandons_still_running_image_thread(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    monkeypatch.setattr(mod, "save_config", lambda cfg: None)
    mod.ABANDONED_THREADS[:] = []

    class FakeThread:
        def __init__(self):
            self.parent_cleared = False
            self.wait_timeouts = []

        def quit(self):
            pass

        def wait(self, timeout_ms):
            self.wait_timeouts.append(timeout_ms)
            return False

        def setParent(self, parent):
            self.parent_cleared = parent is None

    cfg = dict(mod.DEFAULTS)
    pet = mod.Pet(cfg)
    thread = FakeThread()

    try:
        pet._workers = [(object(), thread)]
        pet.shutdown()

        assert thread.wait_timeouts == [mod.IMAGE_WORKER_SHUTDOWN_WAIT_MS]
        assert thread.parent_cleared
        assert thread in mod.ABANDONED_THREADS
    finally:
        pet.close()
        mod.ABANDONED_THREADS[:] = []


def test_startup_disable_removes_shortcut_without_worker(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    removed = []
    monkeypatch.setattr(mod, "save_config", lambda cfg: None)
    monkeypatch.setattr(mod, "remove_startup_shortcut", lambda: removed.append(True) or "link")

    pet = mod.Pet(dict(mod.DEFAULTS))

    try:
        pet.set_startup_enabled(False)

        assert removed == [True]
        assert pet._startup_workers == []
        assert not pet.startup_changing
    finally:
        pet.close()


def test_startup_reentry_does_not_start_second_worker(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    notices = []
    monkeypatch.setattr(mod, "save_config", lambda cfg: None)

    class FakeTray:
        def showMessage(self, title, body, *_args):
            notices.append((title, body))

    pet = mod.Pet(dict(mod.DEFAULTS))

    try:
        pet.tray = FakeTray()
        pet.startup_changing = True
        pet.set_startup_enabled(True)

        assert pet._startup_workers == []
        assert notices
    finally:
        pet.close()


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


def test_outside_region_can_be_cancelled(overlay_module):
    mod = overlay_module
    passable = np.ones((7, 7), dtype=bool)

    with pytest.raises(mod.WorkerCancelled):
        mod.outside_region(
            passable,
            cancel_check=lambda: (_ for _ in ()).throw(mod.WorkerCancelled()))


def test_outside_region_has_iteration_limit(overlay_module):
    mod = overlay_module
    passable = np.ones((7, 7), dtype=bool)

    with pytest.raises(RuntimeError, match="너무 오래"):
        mod.outside_region(passable, max_iterations=0)


def test_outside_region_default_limit_handles_snaking_mask(overlay_module):
    mod = overlay_module
    passable = np.zeros((24, 24), dtype=bool)
    for row in range(passable.shape[0]):
        if row % 2 == 0:
            passable[row, :] = True
        else:
            passable[row, -1] = True

    outside = mod.outside_region(passable)

    assert outside[0, 0]
    assert outside[-1, -1]
    assert np.array_equal(outside, passable)


def test_transparent_border_is_preserved(overlay_module):
    mod = overlay_module
    rgba = np.zeros((5, 5, 4), dtype=np.uint8)
    rgba[1:4, 1:4, :3] = 255
    rgba[1:4, 1:4, 3] = 255

    result = mod.key_out(rgba, np.array([255, 255, 255], dtype=np.float32), 40, 30, True)

    assert np.array_equal(result, rgba)


def test_release_version_compare_handles_v_tags(overlay_module):
    mod = overlay_module

    assert mod.parse_version("v0.2.1") == (0, 2, 1, "")
    assert mod.parse_version("0.10") == (0, 10, 0, "")
    assert mod.parse_version("v1.0.0-rc1") == (1, 0, 0, "rc1")
    assert mod.is_newer_version("v0.2.2", "0.2.1")
    assert mod.is_newer_version("v0.3.0", "0.2.9")
    assert mod.compare_versions("v1.0.0-rc1", "v1.0.0") == -1
    assert not mod.is_newer_version("1.0.0-beta", "0.3.1")
    assert not mod.is_newer_version("v1.0.0-rc1", "0.3.1")
    assert not mod.is_newer_version("0.4.0-alpha", "0.3.1")
    assert mod.is_newer_version("1.0.0", "0.3.1")
    assert mod.parse_version("1.2.3a") is None
    assert mod.parse_version("v1.0.0.final") is None
    assert not mod.is_newer_version("v0.2.1", "0.2.1")
    assert not mod.is_newer_version("v0.2.0", "0.2.1")
    assert not mod.is_newer_version("not-a-version", "0.2.1")


def test_fetch_latest_release_rejects_prerelease_tag(overlay_module, monkeypatch):
    mod = overlay_module

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({"tag_name": "v1.0.0-rc1"}).encode("utf-8")

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    with pytest.raises(ValueError, match="프리릴리스"):
        mod.fetch_latest_release()


def test_fetch_latest_release_rejects_unparseable_tag(overlay_module, monkeypatch):
    mod = overlay_module

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({"tag_name": "v1.0.0.final"}).encode("utf-8")

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    with pytest.raises(ValueError, match="태그 형식"):
        mod.fetch_latest_release()


def test_fetch_latest_release_sanitizes_untrusted_release_url(overlay_module, monkeypatch):
    mod = overlay_module

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, *_args):
            return json.dumps({
                "tag_name": "v9.9.9",
                "html_url": "file:///C:/Windows/System32/calc.exe",
            }).encode("utf-8")

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    result = mod.fetch_latest_release()

    assert result["url"] == mod.RELEASES_LATEST_URL
    assert result["newer"]


def test_safe_release_url_allows_project_release_urls(overlay_module):
    mod = overlay_module
    url = "https://github.com/TailFox-Forge/DesktopOverlay/releases/tag/v0.3.5"

    assert mod.safe_release_url(url) == url


def test_fetch_latest_release_limits_response_size(overlay_module, monkeypatch):
    mod = overlay_module

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            return b"x" * int(size)

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    with pytest.raises(ValueError, match="응답이 너무 큽니다"):
        mod.fetch_latest_release()


def test_open_repository_page_uses_project_url(overlay_module, monkeypatch):
    mod = overlay_module
    opened = []
    monkeypatch.setattr(mod.QtGui.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))

    mod.open_repository_page()

    assert opened == [mod.REPOSITORY_URL]


def test_update_worker_reports_unexpected_errors(overlay_module):
    mod = overlay_module
    worker = mod.UpdateCheckWorker(7, False)
    failures = []
    worker.failed.connect(lambda job_id, message, silent: failures.append((job_id, message, silent)))

    def fail():
        raise RuntimeError("boom")

    mod.fetch_latest_release = fail
    worker.run()

    assert failures == [(7, "boom", False)]


def test_read_frames_limits_gif_frames_and_preserves_duration(overlay_module, tmp_path, monkeypatch):
    mod = overlay_module
    monkeypatch.setattr(mod, "MAX_GIF_FRAMES", 3)
    monkeypatch.setattr(mod, "MAX_GIF_TOTAL_PIXELS", 10_000)
    durations = [40, 50, 60, 70, 80, 90]
    frames = [
        mod.Image.new("RGBA", (8, 8), (i * 35, 0, 0, 255))
        for i in range(len(durations))
    ]
    path = tmp_path / "sample.gif"
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
    )

    metadata = {}
    loaded = mod.read_frames(str(path), metadata)

    assert metadata["source_frame_count"] == len(durations)
    assert metadata["stored_frame_count"] == 3
    assert metadata["dropped_frames"] == 3
    assert sum(delay for _frame, delay in loaded) == sum(durations)
    assert all(frame.shape == (8, 8, 4) for frame, _delay in loaded)


def test_read_frames_limits_gif_after_downscale(overlay_module, tmp_path, monkeypatch):
    mod = overlay_module
    monkeypatch.setattr(mod, "MAX_FRAME_PIXELS", 25)
    monkeypatch.setattr(mod, "MAX_GIF_FRAMES", 20)
    monkeypatch.setattr(mod, "MAX_GIF_TOTAL_PIXELS", 100)
    frames = [mod.Image.new("RGBA", (20, 20), (i * 20, 0, 0, 255)) for i in range(10)]
    path = tmp_path / "large.gif"
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=[30] * 10, loop=0)

    metadata = {}
    loaded = mod.read_frames(str(path), metadata)

    assert metadata["stored_pixels"] <= mod.MAX_FRAME_PIXELS
    assert metadata["frame_limit"] == 4
    assert len(loaded) == 4
    assert all(frame.shape == (5, 5, 4) for frame, _delay in loaded)


def test_read_frames_rejects_source_pixels_before_decode(overlay_module, tmp_path, monkeypatch):
    mod = overlay_module
    monkeypatch.setattr(mod, "MAX_SOURCE_PIXELS", 100)
    path = tmp_path / "too-large.png"
    mod.Image.new("RGBA", (20, 20), (255, 0, 0, 255)).save(path)

    with pytest.raises(ValueError, match="허용 한도"):
        mod.read_frames(str(path))


def test_source_pixel_limit_matches_pillow_and_has_boundary(overlay_module):
    mod = overlay_module

    assert mod.Image.MAX_IMAGE_PIXELS == mod.MAX_SOURCE_PIXELS
    assert mod.validate_source_pixels(mod.MAX_SOURCE_PIXELS, 1) == mod.MAX_SOURCE_PIXELS
    with pytest.raises(ValueError, match="이미지 크기를 줄여서"):
        mod.validate_source_pixels(mod.MAX_SOURCE_PIXELS + 1, 1)


def test_read_frames_closes_image_file(overlay_module, tmp_path, monkeypatch):
    mod = overlay_module
    path = tmp_path / "sample.png"
    mod.Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(path)
    real_open = mod.Image.open
    opened = []

    class ImageProxy:
        def __init__(self, image):
            self.image = image
            self.closed = False

        def __enter__(self):
            return self.image

        def __exit__(self, *_args):
            self.closed = True
            self.image.close()
            return False

        def __getattr__(self, name):
            return getattr(self.image, name)

    def open_proxy(*args, **kwargs):
        proxy = ImageProxy(real_open(*args, **kwargs))
        opened.append(proxy)
        return proxy

    monkeypatch.setattr(mod.Image, "open", open_proxy)

    frames = mod.read_frames(str(path))

    assert frames
    assert opened[0].closed


def test_render_frame_arrays_can_be_cancelled(overlay_module):
    mod = overlay_module
    frames = [(np.zeros((3, 3, 4), dtype=np.uint8), 100)]

    with pytest.raises(mod.WorkerCancelled):
        mod.render_frame_arrays(frames, mod.normalize_config({}), cancel_check=lambda: (_ for _ in ()).throw(mod.WorkerCancelled()))


def test_assign_hotkey_removes_duplicate_and_visibility_conflicts(overlay_module):
    mod = overlay_module
    hotkeys = mod.normalize_hotkeys({})
    hotkeys, messages = mod.assign_hotkey(hotkeys, "show", "Ctrl+Alt+F1")
    assert hotkeys["show"] == "Ctrl+Alt+F1"

    hotkeys, messages = mod.assign_hotkey(hotkeys, "hide", "Ctrl+Alt+F1")
    assert hotkeys["show"] == ""
    assert hotkeys["hide"] == "Ctrl+Alt+F1"
    assert any("이미 등록된" in message for message in messages)

    hotkeys, messages = mod.assign_hotkey(hotkeys, "toggle_visible", "Ctrl+Alt+F2")
    assert hotkeys["toggle_visible"] == "Ctrl+Alt+F2"
    assert hotkeys["hide"] == ""
    assert any("개별 단축키" in message for message in messages)


def test_shortcut_rejects_text_key_without_modifier(overlay_module):
    mod = overlay_module
    event = QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress,
        QtCore.Qt.Key_A,
        QtCore.Qt.NoModifier,
    )

    shortcut, error = mod.shortcut_from_key_event(event)

    assert shortcut is None
    assert "수식어 없는 단독키" in error


def test_shortcut_rejects_function_key_without_modifier(overlay_module):
    mod = overlay_module
    event = QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress,
        QtCore.Qt.Key_F1,
        QtCore.Qt.NoModifier,
    )

    shortcut, error = mod.shortcut_from_key_event(event)

    assert shortcut is None
    assert "수식어 없는 단독키" in error


def test_shortcut_allows_numpad_digit_without_modifier(overlay_module):
    mod = overlay_module
    event = QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress,
        QtCore.Qt.Key_1,
        QtCore.Qt.KeypadModifier,
    )

    shortcut, error = mod.shortcut_from_key_event(event)

    assert shortcut == "Num1"
    assert error is None
    assert mod.hotkey_to_windows("Num1") == (mod.MOD_NOREPEAT, 0x61)


@pytest.mark.parametrize("shortcut", [
    "Delete",
    "Backspace",
    "Tab",
    "Esc",
    "Ctrl+Alt+Delete",
    "Alt+Tab",
    "Alt+Esc",
    "Alt+Shift+Tab",
    "Ctrl+Alt+Tab",
    "Ctrl+Esc",
    "Ctrl+Shift+Esc",
    "Win+D",
    "Win+L",
    "Win+Tab",
])
def test_shortcut_rejects_single_reserved_keys_and_windows_reserved_combos(overlay_module, shortcut):
    mod = overlay_module

    assert mod.normalize_shortcut_string(shortcut) == ""
    assert mod.hotkey_to_windows(shortcut) is None


@pytest.mark.parametrize("shortcut", [
    "Ctrl+Shift+Delete",
    "Ctrl+Delete",
    "Shift+Delete",
    "Ctrl+Backspace",
    "Alt+Backspace",
    "Ctrl+Tab",
    "Ctrl+Shift+Tab",
])
def test_shortcut_allows_modified_editing_and_tab_keys(overlay_module, shortcut):
    mod = overlay_module

    assert mod.normalize_shortcut_string(shortcut) == shortcut
    assert mod.hotkey_to_windows(shortcut) is not None


def test_hotkey_capture_delete_only_clears_without_modifiers(qapp, overlay_module):
    mod = overlay_module
    button = mod.HotkeyCaptureButton("show")
    captured = []
    button.captured.connect(lambda command, shortcut, error: captured.append((command, shortcut, error)))

    try:
        button.start_capture()
        button.keyPressEvent(QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_Delete,
            QtCore.Qt.NoModifier,
        ))
        assert captured == [("show", "", "")]

        captured.clear()
        button.start_capture()
        button.keyPressEvent(QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_Delete,
            QtCore.Qt.ControlModifier,
        ))
        assert captured == [("show", "Ctrl+Delete", "")]
    finally:
        button.deleteLater()


@pytest.mark.parametrize(("key", "modifiers", "expected"), [
    (QtCore.Qt.Key_Tab, QtCore.Qt.ControlModifier, "Ctrl+Tab"),
    (QtCore.Qt.Key_Tab, QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier, "Ctrl+Shift+Tab"),
    (QtCore.Qt.Key_Tab, QtCore.Qt.AltModifier, ""),
    (QtCore.Qt.Key_Tab, QtCore.Qt.MetaModifier, ""),
    (QtCore.Qt.Key_Escape, QtCore.Qt.ControlModifier, ""),
    (QtCore.Qt.Key_Escape, QtCore.Qt.AltModifier, ""),
    (QtCore.Qt.Key_Escape, QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier, ""),
])
def test_hotkey_capture_uses_same_reserved_combo_rules(qapp, overlay_module, key, modifiers, expected):
    mod = overlay_module
    button = mod.HotkeyCaptureButton("show")
    captured = []
    button.captured.connect(lambda command, shortcut, error: captured.append((command, shortcut, error)))

    try:
        button.start_capture()
        button.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, modifiers))

        assert captured
        assert captured[0][1] == expected
        if expected:
            assert captured[0][2] == ""
        else:
            assert "예약 단축키" in captured[0][2] or "사용할 수 없습니다" in captured[0][2]
    finally:
        button.deleteLater()


def test_hotkey_capture_waits_for_modifier_combo(qapp, overlay_module):
    mod = overlay_module
    button = mod.HotkeyCaptureButton("show")
    captured = []
    button.captured.connect(lambda command, shortcut, error: captured.append((command, shortcut, error)))

    try:
        button.start_capture()
        button.keyPressEvent(QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_Control,
            QtCore.Qt.ControlModifier,
        ))
        assert captured == []
        assert button.capturing

        button.keyPressEvent(QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_F1,
            QtCore.Qt.ControlModifier,
        ))
        assert captured == [("show", "Ctrl+F1", "")]
        assert not button.capturing
    finally:
        button.deleteLater()


@pytest.mark.parametrize("size", [(320, 293), (640, 480), (1280, 720)])
def test_first_scale_keeps_saved_custom_position(qapp, overlay_module, size):
    mod = overlay_module
    cfg = dict(mod.DEFAULTS)
    cfg.update({"path": "", "x": 500, "y": 300, "anchor": None})
    pet = mod.Pet(cfg)

    try:
        assert not pet._sized_once
        pet.base_size = size
        pet.cfg["scale"] = 1.0
        pet.cfg["size"] = None
        pet.apply_scale()

        assert (pet.x(), pet.y()) == (500, 300)
        assert (pet.width(), pet.height()) == size
        assert pet._sized_once
    finally:
        pet.close()


def test_first_scale_keeps_anchor_reposition_behavior(qapp, overlay_module):
    mod = overlay_module
    screen = qapp.primaryScreen()
    cfg = dict(mod.DEFAULTS)
    cfg.update({
        "path": "",
        "x": 500,
        "y": 300,
        "anchor": {"screen": screen.name(), "hx": 2, "vy": 2},
    })
    pet = mod.Pet(cfg)

    try:
        pet.base_size = (320, 293)
        pet.cfg["scale"] = 1.0
        pet.cfg["size"] = None
        pet.apply_scale()

        geo = screen.availableGeometry()
        expected_x = geo.right() - pet.width() + 1 - int(pet.cfg.get("snap_margin", 0))
        expected_y = geo.bottom() - pet.height() + 1 - int(pet.cfg.get("snap_margin", 0))
        assert (pet.x(), pet.y()) == (expected_x, expected_y)
    finally:
        pet.close()


def test_scale_after_first_size_preserves_center(qapp, overlay_module):
    mod = overlay_module
    cfg = dict(mod.DEFAULTS)
    cfg.update({"path": "", "x": 500, "y": 300, "anchor": None})
    pet = mod.Pet(cfg)

    try:
        pet.base_size = (320, 293)
        pet.cfg["scale"] = 1.0
        pet.apply_scale()
        center_before = (pet.x() + pet.width() / 2.0, pet.y() + pet.height() / 2.0)

        pet.set_scale(2.0)

        center_after = (pet.x() + pet.width() / 2.0, pet.y() + pet.height() / 2.0)
        assert abs(center_after[0] - center_before[0]) <= 0.5
        assert abs(center_after[1] - center_before[1]) <= 0.5
    finally:
        pet.close()


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


def test_persist_debounces_until_flush(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    writes = []
    monkeypatch.setattr(mod, "save_config", lambda cfg: writes.append(dict(cfg)))
    cfg = dict(mod.DEFAULTS)
    pet = mod.Pet(cfg)

    try:
        writes.clear()
        pet.persist()
        pet.persist()
        assert writes == []

        pet.flush_persist()
        assert len(writes) == 1
    finally:
        pet.close()


def test_pick_file_keeps_previous_path_until_new_image_succeeds(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    old_path = "C:/ok.png"
    new_path = "C:/broken.png"
    loaded = []
    writes = []
    monkeypatch.setattr(mod, "save_config", lambda cfg: writes.append(dict(cfg)))
    monkeypatch.setattr(
        mod.QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (new_path, ""),
    )
    monkeypatch.setattr(mod.Pet, "load_image", lambda self, path: loaded.append(path))
    cfg = dict(mod.DEFAULTS)
    cfg["path"] = old_path

    pet = mod.Pet(cfg)

    try:
        writes.clear()
        pet.pick_file()

        assert loaded[-1] == new_path
        assert pet.cfg["path"] == old_path
        assert writes == []
    finally:
        pet.close()


def test_first_run_notice_shows_dialog_once_and_can_open_picker(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    writes = []
    opened = []
    monkeypatch.setattr(mod, "save_config", lambda cfg: writes.append(dict(cfg)))
    monkeypatch.setattr(mod.Pet, "show_first_run_notice_dialog", lambda self: True)
    monkeypatch.setattr(mod.Pet, "pick_file", lambda self: opened.append(True))
    cfg = dict(mod.DEFAULTS)
    cfg["path"] = ""
    cfg["first_run_notice_shown"] = False

    pet = mod.Pet(cfg)

    try:
        writes.clear()
        pet.prompt_first_run_notice()
        pet.prompt_first_run_notice()

        assert opened == [True]
        assert pet.cfg["first_run_notice_shown"] is True
        assert writes[-1]["first_run_notice_shown"] is True
    finally:
        pet.close()


def test_first_run_notice_is_skipped_after_it_was_shown(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    opened = []
    monkeypatch.setattr(mod, "save_config", lambda cfg: None)
    monkeypatch.setattr(mod.Pet, "show_first_run_notice_dialog", lambda self: True)
    monkeypatch.setattr(mod.Pet, "pick_file", lambda self: opened.append(True))
    cfg = dict(mod.DEFAULTS)
    cfg["path"] = ""
    cfg["first_run_notice_shown"] = True

    pet = mod.Pet(cfg)

    try:
        pet.prompt_first_run_notice()

        assert opened == []
    finally:
        pet.close()


def test_reauto_bg_returns_to_auto_mode(qapp, overlay_module, monkeypatch):
    mod = overlay_module
    monkeypatch.setattr(mod, "save_config", lambda cfg: None)
    rebuilt = []
    monkeypatch.setattr(mod.Pet, "rebuild", lambda self: rebuilt.append(True))
    cfg = dict(mod.DEFAULTS)
    cfg["auto_bg"] = False
    cfg["bg_color"] = [1, 2, 3]
    pet = mod.Pet(cfg)
    frame = np.zeros((4, 4, 4), dtype=np.uint8)
    frame[:, :, :3] = [20, 30, 40]
    frame[:, :, 3] = 255

    try:
        pet.frames = [(frame, 100)]
        pet.reauto_bg()

        assert pet.cfg["auto_bg"] is True
        assert pet.cfg["bg_color"] == [20, 30, 40]
        assert rebuilt == [True]
    finally:
        pet.close()
