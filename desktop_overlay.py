# -*- coding: utf-8 -*-
"""
DesktopOverlay - 어떤 이미지든 바탕화면 원하는 위치/크기에 배경 없이 띄운다.

GIF/PNG/JPG/WEBP/BMP 를 프레임 없는 투명 창으로 항상 위에 표시한다.
배경색은 모서리에서 자동 추출하고, 색이 아니라 피사체의 외곽선을 경계로
그 바깥쪽만 지우므로 흰 배경 + 흰 캐릭터처럼 까다로운 경우도 뚫리지 않는다.

조작:
  좌클릭 드래그 : 위치 이동
  마우스 휠     : 크기 조절
  우클릭 / 트레이 아이콘 : 전체 메뉴
"""
import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import numpy as np
from PIL import Image, ImageSequence
from PyQt5 import QtCore, QtGui, QtWidgets

APP_NAME = "DesktopOverlay"
APP_VERSION = "0.3.4"
RELEASES_LATEST_API = "https://api.github.com/repos/TailFox-Forge/DesktopOverlay/releases/latest"
RELEASES_LATEST_URL = "https://github.com/TailFox-Forge/DesktopOverlay/releases/latest"
UPDATE_CHECK_TIMEOUT_SEC = 8
RESAMPLE_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")

# PyInstaller onefile 로 묶으면 __file__ 은 임시 압축 해제 폴더를 가리킨다.
# 설정은 exe 가 놓인 폴더에 저장해야 다음 실행 때 남아 있다.
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
PORTABLE_CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOCAL_CONFIG_ROOT = (os.environ.get("LOCALAPPDATA")
                     or os.path.join(os.path.expanduser("~"), ".config"))
LOCAL_CONFIG_PATH = os.path.join(LOCAL_CONFIG_ROOT, APP_NAME, "config.json")
CONFIG_PATH = PORTABLE_CONFIG_PATH
CONFIG_NOTICES = []
IMAGE_FILTER = "이미지 (*.gif *.png *.jpg *.jpeg *.webp *.bmp);;모든 파일 (*.*)"
STARTUP_SHORTCUT_NAME = "%s.lnk" % APP_NAME
MIN_SIZE = 48      # 이보다 작아지면 우클릭 메뉴조차 열기 어려워진다
MAX_SIZE = 4000
MAX_FRAME_PIXELS = 4_000_000
MAX_GIF_FRAMES = 180
MAX_GIF_TOTAL_PIXELS = 100_000_000
PROCESSING_TOOLTIP = "%s - 이미지 처리 중..." % APP_NAME

DEFAULTS = {
    "path": "",
    "x": 100,
    "y": 100,
    "scale": 1.0,
    "size": None,        # [너비, 높이] 직접 입력값. None 이면 scale 사용
    "tolerance": 40,     # 배경으로 볼 색 차이 허용치 (0~200)
    "softness": 30,      # 가장자리 부드럽게 (0~100)
    "remove_bg": True,   # 끄면 원본 그대로 (배경 제거 안 함)
    "despill": True,     # 가장자리에 남는 배경색 기운 제거
    "edge_only": True,   # 캐릭터 외곽선 바깥만 제거 (내부 흰색 보호)
    "edge_thresh": 14,   # 외곽선으로 인정할 색 변화량 (낮을수록 선을 잘 지킴)
    "holes": True,       # 캐릭터에 둘러싸인 배경색 덩어리도 제거
    "auto_bg": True,     # 모서리에서 배경색 자동 추출
    "bg_color": [255, 255, 255],
    "opacity": 1.0,          # 창 전체 불투명도 0.1~1.0 (배경 제거와는 별개)
    "capturable": False,     # True 면 OBS/PRISM 윈도우 캡처 목록에 표시된다
    "anchor": None,          # 위치 바로가기로 옮겼을 때 {"screen","hx","vy"}. 직접 끌면 None
    "snap_margin": 0,        # 구석으로 보낼 때 띄울 여백(px)
    "chroma_bg": None,       # [r,g,b] 이면 창을 그 색으로 채운다 (윈도우 캡처 + 컬러키용)
    "click_through": True,   # 기본: 마우스 통과 (게임 조작 방해 없음)
    "flip": False,
    "topmost": True,         # 기본: 항상 위
    "hotkeys": {},           # 기본은 전부 미등록. 사용자가 설정창에서 직접 넣는다
    "hotkeys_enabled": True, # 비활성화 단축키를 누르면 False. 트레이 메뉴로만 다시 켠다
    "hotkey_screen": "",     # 위치 단축키가 움직일 대상 모니터
}

SIZE_PRESETS = (25, 50, 75, 100, 150, 200, 300)
SNAP_SPOTS = (
    ("좌측 상단", 0, 0, "tl"),
    ("상단 중앙", 1, 0, "tc"),
    ("우측 상단", 2, 0, "tr"),
    ("좌측 중앙", 0, 1, "ml"),
    ("정중앙", 1, 1, "mc"),
    ("우측 중앙", 2, 1, "mr"),
    ("좌측 하단", 0, 2, "bl"),
    ("하단 중앙", 1, 2, "bc"),
    ("우측 하단", 2, 2, "br"),
)
HOTKEY_ACTIONS = [
    ("toggle_visible", "보이기/숨기기 토글"),
    ("show", "보이기"),
    ("hide", "숨기기"),
    ("open_image", "이미지 열기"),
    ("flip", "좌우 반전"),
    ("topmost", "항상 위"),
    ("click_through", "클릭 통과"),
    ("disable_hotkeys", "단축키 전체 비활성화"),
]
HOTKEY_ACTIONS += [("scale_%d" % v, "크기 %d%%" % v) for v in SIZE_PRESETS]
HOTKEY_ACTIONS += [("scale_cycle", "크기 순차 변경")]
HOTKEY_ACTIONS += [("snap_%s" % code, "위치 %s" % label) for label, _hx, _vy, code in SNAP_SPOTS]
HOTKEY_LABELS = dict(HOTKEY_ACTIONS)
HOTKEY_DEFAULTS = {key: "" for key, _label in HOTKEY_ACTIONS}
HOTKEY_SIZE_COMMANDS = {"scale_%d" % v: v for v in SIZE_PRESETS}
HOTKEY_SNAP_COMMANDS = {"snap_%s" % code: (label, hx, vy) for label, hx, vy, code in SNAP_SPOTS}
KEY_NAME_MAP = {
    QtCore.Qt.Key_Escape: "Esc",
    QtCore.Qt.Key_Tab: "Tab",
    QtCore.Qt.Key_Backtab: "Tab",
    QtCore.Qt.Key_Backspace: "Backspace",
    QtCore.Qt.Key_Return: "Enter",
    QtCore.Qt.Key_Enter: "Enter",
    QtCore.Qt.Key_Insert: "Insert",
    QtCore.Qt.Key_Delete: "Delete",
    QtCore.Qt.Key_Pause: "Pause",
    QtCore.Qt.Key_Print: "PrintScreen",
    QtCore.Qt.Key_Home: "Home",
    QtCore.Qt.Key_End: "End",
    QtCore.Qt.Key_Left: "Left",
    QtCore.Qt.Key_Up: "Up",
    QtCore.Qt.Key_Right: "Right",
    QtCore.Qt.Key_Down: "Down",
    QtCore.Qt.Key_PageUp: "PageUp",
    QtCore.Qt.Key_PageDown: "PageDown",
    QtCore.Qt.Key_Space: "Space",
}
VK_SPECIAL_KEYS = {
    "Esc": 0x1B,
    "Tab": 0x09,
    "Backspace": 0x08,
    "Enter": 0x0D,
    "Insert": 0x2D,
    "Delete": 0x2E,
    "Pause": 0x13,
    "PrintScreen": 0x2C,
    "Home": 0x24,
    "End": 0x23,
    "Left": 0x25,
    "Up": 0x26,
    "Right": 0x27,
    "Down": 0x28,
    "PageUp": 0x21,
    "PageDown": 0x22,
    "Space": 0x20,
}
SPECIAL_KEY_ALIASES = {name.lower(): name for name in VK_SPECIAL_KEYS}
SPECIAL_KEY_ALIASES.update({
    "escape": "Esc",
    "return": "Enter",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "print": "PrintScreen",
    "prtsc": "PrintScreen",
    "prtscr": "PrintScreen",
})
DISALLOWED_HOTKEY_KEYS = {"Esc", "Tab", "Backspace", "Delete"}
RESERVED_HOTKEY_COMBOS = {
    ("Ctrl", "Alt", "Delete"),
    ("Alt", "Tab"),
    ("Ctrl", "Esc"),
    ("Ctrl", "Shift", "Esc"),
}
MODIFIER_ALIASES = {
    "ctrl": "Ctrl",
    "control": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win",
    "meta": "Win",
}
MODIFIER_ORDER = ("Ctrl", "Alt", "Shift", "Win")
MODIFIER_KEYS = {
    QtCore.Qt.Key_Control,
    QtCore.Qt.Key_Shift,
    QtCore.Qt.Key_Alt,
    QtCore.Qt.Key_Meta,
}
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000


def is_frozen_app():
    return bool(getattr(sys, "frozen", False))


def windows_startup_folder():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return ""
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def startup_shortcut_path():
    folder = windows_startup_folder()
    if not folder:
        return ""
    return os.path.join(folder, STARTUP_SHORTCUT_NAME)


def current_startup_target():
    if is_frozen_app():
        return os.path.abspath(sys.executable), "", APP_DIR
    return source_python_executable(), '"%s"' % os.path.abspath(__file__), APP_DIR


def source_python_executable():
    """소스 실행 자동실행은 가능하면 콘솔 없는 pythonw.exe 를 사용한다."""
    executable = os.path.abspath(sys.executable)
    if os.name == "nt" and os.path.basename(executable).lower() == "python.exe":
        pythonw = os.path.join(os.path.dirname(executable), "pythonw.exe")
        if os.path.exists(pythonw):
            return pythonw
    return executable


def ps_quote(value):
    return "'%s'" % str(value or "").replace("'", "''")


def run_powershell(script):
    last_error = None
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for executable in ("powershell.exe", "powershell"):
        try:
            result = subprocess.run(
                [executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "-"],
                input=script,
                text=True,
                capture_output=True,
                timeout=15,
                creationflags=flags,
            )
        except FileNotFoundError as exc:
            last_error = exc
            continue
        if result.returncode != 0:
            message = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(message or "PowerShell 실행에 실패했습니다.")
        return result.stdout.strip()
    raise RuntimeError("PowerShell을 찾을 수 없습니다. %s" % last_error)


def read_startup_shortcut(shortcut_path=None):
    shortcut_path = shortcut_path or startup_shortcut_path()
    if os.name != "nt" or not shortcut_path or not os.path.exists(shortcut_path):
        return None
    script = "\n".join([
        "$shortcutPath = %s" % ps_quote(shortcut_path),
        "$shell = New-Object -ComObject WScript.Shell",
        "$shortcut = $shell.CreateShortcut($shortcutPath)",
        "$data = @{ TargetPath = $shortcut.TargetPath; Arguments = $shortcut.Arguments }",
        "$data | ConvertTo-Json -Compress",
    ])
    output = run_powershell(script)
    return json.loads(output) if output else None


def startup_shortcut_matches_current(shortcut_path=None):
    info = read_startup_shortcut(shortcut_path)
    if not info:
        return False
    target, arguments, _working_dir = current_startup_target()
    actual_target = os.path.normcase(os.path.abspath(info.get("TargetPath") or ""))
    expected_target = os.path.normcase(os.path.abspath(target))
    actual_arguments = (info.get("Arguments") or "").strip()
    return actual_target == expected_target and actual_arguments == arguments.strip()


def startup_state():
    path = startup_shortcut_path()
    if os.name != "nt":
        return {"supported": False, "path": path, "exists": False, "matches": False, "error": ""}
    if not path:
        return {
            "supported": False,
            "path": "",
            "exists": False,
            "matches": False,
            "error": "APPDATA 환경 변수를 찾을 수 없습니다.",
        }
    exists = os.path.exists(path)
    if not exists:
        return {"supported": True, "path": path, "exists": False, "matches": False, "error": ""}
    # 트레이 메뉴를 열 때마다 PowerShell COM 을 동기 호출하면 UI가 멈출 수 있다.
    # 메뉴에서는 빠른 존재 여부만 보고, 경로 갱신은 명시적 메뉴 동작으로 처리한다.
    return {"supported": True, "path": path, "exists": True, "matches": True, "error": ""}


def create_startup_shortcut(shortcut_path=None):
    if os.name != "nt":
        raise RuntimeError("윈도우에서만 자동 실행을 설정할 수 있습니다.")
    shortcut_path = shortcut_path or startup_shortcut_path()
    if not shortcut_path:
        raise RuntimeError("시작프로그램 폴더를 찾을 수 없습니다.")
    target, arguments, working_dir = current_startup_target()
    script = "\n".join([
        "$shortcutPath = %s" % ps_quote(shortcut_path),
        "$targetPath = %s" % ps_quote(target),
        "$arguments = %s" % ps_quote(arguments),
        "$workingDirectory = %s" % ps_quote(working_dir),
        "$folder = Split-Path -Parent $shortcutPath",
        "New-Item -ItemType Directory -Force -Path $folder | Out-Null",
        "$shell = New-Object -ComObject WScript.Shell",
        "$shortcut = $shell.CreateShortcut($shortcutPath)",
        "$shortcut.TargetPath = $targetPath",
        "$shortcut.Arguments = $arguments",
        "$shortcut.WorkingDirectory = $workingDirectory",
        "$shortcut.IconLocation = \"$targetPath,0\"",
        "$shortcut.Save()",
    ])
    run_powershell(script)
    return shortcut_path


def remove_startup_shortcut(shortcut_path=None):
    shortcut_path = shortcut_path or startup_shortcut_path()
    if shortcut_path and os.path.exists(shortcut_path):
        os.remove(shortcut_path)
    return shortcut_path


def normalize_hotkeys(value):
    hotkeys = dict(HOTKEY_DEFAULTS)
    if isinstance(value, dict):
        for command, shortcut in value.items():
            if command in hotkeys and isinstance(shortcut, str):
                hotkeys[command] = normalize_shortcut_string(shortcut)
    return hotkeys


def normalize_key_name(value):
    text = str(value or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if len(upper) == 1 and upper.isalpha():
        return upper
    if len(upper) == 1 and upper.isdigit():
        return upper
    if upper.startswith("NUM") and upper[3:].isdigit():
        number = int(upper[3:])
        if 0 <= number <= 9:
            return "Num%d" % number
    if upper.startswith("F") and upper[1:].isdigit():
        number = int(upper[1:])
        if 1 <= number <= 24:
            return "F%d" % number
    return SPECIAL_KEY_ALIASES.get(text.lower(), "")


def normalize_shortcut_string(shortcut):
    parts = [p.strip() for p in str(shortcut or "").split("+") if p.strip()]
    if not parts:
        return ""

    modifiers = set()
    key_name = ""
    for part in parts:
        modifier = MODIFIER_ALIASES.get(part.lower())
        if modifier:
            modifiers.add(modifier)
            continue
        candidate = normalize_key_name(part)
        if not candidate or key_name:
            return ""
        key_name = candidate

    if not key_name:
        return ""
    if not modifiers and not key_name.startswith("Num"):
        return ""

    ordered = [modifier for modifier in MODIFIER_ORDER if modifier in modifiers]
    ordered.append(key_name)
    if not modifiers and key_name in DISALLOWED_HOTKEY_KEYS:
        return ""
    if tuple(ordered) in RESERVED_HOTKEY_COMBOS:
        return ""
    return "+".join(ordered)


def key_name_from_qt(key, keypad=False):
    if QtCore.Qt.Key_A <= key <= QtCore.Qt.Key_Z:
        return chr(ord("A") + key - QtCore.Qt.Key_A)
    if QtCore.Qt.Key_0 <= key <= QtCore.Qt.Key_9:
        if keypad:
            return "Num%d" % (key - QtCore.Qt.Key_0)
        return chr(ord("0") + key - QtCore.Qt.Key_0)
    if QtCore.Qt.Key_F1 <= key <= QtCore.Qt.Key_F24:
        return "F%d" % (key - QtCore.Qt.Key_F1 + 1)
    return KEY_NAME_MAP.get(key)


def shortcut_from_key_event(event):
    key = event.key()
    if key in MODIFIER_KEYS:
        return None, "Ctrl, Alt, Shift, Win 만으로는 단축키를 만들 수 없습니다."
    modifiers = event.modifiers()
    active_modifiers = modifiers & (
        QtCore.Qt.ControlModifier
        | QtCore.Qt.AltModifier
        | QtCore.Qt.ShiftModifier
        | QtCore.Qt.MetaModifier)
    if key in (QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete) and not active_modifiers:
        return "", None

    keypad = bool(modifiers & QtCore.Qt.KeypadModifier)
    key_name = key_name_from_qt(key, keypad=keypad)
    if not key_name:
        return None, "이 키는 단축키로 사용할 수 없습니다."

    parts = []
    if modifiers & QtCore.Qt.ControlModifier:
        parts.append("Ctrl")
    if modifiers & QtCore.Qt.AltModifier:
        parts.append("Alt")
    if modifiers & QtCore.Qt.ShiftModifier:
        parts.append("Shift")
    if modifiers & QtCore.Qt.MetaModifier:
        parts.append("Win")

    if not parts and not key_name.startswith("Num"):
        return None, "수식어 없는 단독키는 입력을 방해하므로 Ctrl, Alt, Shift, Win 중 하나와 함께 사용하세요. Num0~Num9만 단독 등록할 수 있습니다."
    parts.append(key_name)
    shortcut = "+".join(parts)
    normalized = normalize_shortcut_string(shortcut)
    if not normalized:
        return None, "이 키 조합은 Windows 예약 단축키이거나 사용할 수 없습니다."
    return normalized, None


def hotkey_to_windows(shortcut):
    shortcut = normalize_shortcut_string(shortcut)
    parts = [p.strip() for p in str(shortcut or "").split("+") if p.strip()]
    if not parts:
        return None
    modifiers = 0
    key_name = None
    for part in parts:
        lowered = part.lower()
        if lowered in ("ctrl", "control"):
            modifiers |= MOD_CONTROL
        elif lowered == "alt":
            modifiers |= MOD_ALT
        elif lowered == "shift":
            modifiers |= MOD_SHIFT
        elif lowered in ("win", "meta"):
            modifiers |= MOD_WIN
        else:
            key_name = part
    if not key_name:
        return None
    upper = key_name.upper()
    if upper.startswith("NUM") and upper[3:].isdigit() and 0 <= int(upper[3:]) <= 9:
        vk = 0x60 + int(upper[3:])
    elif len(upper) == 1 and upper.isalpha():
        vk = ord(upper)
    elif len(upper) == 1 and upper.isdigit():
        vk = ord(upper)
    elif upper.startswith("F") and upper[1:].isdigit() and 1 <= int(upper[1:]) <= 24:
        vk = 0x70 + int(upper[1:]) - 1
    else:
        vk = VK_SPECIAL_KEYS.get(key_name)
    if vk is None:
        return None
    return modifiers | MOD_NOREPEAT, vk


def assign_hotkey(hotkeys, command, shortcut):
    hotkeys = normalize_hotkeys(hotkeys)
    shortcut = str(shortcut or "").strip()
    messages = []
    if shortcut:
        for other, existing in list(hotkeys.items()):
            if other != command and existing.lower() == shortcut.lower():
                hotkeys[other] = ""
                messages.append(
                    "%s에 이미 등록된 %s 단축키를 삭제했습니다."
                    % (HOTKEY_LABELS.get(other, other), shortcut))
        if command == "toggle_visible":
            cleared = [name for name in ("show", "hide") if hotkeys.get(name)]
            for name in cleared:
                hotkeys[name] = ""
            if cleared:
                messages.append("토글 단축키를 등록해서 보이기/숨기기 개별 단축키를 삭제했습니다.")
        elif command in ("show", "hide") and hotkeys.get("toggle_visible"):
            hotkeys["toggle_visible"] = ""
            messages.append("보이기 또는 숨기기 단축키를 등록해서 토글 단축키를 삭제했습니다.")
    hotkeys[command] = shortcut
    return hotkeys, messages


def normalize_anchor(value):
    """anchor 는 None 또는 {"screen": str, "hx": 0..2, "vy": 0..2} 만 허용한다.
    설정 파일은 사용자가 직접 고칠 수 있으므로 어떤 값이 와도 시작을 막으면 안 된다."""
    if not isinstance(value, dict):
        return None
    try:
        hx = int(value["hx"])
        vy = int(value["vy"])
        screen = value["screen"]
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(screen, str) or not (0 <= hx <= 2 and 0 <= vy <= 2):
        return None
    return {"screen": screen, "hx": hx, "vy": vy}


def clamp_int(value, default, low, high):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def clamp_float(value, default, low, high):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def normalize_bool(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "1", "yes", "y", "on"):
            return True
        if text in ("false", "0", "no", "n", "off"):
            return False
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return bool(default)


def normalize_color(value, default, allow_none=False):
    if value is None and allow_none:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return list(default) if default is not None else None
    return [clamp_int(channel, int(default[i] if default is not None else 0), 0, 255)
            for i, channel in enumerate(value)]


def normalize_size(value):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    return [
        clamp_int(value[0], MIN_SIZE, MIN_SIZE, MAX_SIZE),
        clamp_int(value[1], MIN_SIZE, MIN_SIZE, MAX_SIZE),
    ]


def default_config():
    return json.loads(json.dumps(DEFAULTS))


def normalize_config(value):
    cfg = default_config()
    if isinstance(value, dict):
        cfg.update(value)

    cfg["path"] = cfg["path"] if isinstance(cfg.get("path"), str) else ""
    cfg["x"] = clamp_int(cfg.get("x"), DEFAULTS["x"], -100000, 100000)
    cfg["y"] = clamp_int(cfg.get("y"), DEFAULTS["y"], -100000, 100000)
    cfg["scale"] = clamp_float(cfg.get("scale"), DEFAULTS["scale"], 0.05, 20.0)
    cfg["size"] = normalize_size(cfg.get("size"))
    cfg["tolerance"] = clamp_int(cfg.get("tolerance"), DEFAULTS["tolerance"], 0, 200)
    cfg["softness"] = clamp_int(cfg.get("softness"), DEFAULTS["softness"], 0, 100)
    cfg["edge_thresh"] = clamp_int(cfg.get("edge_thresh"), DEFAULTS["edge_thresh"], 0, 255)
    cfg["bg_color"] = normalize_color(cfg.get("bg_color"), DEFAULTS["bg_color"])
    cfg["opacity"] = clamp_float(cfg.get("opacity"), DEFAULTS["opacity"], 0.1, 1.0)
    cfg["anchor"] = normalize_anchor(cfg.get("anchor"))
    cfg["snap_margin"] = clamp_int(cfg.get("snap_margin"), DEFAULTS["snap_margin"], 0, 500)
    cfg["chroma_bg"] = normalize_color(cfg.get("chroma_bg"), None, allow_none=True)
    for key in (
            "remove_bg", "despill", "edge_only", "holes", "auto_bg", "capturable",
            "click_through", "flip", "topmost", "hotkeys_enabled"):
        cfg[key] = normalize_bool(cfg.get(key), DEFAULTS[key])
    cfg["hotkeys"] = normalize_hotkeys(cfg.get("hotkeys"))
    cfg["hotkey_screen"] = cfg["hotkey_screen"] if isinstance(cfg.get("hotkey_screen"), str) else ""
    return cfg


def add_config_notice(message):
    if message not in CONFIG_NOTICES:
        CONFIG_NOTICES.append(message)


def consume_config_notices():
    notices = list(CONFIG_NOTICES)
    CONFIG_NOTICES[:] = []
    return notices


def initial_config_path():
    if os.path.exists(PORTABLE_CONFIG_PATH):
        return PORTABLE_CONFIG_PATH
    if os.path.exists(LOCAL_CONFIG_PATH):
        return LOCAL_CONFIG_PATH
    return PORTABLE_CONFIG_PATH


def load_config():
    global CONFIG_PATH
    cfg = default_config()
    CONFIG_PATH = initial_config_path()
    try:
        # utf-8-sig: 메모장이나 PowerShell 이 붙인 BOM 이 있어도 읽는다
        with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
        else:
            add_config_notice("설정 파일 형식이 올바르지 않아 기본값으로 시작했습니다.\n%s" % CONFIG_PATH)
    except Exception:
        if os.path.exists(CONFIG_PATH):
            add_config_notice("설정을 읽지 못해 기본값으로 시작했습니다.\n%s" % CONFIG_PATH)
    normalized = normalize_config(cfg)
    if normalized != cfg and os.path.exists(CONFIG_PATH):
        add_config_notice("설정값 일부가 올바르지 않아 기본값 또는 허용 범위로 보정했습니다.\n%s" % CONFIG_PATH)
    return normalized


def save_config(cfg):
    global CONFIG_PATH
    def write(path):
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        tmp_path = "%s.tmp" % path
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    try:
        write(CONFIG_PATH)
    except Exception as primary_error:
        if CONFIG_PATH != LOCAL_CONFIG_PATH:
            try:
                write(LOCAL_CONFIG_PATH)
                CONFIG_PATH = LOCAL_CONFIG_PATH
                add_config_notice(
                    "실행 파일 폴더에 설정을 저장하지 못해 사용자 설정 폴더로 전환했습니다.\n%s"
                    % LOCAL_CONFIG_PATH)
                return
            except Exception as fallback_error:
                add_config_notice(
                    "설정을 저장하지 못했습니다.\n%s\n%s"
                    % (primary_error, fallback_error))
        else:
            add_config_notice("설정을 저장하지 못했습니다.\n%s" % primary_error)


# ---------------------------------------------------------------- 업데이트 확인

def parse_version(value):
    """v0.2.1 같은 릴리스 태그를 (major, minor, patch, prerelease) 로 바꾼다."""
    text = str(value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    text = text.split("+", 1)[0]
    prerelease = ""
    if "-" in text:
        text, prerelease = text.split("-", 1)
    if not text:
        return None
    parts = text.split(".")
    nums = []
    for part in parts:
        if not part.isdigit():
            return None
        nums.append(int(part))
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3] + [prerelease])


def compare_versions(left_tag, right_tag):
    left = parse_version(left_tag)
    right = parse_version(right_tag)
    if not left or not right:
        return None
    left_nums, right_nums = left[:3], right[:3]
    if left_nums != right_nums:
        return 1 if left_nums > right_nums else -1
    left_pre, right_pre = left[3], right[3]
    if left_pre == right_pre:
        return 0
    if left_pre and not right_pre:
        return -1
    if right_pre and not left_pre:
        return 1
    return 1 if left_pre > right_pre else -1


def is_newer_version(latest_tag, current_version=APP_VERSION):
    latest = parse_version(latest_tag)
    if not latest or latest[3]:
        return False
    compared = compare_versions(latest_tag, current_version)
    return bool(compared and compared > 0)


def fetch_latest_release():
    req = urllib.request.Request(
        RELEASES_LATEST_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "%s/%s" % (APP_NAME, APP_VERSION),
        },
    )
    with urllib.request.urlopen(req, timeout=UPDATE_CHECK_TIMEOUT_SEC) as response:
        data = json.loads(response.read().decode("utf-8"))
    tag = data.get("tag_name") or ""
    parsed = parse_version(tag)
    if not parsed:
        raise ValueError("릴리스 태그 형식을 확인할 수 없습니다: %s" % (tag or "(없음)"))
    if parsed[3]:
        raise ValueError("프리릴리스 태그는 자동 업데이트 대상이 아닙니다: %s" % tag)
    return {
        "tag": tag,
        "name": data.get("name") or tag,
        "url": data.get("html_url") or RELEASES_LATEST_URL,
        "newer": is_newer_version(tag),
    }


# ---------------------------------------------------------------- 이미지 처리

def fit_size_within_pixels(width, height, max_pixels=None):
    max_pixels = MAX_FRAME_PIXELS if max_pixels is None else max_pixels
    pixels = max(1, int(width) * int(height))
    if pixels <= max_pixels:
        return int(width), int(height)
    scale = (float(max_pixels) / float(pixels)) ** 0.5
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def frame_limit_for_image(width, height):
    pixels = max(1, int(width) * int(height))
    pixel_limited = max(1, MAX_GIF_TOTAL_PIXELS // pixels)
    return max(1, min(MAX_GIF_FRAMES, pixel_limited))


def selected_frame_indices(total_frames, frame_limit):
    total_frames = int(total_frames or 0)
    frame_limit = max(1, int(frame_limit or 1))
    if total_frames <= 0:
        return set()
    if total_frames <= frame_limit:
        return set(range(total_frames))
    if frame_limit == 1:
        return {0}
    return {
        int(round(i * (total_frames - 1) / float(frame_limit - 1)))
        for i in range(frame_limit)
    }


def frame_to_array(image, metadata=None):
    original_size = image.size
    target_size = fit_size_within_pixels(original_size[0], original_size[1])
    if target_size != original_size:
        image = image.resize(target_size, RESAMPLE_LANCZOS)
        if metadata is not None:
            metadata["downsized"] = True
            metadata["original_size"] = list(original_size)
            metadata["stored_size"] = list(target_size)
    return np.array(image)


def read_frames(path, metadata=None, cancel_check=None):
    """어떤 이미지든 (RGBA numpy 배열, 지속시간ms) 목록으로 읽는다."""
    im = Image.open(path)
    frames = []
    if getattr(im, "is_animated", False):
        last = None
        total = int(getattr(im, "n_frames", 0) or 0)
        stored_w, stored_h = fit_size_within_pixels(im.size[0], im.size[1])
        frame_limit = frame_limit_for_image(stored_w, stored_h)
        selected = selected_frame_indices(total, frame_limit) if total else None
        pending_delay = 0
        source_count = 0
        for index, frame in enumerate(ImageSequence.Iterator(im)):
            if cancel_check:
                cancel_check()
            source_count += 1
            cur = frame.convert("RGBA")
            if last is not None and frame.tile:
                # 부분 갱신 프레임이면 이전 프레임 위에 합성
                merged = last.copy()
                merged.alpha_composite(cur)
                cur = merged
            last = cur
            delay = frame.info.get("duration", 100) or 100
            delay = max(20, int(delay))
            if selected is None or index in selected:
                frames.append((frame_to_array(cur, metadata), pending_delay + delay))
                pending_delay = 0
            else:
                pending_delay += delay
        if pending_delay and frames:
            frame, delay = frames[-1]
            frames[-1] = (frame, delay + pending_delay)
        if metadata is not None:
            metadata["source_frame_count"] = source_count
            metadata["stored_frame_count"] = len(frames)
            metadata["frame_limit"] = frame_limit
            metadata["dropped_frames"] = max(0, source_count - len(frames))
            metadata["source_pixels"] = int(im.size[0]) * int(im.size[1])
            metadata["stored_pixels"] = int(stored_w) * int(stored_h)
            metadata["total_pixel_limit"] = MAX_GIF_TOTAL_PIXELS
    else:
        if cancel_check:
            cancel_check()
        frames.append((frame_to_array(im.convert("RGBA"), metadata), 100))
        if metadata is not None:
            metadata["source_frame_count"] = 1
            metadata["stored_frame_count"] = 1
            metadata["dropped_frames"] = 0
    return frames


def already_transparent(rgba):
    """가장자리가 이미 투명하면(투명 PNG/GIF) 배경 제거를 할 필요가 없다."""
    a = rgba[:, :, 3]
    border = np.concatenate([a[0, :], a[-1, :], a[:, 0], a[:, -1]])
    return (border < 16).mean() > 0.9


def detect_bg_color(rgba):
    """네 모서리 영역에서 가장 흔한 색을 배경색으로 추정."""
    h, w = rgba.shape[:2]
    k = max(2, min(h, w) // 20)
    corners = np.concatenate([
        rgba[:k, :k].reshape(-1, 4),
        rgba[:k, -k:].reshape(-1, 4),
        rgba[-k:, :k].reshape(-1, 4),
        rgba[-k:, -k:].reshape(-1, 4),
    ])
    corners = corners[corners[:, 3] > 128][:, :3]
    if len(corners) == 0:
        return np.array([255, 255, 255], dtype=np.float32)
    q = (corners // 8).astype(np.int32)
    keys = q[:, 0] * 4096 + q[:, 1] * 64 + q[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    top = vals[counts.argmax()]
    mask = keys == top
    return corners[mask].mean(axis=0).astype(np.float32)


def edge_strength(rgb):
    """인접 픽셀과의 색 차이. 캐릭터의 외곽선(선화)에서 크게 나온다."""
    g = rgb.mean(axis=2)
    dx = np.zeros_like(g)
    dy = np.zeros_like(g)
    dx[:, 1:] = np.abs(np.diff(g, axis=1))
    dy[1:, :] = np.abs(np.diff(g, axis=0))
    e = np.maximum(dx, dy)
    # 차이는 두 픽셀 사이에서 생기므로 양쪽 모두를 벽으로 본다
    e[:, :-1] = np.maximum(e[:, :-1], e[:, 1:])
    e[:-1, :] = np.maximum(e[:-1, :], e[1:, :])
    return e


def outside_region(passable):
    """이미지 가장자리에서 passable 을 따라 이어진 영역만 True.
    캐릭터 외곽선은 passable 이 아니므로 채우기가 안쪽으로 못 들어간다.
    행/열 단위 전파로 연결 영역을 찾는다. 픽셀별 파이썬 루프보다 큰 GIF에서 훨씬 빠르다."""
    h, w = passable.shape
    filled = np.zeros((h, w), dtype=bool)
    filled[0, :] = passable[0, :]
    filled[-1, :] |= passable[-1, :]
    filled[:, 0] |= passable[:, 0]
    filled[:, -1] |= passable[:, -1]

    while True:
        old = filled.copy()
        for _ in range(2):
            for x in range(1, w):
                filled[:, x] |= filled[:, x - 1] & passable[:, x]
            for x in range(w - 2, -1, -1):
                filled[:, x] |= filled[:, x + 1] & passable[:, x]
            for y in range(1, h):
                filled[y, :] |= filled[y - 1, :] & passable[y, :]
            for y in range(h - 2, -1, -1):
                filled[y, :] |= filled[y + 1, :] & passable[y, :]
        if np.array_equal(old, filled):
            break
    return filled


def key_out(rgba, bg, tolerance, softness, despill, edge_only=True, edge_thresh=14,
            holes=True):
    """캐릭터 외곽선 바깥쪽을 투명하게. 반환: RGBA uint8"""
    if already_transparent(rgba):
        return rgba          # 이미 배경이 투명하다 - 그대로 둔다

    rgb = rgba[:, :, :3].astype(np.float32)
    src_a = rgba[:, :, 3].astype(np.float32) / 255.0

    dist = np.abs(rgb - bg.reshape(1, 1, 3)).max(axis=2)

    lo = float(tolerance)
    hi = lo + max(1.0, float(softness))
    soft = np.clip((dist - lo) / (hi - lo), 0.0, 1.0)

    if edge_only:
        # 배경색과 비슷하면서 & 외곽선이 아닌 픽셀만 채우기가 지나갈 수 있다
        passable = (dist < hi) & (edge_strength(rgb) < float(edge_thresh))
        outside = outside_region(passable)

        alpha = np.where(outside, 0.0, 1.0)
        # 바깥과 맞닿은 픽셀만 원래의 부드러운 알파를 써서 계단현상을 줄인다
        nb = np.zeros_like(outside)
        nb[:, :-1] |= outside[:, 1:]
        nb[:, 1:] |= outside[:, :-1]
        nb[:-1, :] |= outside[1:, :]
        nb[1:, :] |= outside[:-1, :]
        # 캐릭터에 둘러싸여 바깥과 끊긴 배경색 덩어리(팔과 몸 사이 등)도 지운다.
        # 단 흰/검/회색 배경에서는 캐릭터 고유색과 구분이 안 되므로 하지 않는다.
        if holes and float(bg.max() - bg.min()) > 60.0:
            enclosed = ~outside & (dist < lo)
            alpha = np.where(enclosed, 0.0, alpha)

        border = nb & ~outside
        alpha = np.where(border, np.maximum(soft, 0.0), alpha)
    else:
        alpha = soft

    alpha *= src_a

    out = rgba.copy()
    if despill:
        # 반투명 가장자리에서 배경색 성분을 빼서 흰 테두리 제거
        with np.errstate(divide="ignore", invalid="ignore"):
            edge = (alpha > 0.02) & (alpha < 0.98)
            a = alpha[..., None]
            un = np.where(a > 0.02, (rgb - bg.reshape(1, 1, 3) * (1 - a)) / np.maximum(a, 0.02), rgb)
            un = np.clip(un, 0, 255)
            rgb = np.where(edge[..., None], un, rgb)
        out[:, :, :3] = rgb.astype(np.uint8)

    out[:, :, 3] = (alpha * 255).astype(np.uint8)
    return out


WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1


def to_qpixmap(rgba):
    h, w = rgba.shape[:2]
    buf = np.ascontiguousarray(rgba)
    img = QtGui.QImage(buf.data, w, h, w * 4, QtGui.QImage.Format_RGBA8888).copy()
    return QtGui.QPixmap.fromImage(img)


class WorkerCancelled(Exception):
    pass


def render_frame_arrays(frames, cfg, bg_color=None, cancel_check=None):
    rendered = []
    if not cfg.get("remove_bg"):
        for frame, delay in frames:
            if cancel_check:
                cancel_check()
            rendered.append((frame, delay))
        return rendered
    bg = np.array(bg_color if bg_color is not None else cfg["bg_color"], dtype=np.float32)
    for frame, delay in frames:
        if cancel_check:
            cancel_check()
        rendered.append((
            key_out(frame, bg, cfg["tolerance"], cfg["softness"],
                    cfg["despill"], cfg["edge_only"], cfg["edge_thresh"], cfg["holes"]),
            delay,
        ))
    return rendered


class ImageProcessWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(int, object)
    failed = QtCore.pyqtSignal(int, str, str, str)
    cancelled = QtCore.pyqtSignal(int)

    def __init__(self, job_id, cfg, path=None, frames=None, detect_bg=False):
        super().__init__()
        self.job_id = job_id
        self.cfg = dict(cfg)
        self.path = path
        self.frames = frames
        self.detect_bg = detect_bg
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def check_cancelled(self):
        if self._cancelled:
            raise WorkerCancelled()

    @QtCore.pyqtSlot()
    def run(self):
        try:
            metadata = {}
            if self.frames is not None:
                frames = self.frames
            else:
                try:
                    frames = read_frames(self.path, metadata, self.check_cancelled)
                except WorkerCancelled:
                    raise
                except Exception as e:
                    self.failed.emit(self.job_id, self.path or "", "read", str(e))
                    return
            self.check_cancelled()
            bg_color = self.cfg.get("bg_color")
            if self.detect_bg and frames:
                bg_color = detect_bg_color(frames[0][0]).tolist()
            rendered = render_frame_arrays(frames, self.cfg, bg_color, self.check_cancelled)
            self.check_cancelled()
            self.finished.emit(self.job_id, {
                "path": self.path,
                "frames": frames,
                "rendered": rendered,
                "bg_color": bg_color,
                "metadata": metadata,
            })
        except WorkerCancelled:
            self.cancelled.emit(self.job_id)
        except Exception as e:
            self.failed.emit(self.job_id, self.path or "", "process", str(e))


class UpdateCheckWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(int, object, bool)
    failed = QtCore.pyqtSignal(int, str, bool)

    def __init__(self, job_id, silent):
        super().__init__()
        self.job_id = job_id
        self.silent = silent

    @QtCore.pyqtSlot()
    def run(self):
        try:
            self.finished.emit(self.job_id, fetch_latest_release(), self.silent)
        except Exception as e:
            self.failed.emit(self.job_id, str(e), self.silent)


# ---------------------------------------------------------------- 오버레이 창

class SizeDialog(QtWidgets.QDialog):
    """가로/세로를 직접 입력. 원본 비율 유지 옵션 포함."""

    def __init__(self, w, h, base_size):
        super().__init__(None)
        self.setWindowTitle("크기 직접 입력")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.ratio = (base_size[1] / base_size[0]) if base_size[0] else 1.0
        self._syncing = False

        self.w_box = QtWidgets.QSpinBox()
        self.h_box = QtWidgets.QSpinBox()
        for box, v in ((self.w_box, w), (self.h_box, h)):
            box.setRange(MIN_SIZE, MAX_SIZE)
            box.setSuffix(" px")
            box.setValue(int(v))

        self.lock = QtWidgets.QCheckBox("원본 비율 유지")
        self.lock.setChecked(True)
        self.w_box.valueChanged.connect(self.on_w)
        self.h_box.valueChanged.connect(self.on_h)

        form = QtWidgets.QFormLayout()
        form.addRow("너비", self.w_box)
        form.addRow("높이", self.h_box)
        form.addRow("", self.lock)

        hint = QtWidgets.QLabel("원본 %d x %d · 최소 %d px" % (base_size[0], base_size[1], MIN_SIZE))
        hint.setStyleSheet("color: gray;")

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        reset = buttons.addButton("원본 크기", QtWidgets.QDialogButtonBox.ResetRole)
        reset.clicked.connect(lambda: (self.w_box.setValue(max(MIN_SIZE, base_size[0])),
                                       self.h_box.setValue(max(MIN_SIZE, base_size[1]))))

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hint)
        lay.addWidget(buttons)

    def on_w(self, v):
        if self.lock.isChecked() and not self._syncing:
            self._syncing = True
            self.h_box.setValue(max(MIN_SIZE, int(round(v * self.ratio))))
            self._syncing = False

    def on_h(self, v):
        if self.lock.isChecked() and not self._syncing:
            self._syncing = True
            self.w_box.setValue(max(MIN_SIZE, int(round(v / self.ratio))))
            self._syncing = False

    def values(self):
        return self.w_box.value(), self.h_box.value()


class HotkeyManager(QtCore.QAbstractNativeEventFilter):
    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.registered = {}
        self.installed = False
        self.next_id = 7100

    def register_all(self, hotkeys):
        if os.name != "nt":
            return []
        self.unregister_all()
        app = QtCore.QCoreApplication.instance()
        if app and not self.installed:
            app.installNativeEventFilter(self)
            self.installed = True

        errors = []
        for command, shortcut in normalize_hotkeys(hotkeys).items():
            if not shortcut:
                continue
            parsed = hotkey_to_windows(shortcut)
            if not parsed:
                errors.append("%s: 지원하지 않는 단축키(%s)" % (
                    HOTKEY_LABELS.get(command, command), shortcut))
                continue
            modifiers, vk = parsed
            hotkey_id = self.next_id
            self.next_id += 1
            if not ctypes.windll.user32.RegisterHotKey(None, hotkey_id, modifiers, vk):
                errors.append("%s: 다른 프로그램이 사용 중이거나 Windows에서 거부했습니다(%s)" % (
                    HOTKEY_LABELS.get(command, command), shortcut))
                continue
            self.registered[hotkey_id] = command
        return errors

    def unregister_all(self):
        if os.name == "nt":
            for hotkey_id in list(self.registered):
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        self.registered.clear()

    def nativeEventFilter(self, event_type, message):
        if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG",
                              "windows_generic_MSG", "windows_dispatcher_MSG"):
            return False, 0
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message != WM_HOTKEY:
            return False, 0
        command = self.registered.get(int(msg.wParam))
        if not command:
            return False, 0
        QtCore.QTimer.singleShot(0, lambda c=command: self.pet.execute_hotkey(c))
        return True, 0


class HotkeyCaptureButton(QtWidgets.QPushButton):
    captured = QtCore.pyqtSignal(str, str, str)

    def __init__(self, command, parent=None):
        super().__init__(parent)
        self.command = command
        self.shortcut = ""
        self.capturing = False
        self.clicked.connect(self.start_capture)
        self.setMinimumWidth(150)
        self.refresh()

    def set_shortcut(self, shortcut):
        self.shortcut = shortcut or ""
        self.refresh()

    def refresh(self):
        if self.capturing:
            self.setText("키를 누르세요...")
        else:
            self.setText(self.shortcut or "미등록")

    def start_capture(self):
        self.capturing = True
        self.setFocus(QtCore.Qt.MouseFocusReason)
        self.refresh()

    def keyPressEvent(self, event):
        if not self.capturing:
            super().keyPressEvent(event)
            return
        active_modifiers = event.modifiers() & (
            QtCore.Qt.ControlModifier
            | QtCore.Qt.AltModifier
            | QtCore.Qt.ShiftModifier
            | QtCore.Qt.MetaModifier)
        if event.key() == QtCore.Qt.Key_Escape and not active_modifiers:
            self.capturing = False
            self.refresh()
            return
        if event.key() in MODIFIER_KEYS:
            event.accept()
            return
        shortcut, error = shortcut_from_key_event(event)
        self.capturing = False
        self.refresh()
        self.captured.emit(self.command, shortcut or "", error or "")

    def keyReleaseEvent(self, event):
        if not self.capturing or event.key() not in MODIFIER_KEYS:
            super().keyReleaseEvent(event)
            return
        active_modifiers = event.modifiers() & (
            QtCore.Qt.ControlModifier
            | QtCore.Qt.AltModifier
            | QtCore.Qt.ShiftModifier
            | QtCore.Qt.MetaModifier)
        if not active_modifiers:
            self.capturing = False
            self.refresh()
            self.captured.emit(
                self.command,
                "",
                "Ctrl, Alt, Shift, Win 만으로는 단축키를 만들 수 없습니다.")
        event.accept()


class HotkeyDialog(QtWidgets.QDialog):
    def __init__(self, pet):
        super().__init__(None)
        self.pet = pet
        self.hotkeys = normalize_hotkeys(pet.cfg.get("hotkeys"))
        self.buttons = {}
        self._hotkeys_released = False
        self.setWindowTitle("단축키 설정")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        self.setMinimumSize(980, 720)
        self.resize(1080, 760)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        hint = QtWidgets.QLabel(
            "단축키 버튼을 누른 뒤 원하는 키를 입력하세요. 기본값은 모두 미등록입니다.")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.screen_combo = QtWidgets.QComboBox()
        self.populate_screens()
        screen_row = QtWidgets.QHBoxLayout()
        screen_row.addWidget(QtWidgets.QLabel("위치 단축키 대상 모니터"))
        screen_row.addWidget(self.screen_combo, 1)
        root.addLayout(screen_row)

        body_layout = QtWidgets.QHBoxLayout()
        body_layout.setSpacing(12)
        left_column = QtWidgets.QVBoxLayout()
        right_column = QtWidgets.QVBoxLayout()
        self.add_group(left_column, "표시", ["toggle_visible", "show", "hide"])
        self.add_group(left_column, "이미지/창", [
            "open_image", "flip", "topmost", "click_through", "disable_hotkeys"])
        self.add_group(
            left_column,
            "크기",
            ["scale_%d" % v for v in SIZE_PRESETS] + ["scale_cycle"])
        left_column.addStretch(1)
        self.add_group(right_column, "위치", ["snap_%s" % code for _label, _hx, _vy, code in SNAP_SPOTS])
        right_column.addStretch(1)
        body_layout.addLayout(left_column, 1)
        body_layout.addLayout(right_column, 1)
        root.addLayout(body_layout, 1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        reset = buttons.addButton("전체 초기화", QtWidgets.QDialogButtonBox.ResetRole)
        reset.clicked.connect(self.reset_all)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.center_on_primary()

    def showEvent(self, event):
        if not self._hotkeys_released:
            self.pet.unregister_hotkeys()
            self._hotkeys_released = True
        super().showEvent(event)

    def closeEvent(self, event):
        super().closeEvent(event)

    def populate_screens(self):
        selected = self.pet.cfg.get("hotkey_screen") or ""
        primary = QtWidgets.QApplication.primaryScreen()
        for index, screen in enumerate(QtWidgets.QApplication.screens(), start=1):
            g = screen.geometry()
            label = "%s 모니터 %d (%dx%d)" % (
                "주" if screen == primary else "보조", index, g.width(), g.height())
            self.screen_combo.addItem(label, screen.name())
            if selected and screen.name() == selected:
                self.screen_combo.setCurrentIndex(self.screen_combo.count() - 1)
        if not selected and primary:
            for i in range(self.screen_combo.count()):
                if self.screen_combo.itemData(i) == primary.name():
                    self.screen_combo.setCurrentIndex(i)
                    break

    def add_group(self, layout, title, commands):
        group = QtWidgets.QGroupBox(title)
        form = QtWidgets.QGridLayout(group)
        form.setContentsMargins(10, 10, 10, 10)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)
        form.setColumnStretch(1, 1)
        for row, command in enumerate(commands):
            form.addWidget(QtWidgets.QLabel(HOTKEY_LABELS[command]), row, 0)
            capture = HotkeyCaptureButton(command)
            capture.set_shortcut(self.hotkeys.get(command, ""))
            capture.captured.connect(self.on_captured)
            self.buttons[command] = capture
            form.addWidget(capture, row, 1)
            clear = QtWidgets.QPushButton("삭제")
            clear.clicked.connect(lambda _=False, c=command: self.set_hotkey(c, ""))
            form.addWidget(clear, row, 2)
        layout.addWidget(group)

    def on_captured(self, command, shortcut, error):
        if error:
            QtWidgets.QMessageBox.warning(self, "단축키 설정 불가", error)
            return
        self.set_hotkey(command, shortcut)

    def set_hotkey(self, command, shortcut):
        self.hotkeys, messages = assign_hotkey(self.hotkeys, command, shortcut)
        if command == "disable_hotkeys" and shortcut:
            messages.append(
                "이 단축키를 누르면 모든 단축키가 비활성화됩니다. 다시 켜려면 트레이 메뉴에서 단축키 활성화를 선택하세요.")
        self.sync_buttons()
        if messages:
            QtWidgets.QMessageBox.information(self, "단축키 정리", "\n".join(messages))

    def sync_buttons(self):
        for command, button in self.buttons.items():
            button.set_shortcut(self.hotkeys.get(command, ""))

    def reset_all(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            "전체 초기화",
            "등록된 단축키를 모두 삭제할까요?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.hotkeys = dict(HOTKEY_DEFAULTS)
            self.sync_buttons()

    def selected_screen_name(self):
        return self.screen_combo.currentData() or ""

    def accept(self):
        self.pet.cfg["hotkeys"] = normalize_hotkeys(self.hotkeys)
        self.pet.cfg["hotkey_screen"] = self.selected_screen_name()
        self.pet.persist(immediate=True)
        self.pet.register_hotkeys(show_errors=True)
        self._hotkeys_released = False
        super().accept()

    def reject(self):
        self.pet.register_hotkeys(show_errors=True)
        self._hotkeys_released = False
        super().reject()

    def center_on_primary(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        max_width = max(640, geo.width() - 40)
        max_height = max(640, geo.height() - 40)
        self.resize(min(self.width(), max_width), min(self.height(), max_height))
        self.move(geo.center() - self.rect().center())


class Pet(QtWidgets.QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.frames = []        # (rgba, delay)
        self.pixmaps = []
        self.index = 0
        self.base_size = (200, 200)
        self._drag = None
        self._drag_start_global = None
        self._drag_start_window = None
        self._drag_moved = False
        self._job_id = 0
        self._workers = []
        self._update_job_id = 0
        self._update_workers = []
        self.update_checking = False
        self.update_available = False
        self.latest_release = None
        self.last_update_error = ""
        self.tray = None
        self.hotkey_manager = HotkeyManager(self)
        self.hidden = False      # 숨김 상태는 저장하지 않는다. 다음 실행 때는 항상 보인다
        self.need_image = None   # None / "first" / "missing"
        self.missing_image_path = None
        self.startup_missing_path = None
        self.ready = False       # 초기화 중에는 위치 보정을 하지 않는다
        self._sized_once = False # 첫 렌더 크기 확정 전에는 640x480 기본 창 중심을 보존하면 안 된다

        self.setWindowTitle(APP_NAME)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.apply_window_flags()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self._persist_timer = QtCore.QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.timeout.connect(self.flush_persist)

        startup_missing_path = cfg.pop("_startup_missing_path", None)
        if startup_missing_path:
            self.startup_missing_path = startup_missing_path

        self.move(cfg["x"], cfg["y"])
        # 이미지가 없으면 파일 대화상자를 곧바로 띄우지 않는다.
        # 트레이 아이콘이 준비된 뒤 알림으로 안내한다 (main 에서 prompt_if_no_image 호출).
        if startup_missing_path and cfg["path"] and os.path.exists(cfg["path"]):
            self.load_image(cfg["path"])
        elif startup_missing_path:
            self.need_image = "missing"
            self.missing_image_path = startup_missing_path
        elif not cfg["path"]:
            self.need_image = "first"
        elif not os.path.exists(cfg["path"]):
            self.need_image = "missing"
            self.missing_image_path = cfg["path"]
        else:
            self.load_image(cfg["path"])

        self.ready = True
        # 저장된 위치를 복원한다. 바로가기로 옮겨 둔 상태면 그 구석으로 다시 붙는다
        if cfg.get("anchor"):
            self.restore_position()
        self.persist(immediate=True)   # 첫 실행에서도 설정 파일이 생기도록

    # ---- 창 속성
    def apply_window_flags(self):
        flags = QtCore.Qt.FramelessWindowHint
        if self.cfg.get("capturable"):
            # 일반 창(WS_EX_TOOLWINDOW 없음)이라야 OBS/PRISM 윈도우 캡처 목록에 뜬다.
            # 대신 작업표시줄에도 항목이 생긴다.
            flags |= QtCore.Qt.Window
        else:
            flags |= QtCore.Qt.Tool
        if self.cfg["topmost"]:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if not self.hidden:
            self.show()
            self.raise_()
        self.setWindowOpacity(float(self.cfg.get("opacity", 1.0)))

    def toggle_visible(self):
        """방송 중 즉시 감추기. 트레이 아이콘은 남아 있어 언제든 되돌릴 수 있다."""
        self.set_visible_state(self.hidden)

    def set_visible_state(self, visible):
        self.hidden = not bool(visible)
        if self.hidden:
            self.hide()
        else:
            self.show()
            self.raise_()
        if self.tray:
            self.tray.setToolTip("%s (%s)" % (APP_NAME, "숨김" if self.hidden else "표시 중"))

    def set_opacity(self, v):
        self.cfg["opacity"] = v
        self.setWindowOpacity(v)
        self.persist()

    def nativeEvent(self, event_type, message):
        """클릭 통과: WM_NCHITTEST 에 HTTRANSPARENT 를 돌려주면 마우스가 아래 창으로 넘어간다.
        WS_EX_TRANSPARENT 와 달리 창 렌더링에는 영향이 없다."""
        if self.cfg.get("click_through") and event_type == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST:
                return True, HTTRANSPARENT
        return super().nativeEvent(event_type, message)

    # ---- 로딩 / 처리
    def prompt_if_no_image(self):
        """띄울 이미지가 없을 때 트레이 알림으로 안내한다.
        파일 대화상자를 강제로 띄우면 트레이에 있는 프로그램이라는 걸 알기 어렵다."""
        if not self.tray:
            return
        if self.startup_missing_path:
            self.tray.showMessage(
                "전달받은 이미지 경로를 찾을 수 없습니다",
                "%s\n저장된 이미지가 있으면 대신 복원했습니다." % self.startup_missing_path,
                QtWidgets.QSystemTrayIcon.Warning,
                10000)
            self.startup_missing_path = None
        if not self.need_image:
            return
        if self.need_image == "first":
            title = "%s 를 시작했습니다" % APP_NAME
            body = ("띄울 이미지가 아직 없습니다.\n"
                    "트레이 아이콘을 클릭해 [이미지 열기] 를 선택하세요.")
        else:
            title = "이미지를 찾을 수 없습니다"
            body = ("전에 쓰던 파일이 옮겨졌거나 삭제되었습니다.\n%s\n"
                    "트레이 아이콘을 클릭해 [이미지 열기] 로 다시 선택하세요."
                    % (self.missing_image_path or self.cfg["path"]))
        self.tray.showMessage(title, body, QtWidgets.QSystemTrayIcon.Information, 10000)
        self.tray.setToolTip("%s - 이미지를 선택하세요" % APP_NAME)

    def prompt_config_notices(self):
        if not self.tray:
            return
        for notice in consume_config_notices():
            self.tray.showMessage("설정 안내", notice, QtWidgets.QSystemTrayIcon.Warning, 10000)

    def schedule_update_check(self):
        QtCore.QTimer.singleShot(3000, lambda: self.check_for_updates(silent=True))

    def check_for_updates(self, silent=False):
        if self.update_checking:
            if self.tray and not silent:
                self.tray.showMessage(
                    "업데이트 확인",
                    "이미 최신 릴리스를 확인하는 중입니다.",
                    QtWidgets.QSystemTrayIcon.Information,
                    5000)
            return

        self._update_job_id += 1
        job_id = self._update_job_id
        self.update_checking = True
        self.last_update_error = ""
        if self.tray:
            self.tray.refresh_icon()

        thread = QtCore.QThread(self)
        worker = UpdateCheckWorker(job_id, silent)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_update_check_finished)
        worker.failed.connect(self.on_update_check_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(lambda w=worker, t=thread: self.cleanup_update_worker(w, t))
        self._update_workers.append((worker, thread))
        thread.start()

    def cleanup_update_worker(self, worker, thread):
        self._update_workers = [
            (w, t) for w, t in self._update_workers
            if w is not worker and t is not thread
        ]
        worker.deleteLater()
        thread.deleteLater()

    def on_update_check_finished(self, job_id, result, silent):
        if job_id != self._update_job_id:
            return
        self.update_checking = False
        self.latest_release = result
        self.update_available = bool(result.get("newer"))
        if self.tray:
            self.tray.refresh_icon()
            if self.update_available and not silent:
                self.tray.showMessage(
                    "업데이트가 있습니다",
                    "%s 릴리스를 사용할 수 있습니다.\n트레이 메뉴에서 업데이트 페이지를 여세요."
                    % result.get("tag", "새 버전"),
                    QtWidgets.QSystemTrayIcon.Information,
                    10000)
            elif not silent:
                self.tray.showMessage(
                    "최신 버전입니다",
                    "현재 버전 %s 이 최신 릴리스입니다." % APP_VERSION,
                    QtWidgets.QSystemTrayIcon.Information,
                    5000)

    def on_update_check_failed(self, job_id, message, silent):
        if job_id != self._update_job_id:
            return
        self.update_checking = False
        self.last_update_error = message
        if self.tray:
            self.tray.refresh_icon()
            if not silent:
                self.tray.showMessage(
                    "업데이트 확인 실패",
                    message,
                    QtWidgets.QSystemTrayIcon.Warning,
                    10000)

    def open_update_page(self):
        url = RELEASES_LATEST_URL
        if self.latest_release and self.latest_release.get("url"):
            url = self.latest_release["url"]
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def pick_file(self):
        start = self.cfg["path"] if os.path.exists(self.cfg["path"] or "") else os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            None, "띄울 이미지 선택", start, IMAGE_FILTER)
        if path:
            self.cfg["path"] = path
            self.need_image = None
            self.load_image(path)
            self.persist()
            if self.tray:
                self.tray.setToolTip(APP_NAME)

    def load_image(self, path):
        self.need_image = None
        self.start_processing(path=path, frames=None, detect_bg=bool(self.cfg["auto_bg"]))

    def rebuild(self):
        if not self.frames:
            return
        self.start_processing(path=None, frames=self.frames, detect_bg=False)

    def start_processing(self, path=None, frames=None, detect_bg=False):
        self._job_id += 1
        job_id = self._job_id
        self.cancel_processing_workers()
        if self.tray:
            self.tray.setToolTip(PROCESSING_TOOLTIP)

        thread = QtCore.QThread(self)
        worker = ImageProcessWorker(job_id, self.cfg, path=path, frames=frames, detect_bg=detect_bg)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.on_processing_finished)
        worker.failed.connect(self.on_processing_failed)
        worker.cancelled.connect(thread.quit)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(lambda w=worker, t=thread: self.cleanup_worker(w, t))
        self._workers.append((worker, thread))
        thread.start()

    def cancel_processing_workers(self):
        for worker, _thread in list(self._workers):
            if hasattr(worker, "cancel"):
                worker.cancel()

    def cleanup_worker(self, worker, thread):
        self._workers = [(w, t) for w, t in self._workers if w is not worker and t is not thread]
        worker.deleteLater()
        thread.deleteLater()

    def on_processing_finished(self, job_id, result):
        if job_id != self._job_id:
            return
        path = result.get("path")
        frames = result["frames"]
        rendered = result["rendered"]
        if path:
            self.cfg["path"] = path
            self.frames = frames
            if result.get("bg_color") is not None:
                self.cfg["bg_color"] = result["bg_color"]
            h, w = frames[0][0].shape[:2]
            if (w, h) != self.base_size:
                self.cfg["size"] = None   # 다른 비율의 이미지면 직접 입력값은 버린다
            self.base_size = (w, h)
        self.apply_rendered_frames(rendered)
        self.persist()
        self.prompt_image_policy_notice(result.get("metadata"))
        if self.tray:
            self.tray.setToolTip(APP_NAME)
            self.tray.refresh_icon()

    def prompt_image_policy_notice(self, metadata):
        if not self.tray or not metadata:
            return
        lines = []
        dropped = int(metadata.get("dropped_frames") or 0)
        if dropped:
            lines.append(
                "GIF 프레임 %d개 중 %d개만 사용했습니다."
                % (int(metadata.get("source_frame_count") or 0),
                   int(metadata.get("stored_frame_count") or 0)))
        if metadata.get("downsized"):
            lines.append(
                "프레임 크기를 %dx%d에서 %dx%d로 줄였습니다."
                % (metadata["original_size"][0], metadata["original_size"][1],
                   metadata["stored_size"][0], metadata["stored_size"][1]))
        if lines:
            self.tray.showMessage(
                "대형 이미지 자동 최적화",
                "\n".join(lines),
                QtWidgets.QSystemTrayIcon.Information,
                10000)

    def on_processing_failed(self, job_id, path, kind, message):
        if job_id != self._job_id:
            return
        read_error = kind == "read"
        if read_error:
            self.need_image = "missing"
            self.missing_image_path = path
        if self.tray:
            if read_error:
                self.tray.setToolTip("%s - 이미지를 선택하세요" % APP_NAME)
            self.tray.showMessage(
                "이미지를 읽지 못했습니다" if read_error else "이미지 처리에 실패했습니다",
                "%s\n%s" % (path or "(경로 없음)", message),
                QtWidgets.QSystemTrayIcon.Warning, 10000)
        else:
            QtWidgets.QMessageBox.critical(
                None, "오류",
                ("이미지를 읽지 못했습니다." if read_error else "이미지 처리에 실패했습니다.")
                + "\n%s" % message)

    def apply_rendered_frames(self, rendered):
        self.pixmaps = [(to_qpixmap(f), d) for f, d in rendered]
        if hasattr(rendered, "clear"):
            rendered.clear()
        self.index = 0
        self.apply_scale()
        self.show_frame()
        self.timer.stop()
        if len(self.pixmaps) > 1:
            self.timer.start(self.pixmaps[0][1])

    def apply_scale(self):
        # QRect.center() 는 정수로 내림해서 크기를 바꿀 때마다 1px 씩 밀린다.
        # 실수로 중심을 잡아야 반복해서 조절해도 제자리에 머문다.
        old_center = None
        if self.ready and self._sized_once:
            old_center = (self.x() + self.width() / 2.0, self.y() + self.height() / 2.0)
        size = self.cfg.get("size")
        if size:
            w, h = int(size[0]), int(size[1])
        else:
            w = int(self.base_size[0] * self.cfg["scale"])
            h = int(self.base_size[1] * self.cfg["scale"])
        self.resize(max(MIN_SIZE, w), max(MIN_SIZE, h))
        if self.ready:
            self.restore_position(old_center)
        self._sized_once = True
        self.update()

    def set_pixel_size(self, w, h):
        # 너무 작아지면 우클릭조차 못 하게 되므로 하한을 둔다
        self.cfg["size"] = [max(MIN_SIZE, int(w)), max(MIN_SIZE, int(h))]
        self.cfg["scale"] = self.cfg["size"][0] / float(self.base_size[0] or 1)
        self.apply_scale()
        self.persist()

    def ask_size(self):
        dlg = SizeDialog(self.width(), self.height(), self.base_size)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            w, h = dlg.values()
            self.set_pixel_size(w, h)

    def show_frame(self):
        self.update()

    def paintEvent(self, _e):
        if not self.pixmaps:
            return
        p = QtGui.QPainter(self)
        chroma = self.cfg.get("chroma_bg")
        if chroma:
            # OBS/PRISM 윈도우 캡처는 투명 창의 알파를 못 살린다.
            # 단색으로 칠해두고 방송 툴에서 컬러키를 걸면 깔끔하게 빠진다.
            p.fillRect(self.rect(), QtGui.QColor(*chroma))
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, True)
        pm = self.pixmaps[self.index][0]
        if self.cfg["flip"]:
            pm = pm.transformed(QtGui.QTransform().scale(-1, 1))
        p.drawPixmap(self.rect(), pm)
        p.end()

    def next_frame(self):
        if not self.pixmaps:
            return
        self.index = (self.index + 1) % len(self.pixmaps)
        self.show_frame()
        self.timer.start(self.pixmaps[self.index][1])

    # ---- 상호작용
    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
            self._drag_start_global = e.globalPos()
            self._drag_start_window = self.pos()
            self._drag_moved = False
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & QtCore.Qt.LeftButton:
            if self._drag_start_global is not None:
                distance = (e.globalPos() - self._drag_start_global).manhattanLength()
                if distance >= QtWidgets.QApplication.startDragDistance():
                    self._drag_moved = True
            if not self._drag_moved:
                e.accept()
                return
            self.move(e.globalPos() - self._drag)
            e.accept()

    def mouseReleaseEvent(self, e):
        moved = (self._drag_moved
                 and self._drag_start_window is not None
                 and self.pos() != self._drag_start_window)
        if moved:
            # 직접 끌어다 놓았으면 커스텀 위치다. 구석 기억을 버린다
            self.cfg["anchor"] = None
        self._drag = None
        self._drag_start_global = None
        self._drag_start_window = None
        self._drag_moved = False
        self.persist()

    def wheelEvent(self, e):
        step = 1.1 if e.angleDelta().y() > 0 else 1 / 1.1
        self.set_pixel_size(self.width() * step, self.height() * step)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            p = url.toLocalFile()
            if p:
                self.load_image(p)
                self.persist()
                break

    def contextMenuEvent(self, e):
        self.build_menu().exec_(e.globalPos())

    def build_menu(self):
        m = QtWidgets.QMenu(self)
        m.addAction("보이기" if self.hidden else "숨기기", self.toggle_visible)
        m.addSeparator()
        self.add_update_menu(m)
        m.addSeparator()
        m.addAction("이미지 열기…", self.pick_file)
        self.add_startup_menu(m)
        hotkeys_enabled = bool(self.cfg.get("hotkeys_enabled", True))
        m.addAction("단축키 비활성화" if hotkeys_enabled else "단축키 활성화",
                    self.toggle_hotkeys_enabled)
        m.addAction("단축키 설정…", self.open_hotkey_dialog)
        m.addAction("배경 색 다시 잡기", self.reauto_bg)
        m.addAction("배경 색 직접 고르기…", self.pick_bg_color)
        m.addSeparator()

        sub = m.addMenu("배경 제거 강도: %d" % self.cfg["tolerance"])
        for v in (10, 20, 30, 40, 60, 80, 110, 150):
            a = sub.addAction("%d%s" % (v, "  ←" if v == self.cfg["tolerance"] else ""))
            a.triggered.connect(lambda _, v=v: self.set_cfg("tolerance", v))

        sub = m.addMenu("가장자리 부드럽게: %d" % self.cfg["softness"])
        for v in (0, 10, 20, 30, 50, 80):
            a = sub.addAction("%d%s" % (v, "  ←" if v == self.cfg["softness"] else ""))
            a.triggered.connect(lambda _, v=v: self.set_cfg("softness", v))

        sub = m.addMenu("외곽선 민감도: %d" % self.cfg["edge_thresh"])
        for v in (6, 10, 14, 20, 30, 45):
            a = sub.addAction("%d%s" % (v, "  ←" if v == self.cfg["edge_thresh"] else ""))
            a.triggered.connect(lambda _, v=v: self.set_cfg("edge_thresh", v))

        cur = self.cfg.get("chroma_bg")
        sub = m.addMenu("방송 캡처용 배경: %s" % ("없음(투명)" if not cur else str(tuple(cur))))
        for label, col in (("없음 (투명 - 데스크톱용)", None),
                           ("초록 (0,177,64)", [0, 177, 64]),
                           ("자홍 (255,0,255)", [255, 0, 255]),
                           ("파랑 (0,71,187)", [0, 71, 187])):
            a = sub.addAction(label + ("  ←" if (col or None) == (cur or None) else ""))
            a.triggered.connect(lambda _, c=col: self.set_chroma(c))

        sub = m.addMenu("투명도: %d%%" % round(self.cfg.get("opacity", 1.0) * 100))
        for v in (100, 90, 75, 60, 40, 25, 10):
            a = sub.addAction("%d%%%s" % (v, "  ←" if abs(self.cfg.get("opacity", 1.0) - v / 100.0) < 0.01 else ""))
            a.triggered.connect(lambda _, v=v: self.set_opacity(v / 100.0))

        sub = m.addMenu("크기: %d x %d" % (self.width(), self.height()))
        for v in SIZE_PRESETS:
            a = sub.addAction("%d%%" % v)
            a.triggered.connect(lambda _, v=v: self.set_scale(v / 100.0))
        sub.addSeparator()
        sub.addAction("직접 입력…", self.ask_size)
        m.addSeparator()

        for key, text in (("capturable", "윈도우 캡처 목록에 표시 (방송용)"),
                          ("remove_bg", "배경 제거 (끄면 원본 그대로)"),
                          ("edge_only", "외곽선 바깥만 제거 (캐릭터 색 보호)"),
                          ("holes", "둘러싸인 배경도 제거 (선명한 단색 배경만)"),
                          ("despill", "테두리 배경색 물빠짐 제거"),
                          ("flip", "좌우 반전"),
                          ("topmost", "항상 위"),
                          ("click_through", "클릭 통과 (끄면 드래그로 이동 가능)")):
            a = m.addAction(text)
            a.setCheckable(True)
            a.setChecked(bool(self.cfg[key]))
            a.triggered.connect(lambda _, k=key: self.toggle(k))

        m.addSeparator()
        self.add_position_menu(m)
        m.addAction("종료", QtWidgets.QApplication.quit)
        return m

    def open_hotkey_dialog(self):
        dlg = HotkeyDialog(self)
        dlg.exec_()

    def add_update_menu(self, parent):
        if self.update_available and self.latest_release:
            tag = self.latest_release.get("tag") or "새 버전"
            parent.addAction("● 업데이트 있음: %s 열기" % tag, self.open_update_page)
        elif self.update_checking:
            checking = parent.addAction("업데이트 확인 중…")
            checking.setEnabled(False)
        else:
            parent.addAction("업데이트 확인", lambda: self.check_for_updates(silent=False))

        info = "현재 버전: v%s" % APP_VERSION
        if self.latest_release and not self.update_available:
            info += " · 최신"
        version = parent.addAction(info)
        version.setEnabled(False)
        if self.last_update_error and not self.update_available:
            err = parent.addAction("최근 확인 실패")
            err.setEnabled(False)

    def add_startup_menu(self, parent):
        state = startup_state()
        if not state["supported"]:
            action = parent.addAction("윈도우 시작 시 자동 실행")
            action.setCheckable(True)
            action.setChecked(False)
            action.setEnabled(False)
            return
        action = parent.addAction("윈도우 시작 시 자동 실행")
        action.setCheckable(True)
        action.setChecked(bool(state["exists"]))
        action.triggered.connect(lambda checked: self.set_startup_enabled(bool(checked)))
        if state["exists"]:
            parent.addAction("자동 실행 경로 갱신", lambda: self.set_startup_enabled(True))

    def set_startup_enabled(self, enabled):
        try:
            if enabled:
                path = create_startup_shortcut()
                title = "자동 실행 설정"
                body = "윈도우 시작프로그램 폴더에 바로가기를 만들었습니다.\n%s" % path
            else:
                path = remove_startup_shortcut()
                title = "자동 실행 해제"
                body = "윈도우 시작프로그램 폴더의 바로가기를 삭제했습니다.\n%s" % path
            if self.tray:
                self.tray.showMessage(title, body, QtWidgets.QSystemTrayIcon.Information, 8000)
        except Exception as exc:
            if self.tray:
                self.tray.showMessage(
                    "자동 실행 설정 실패",
                    str(exc),
                    QtWidgets.QSystemTrayIcon.Warning,
                    10000)
            else:
                QtWidgets.QMessageBox.warning(None, "자동 실행 설정 실패", str(exc))

    def center_on_screen(self):
        self.snap_to(QtWidgets.QApplication.primaryScreen(), 1, 1)

    def snap_to(self, screen, hx, vy, remember=True):
        """지정한 모니터의 구석으로 옮긴다. hx/vy: 0=시작, 1=가운데, 2=끝.
        작업표시줄을 침범하지 않도록 availableGeometry 를 쓴다."""
        g = screen.availableGeometry()
        m = int(self.cfg.get("snap_margin", 0))
        x = (g.left() + m, g.center().x() - self.width() // 2, g.right() - self.width() + 1 - m)[hx]
        y = (g.top() + m, g.center().y() - self.height() // 2, g.bottom() - self.height() + 1 - m)[vy]
        self.move(int(x), int(y))
        self.raise_()
        if remember:
            # 이미지나 크기가 바뀌어도 같은 구석으로 다시 붙도록 기억해 둔다
            self.cfg["anchor"] = {"screen": screen.name(), "hx": hx, "vy": vy}
        self.persist()

    def anchored_screen(self):
        """기억해 둔 모니터를 찾는다. 분리되었으면 현재 모니터로 대체."""
        a = self.cfg.get("anchor")
        if not a:
            return None
        for sc in QtWidgets.QApplication.screens():
            if sc.name() == a.get("screen"):
                return sc
        return self.screen_of_window()

    def restore_position(self, old_center=None):
        """이미지나 크기가 바뀐 뒤 위치를 되돌린다.

        위치 바로가기로 옮겨 둔 상태면 그 구석으로 다시 붙이고,
        직접 끌어다 놓은 상태면 중심 좌표를 유지한다.

        old_center 는 (x, y) 실수 좌표."""
        a = self.cfg.get("anchor")
        sc = self.anchored_screen()
        if a and sc:
            self.snap_to(sc, a["hx"], a["vy"], remember=False)
            return
        if old_center is None:
            return
        self.move(int(round(old_center[0] - self.width() / 2.0)),
                  int(round(old_center[1] - self.height() / 2.0)))
        self.persist()

    def add_position_menu(self, parent):
        screens = QtWidgets.QApplication.screens()
        primary = QtWidgets.QApplication.primaryScreen()
        here = self.screen_of_window()

        anchor = self.cfg.get("anchor") or {}
        root = parent.addMenu("위치 바로가기")
        for i, sc in enumerate(screens, start=1):
            g = sc.geometry()
            label = "%s 모니터 %d (%dx%d)%s" % (
                "주" if sc == primary else "보조", i, g.width(), g.height(),
                "  ← 현재" if sc == here else "")
            sub = root.addMenu(label)
            for text, hx, vy, _code in SNAP_SPOTS:
                fixed = (anchor.get("screen") == sc.name()
                         and anchor.get("hx") == hx and anchor.get("vy") == vy)
                a = sub.addAction(text + ("  ← 고정됨" if fixed else ""))
                a.triggered.connect(lambda _, s=sc, h=hx, v=vy: self.snap_to(s, h, v))

        root.addSeparator()
        if anchor:
            root.addAction("구석 고정 해제 (지금 위치 유지)", self.clear_anchor)
        mm = root.addMenu("구석 여백: %dpx" % self.cfg.get("snap_margin", 0))
        for v in (0, 10, 20, 40, 80):
            a = mm.addAction("%dpx%s" % (v, "  ←" if v == self.cfg.get("snap_margin", 0) else ""))
            a.triggered.connect(lambda _, v=v: self.set_margin(v))

    def clear_anchor(self):
        self.cfg["anchor"] = None
        self.persist()

    def set_margin(self, v):
        self.cfg["snap_margin"] = v
        if self.cfg.get("anchor"):
            self.restore_position()
            return
        self.persist()

    def screen_of_window(self):
        c = self.frameGeometry().center()
        return QtWidgets.QApplication.screenAt(c) or QtWidgets.QApplication.primaryScreen()

    def set_cfg(self, key, value):
        self.cfg[key] = value
        self.rebuild()
        self.persist()

    def set_chroma(self, color):
        self.cfg["chroma_bg"] = color
        self.update()
        self.persist()

    def set_scale(self, s):
        self.cfg["scale"] = s
        self.cfg["size"] = None      # 배율 프리셋을 고르면 직접 입력값은 해제
        self.apply_scale()
        self.persist()

    def cycle_scale(self):
        current = int(round(float(self.cfg.get("scale", 1.0)) * 100))
        for value in SIZE_PRESETS:
            if value > current:
                self.set_scale(value / 100.0)
                return
        self.set_scale(SIZE_PRESETS[0] / 100.0)

    def toggle(self, key):
        self.cfg[key] = not self.cfg[key]
        if key in ("topmost", "click_through", "capturable"):
            self.apply_window_flags()
        elif key in ("despill", "edge_only", "holes", "remove_bg"):
            self.rebuild()
        else:
            self.show_frame()
        self.persist()

    def reauto_bg(self):
        if self.frames:
            self.cfg["bg_color"] = detect_bg_color(self.frames[0][0]).tolist()
            self.rebuild()
            self.persist()

    def pick_bg_color(self):
        c = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(*[int(v) for v in self.cfg["bg_color"]]), None, "지울 배경 색")
        if c.isValid():
            self.cfg["bg_color"] = [c.red(), c.green(), c.blue()]
            self.cfg["auto_bg"] = False
            self.rebuild()
            self.persist()

    def persist(self, immediate=False):
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        if immediate:
            self.flush_persist()
            return
        self._persist_timer.start(500)

    def flush_persist(self):
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        save_config(self.cfg)
        self.prompt_config_notices()

    def shutdown(self):
        self.unregister_hotkeys()
        self.flush_persist()
        self.cancel_processing_workers()
        for _worker, thread in list(self._workers):
            thread.quit()
            thread.wait(2000)
        for _worker, thread in list(self._update_workers):
            thread.quit()
            thread.wait((UPDATE_CHECK_TIMEOUT_SEC + 2) * 1000)

    def hotkey_target_screen(self):
        wanted = self.cfg.get("hotkey_screen") or ""
        for screen in QtWidgets.QApplication.screens():
            if screen.name() == wanted:
                return screen
        return QtWidgets.QApplication.primaryScreen()

    def execute_hotkey(self, command):
        if command == "toggle_visible":
            self.toggle_visible()
        elif command == "show":
            self.set_visible_state(True)
        elif command == "hide":
            self.set_visible_state(False)
        elif command == "open_image":
            self.pick_file()
        elif command in ("flip", "topmost", "click_through"):
            self.toggle(command)
        elif command == "disable_hotkeys":
            self.set_hotkeys_enabled(False, notify=True)
        elif command == "scale_cycle":
            self.cycle_scale()
        elif command in HOTKEY_SIZE_COMMANDS:
            self.set_scale(HOTKEY_SIZE_COMMANDS[command] / 100.0)
        elif command in HOTKEY_SNAP_COMMANDS:
            _label, hx, vy = HOTKEY_SNAP_COMMANDS[command]
            screen = self.hotkey_target_screen()
            if screen:
                self.snap_to(screen, hx, vy)

    def register_hotkeys(self, show_errors=False):
        self.hotkey_manager.unregister_all()
        if not self.cfg.get("hotkeys_enabled", True):
            return []
        errors = self.hotkey_manager.register_all(self.cfg.get("hotkeys", {}))
        if errors and show_errors:
            message = "\n".join(errors[:6])
            if len(errors) > 6:
                message += "\n외 %d개" % (len(errors) - 6)
            if self.tray:
                self.tray.showMessage("단축키 등록 실패", message, QtWidgets.QSystemTrayIcon.Warning, 10000)
            else:
                QtWidgets.QMessageBox.warning(None, "단축키 등록 실패", message)
        return errors

    def unregister_hotkeys(self):
        self.hotkey_manager.unregister_all()

    def set_hotkeys_enabled(self, enabled, notify=False):
        self.cfg["hotkeys_enabled"] = bool(enabled)
        if enabled:
            errors = self.register_hotkeys(show_errors=True)
            if notify and self.tray and not errors:
                self.tray.showMessage(
                    "단축키 활성화",
                    "등록된 전역 단축키를 다시 활성화했습니다.",
                    QtWidgets.QSystemTrayIcon.Information,
                    5000)
        else:
            self.unregister_hotkeys()
            if notify and self.tray:
                self.tray.showMessage(
                    "단축키 비활성화",
                    "전역 단축키를 모두 비활성화했습니다.\n다시 사용하려면 트레이 메뉴에서 단축키 활성화를 선택하세요.",
                    QtWidgets.QSystemTrayIcon.Warning,
                    10000)
        self.persist()

    def toggle_hotkeys_enabled(self):
        self.set_hotkeys_enabled(not bool(self.cfg.get("hotkeys_enabled", True)), notify=True)


class Tray(QtWidgets.QSystemTrayIcon):
    """작업표시줄 트레이 아이콘 - 창이 클릭 통과 상태여도 여기서 전부 조작 가능."""

    def __init__(self, pet):
        super().__init__()
        self.pet = pet
        self.setToolTip(APP_NAME)
        self.refresh_icon()
        self.activated.connect(self.on_activated)
        self.show()

    def refresh_icon(self):
        if self.pet.pixmaps:
            base = QtGui.QIcon(self.pet.pixmaps[0][0])
        else:
            base = self.pet.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        if self.pet.update_available:
            self.setIcon(self.with_update_badge(base))
        else:
            self.setIcon(base)

    def with_update_badge(self, icon):
        size = 64
        base = icon.pixmap(size, size)
        canvas = QtGui.QPixmap(size, size)
        canvas.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(canvas)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        x = (size - base.width()) // 2
        y = (size - base.height()) // 2
        painter.drawPixmap(x, y, base)

        diameter = 18
        margin = 4
        rect = QtCore.QRect(size - diameter - margin, margin, diameter, diameter)
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 3))
        painter.setBrush(QtGui.QBrush(QtGui.QColor(230, 40, 45)))
        painter.drawEllipse(rect)
        painter.end()
        return QtGui.QIcon(canvas)

    def on_activated(self, reason):
        self.show_menu()

    def show_menu(self):
        menu = self.pet.build_menu()
        menu.exec_(QtGui.QCursor.pos())


def main():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    cfg = load_config()
    if len(sys.argv) > 1:
        if os.path.exists(sys.argv[1]):
            cfg["path"] = sys.argv[1]
        else:
            cfg["_startup_missing_path"] = sys.argv[1]

    pet = Pet(cfg)                 # 참조를 유지해야 창이 사라지지 않는다
    tray = Tray(pet)
    pet.tray = tray
    tray.refresh_icon()
    pet.register_hotkeys(show_errors=True)
    pet.prompt_config_notices()
    pet.prompt_if_no_image()
    pet.schedule_update_check()
    app.aboutToQuit.connect(pet.shutdown)
    app.pet, app.tray = pet, tray  # 가비지 컬렉션 방지
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
