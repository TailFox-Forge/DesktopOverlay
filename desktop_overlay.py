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
import sys

import numpy as np
from PIL import Image, ImageSequence
from PyQt5 import QtCore, QtGui, QtWidgets

APP_NAME = "DesktopOverlay"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
IMAGE_FILTER = "이미지 (*.gif *.png *.jpg *.jpeg *.webp *.bmp);;모든 파일 (*.*)"
MIN_SIZE = 48      # 이보다 작아지면 우클릭 메뉴조차 열기 어려워진다
MAX_SIZE = 4000

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
    "chroma_bg": None,       # [r,g,b] 이면 창을 그 색으로 채운다 (윈도우 캡처 + 컬러키용)
    "click_through": True,   # 기본: 마우스 통과 (게임 조작 방해 없음)
    "flip": False,
    "topmost": True,         # 기본: 항상 위
}


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- 이미지 처리

def read_frames(path):
    """어떤 이미지든 (RGBA numpy 배열, 지속시간ms) 목록으로 읽는다."""
    im = Image.open(path)
    frames = []
    if getattr(im, "is_animated", False):
        last = None
        for frame in ImageSequence.Iterator(im):
            cur = frame.convert("RGBA")
            if last is not None and frame.tile:
                # 부분 갱신 프레임이면 이전 프레임 위에 합성
                merged = last.copy()
                merged.alpha_composite(cur)
                cur = merged
            last = cur
            delay = frame.info.get("duration", 100) or 100
            frames.append((np.array(cur), max(20, int(delay))))
    else:
        frames.append((np.array(im.convert("RGBA")), 100))
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
    스캔라인 방식 flood fill - 한 줄씩 통째로 처리해서 파이썬 반복을 줄인다."""
    h, w = passable.shape
    filled = np.zeros((h, w), dtype=bool)

    stack = []
    for x in range(w):
        if passable[0, x]:
            stack.append((0, x))
        if passable[h - 1, x]:
            stack.append((h - 1, x))
    for y in range(h):
        if passable[y, 0]:
            stack.append((y, 0))
        if passable[y, w - 1]:
            stack.append((y, w - 1))

    row_pass = passable
    while stack:
        y, x = stack.pop()
        if filled[y, x] or not row_pass[y, x]:
            continue
        # 이 줄에서 좌우로 갈 수 있는 데까지 넓힌다
        left = x
        while left > 0 and row_pass[y, left - 1] and not filled[y, left - 1]:
            left -= 1
        right = x
        while right < w - 1 and row_pass[y, right + 1] and not filled[y, right + 1]:
            right += 1
        filled[y, left:right + 1] = True

        # 위아래 줄에서 새로 열린 구간의 시작점만 스택에 넣는다
        for ny in (y - 1, y + 1):
            if 0 <= ny < h:
                seg = row_pass[ny, left:right + 1] & ~filled[ny, left:right + 1]
                if seg.any():
                    starts = np.flatnonzero(seg & ~np.concatenate(([False], seg[:-1])))
                    for s in starts:
                        stack.append((ny, left + int(s)))
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


class Pet(QtWidgets.QWidget):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.frames = []        # (rgba, delay)
        self.pixmaps = []
        self.index = 0
        self.base_size = (200, 200)
        self._drag = None
        self.tray = None

        self.setWindowTitle(APP_NAME)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.apply_window_flags()

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.next_frame)

        self.move(cfg["x"], cfg["y"])
        if cfg["path"] and os.path.exists(cfg["path"]):
            self.load_image(cfg["path"])
        else:
            self.pick_file()

    # ---- 창 속성
    def apply_window_flags(self):
        flags = QtCore.Qt.FramelessWindowHint | QtCore.Qt.Tool
        if self.cfg["topmost"]:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        self.raise_()

    def nativeEvent(self, event_type, message):
        """클릭 통과: WM_NCHITTEST 에 HTTRANSPARENT 를 돌려주면 마우스가 아래 창으로 넘어간다.
        WS_EX_TRANSPARENT 와 달리 창 렌더링에는 영향이 없다."""
        if self.cfg.get("click_through") and event_type == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST:
                return True, HTTRANSPARENT
        return super().nativeEvent(event_type, message)

    # ---- 로딩 / 처리
    def pick_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            None, "띄울 이미지 선택", self.cfg["path"] or os.path.expanduser("~"), IMAGE_FILTER)
        if path:
            self.cfg["path"] = path
            self.load_image(path)
        elif not self.frames:
            QtWidgets.QApplication.quit()

    def load_image(self, path):
        try:
            self.frames = read_frames(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "오류", "이미지를 읽지 못했습니다.\n%s" % e)
            return
        self.cfg["path"] = path
        if self.cfg["auto_bg"]:
            self.cfg["bg_color"] = detect_bg_color(self.frames[0][0]).tolist()
        h, w = self.frames[0][0].shape[:2]
        if (w, h) != self.base_size:
            self.cfg["size"] = None   # 다른 비율의 이미지면 직접 입력값은 버린다
        self.base_size = (w, h)
        self.rebuild()

    def rebuild(self):
        if not self.cfg["remove_bg"]:
            self.pixmaps = [(to_qpixmap(f), d) for f, d in self.frames]
        else:
            bg = np.array(self.cfg["bg_color"], dtype=np.float32)
            self.pixmaps = [
                (to_qpixmap(key_out(f, bg, self.cfg["tolerance"], self.cfg["softness"],
                                    self.cfg["despill"], self.cfg["edge_only"],
                                    self.cfg["edge_thresh"], self.cfg["holes"])), d)
                for f, d in self.frames
            ]
        self.index = 0
        self.apply_scale()
        self.show_frame()
        if self.tray:
            self.tray.refresh_icon()
        self.timer.stop()
        if len(self.pixmaps) > 1:
            self.timer.start(self.pixmaps[0][1])

    def apply_scale(self):
        size = self.cfg.get("size")
        if size:
            w, h = int(size[0]), int(size[1])
        else:
            w = int(self.base_size[0] * self.cfg["scale"])
            h = int(self.base_size[1] * self.cfg["scale"])
        self.resize(max(MIN_SIZE, w), max(MIN_SIZE, h))
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
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() & QtCore.Qt.LeftButton:
            self.move(e.globalPos() - self._drag)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag = None
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
        m.addAction("이미지 열기…", self.pick_file)
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

        sub = m.addMenu("크기: %d x %d" % (self.width(), self.height()))
        for v in (25, 50, 75, 100, 150, 200, 300):
            a = sub.addAction("%d%%" % v)
            a.triggered.connect(lambda _, v=v: self.set_scale(v / 100.0))
        sub.addSeparator()
        sub.addAction("직접 입력…", self.ask_size)
        m.addSeparator()

        for key, text in (("remove_bg", "배경 제거 (끄면 원본 그대로)"),
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
        m.addAction("화면 가운데로 되돌리기", self.center_on_screen)
        m.addAction("종료", QtWidgets.QApplication.quit)
        return m

    def center_on_screen(self):
        g = QtWidgets.QApplication.primaryScreen().availableGeometry()
        self.move(g.center().x() - self.width() // 2, g.center().y() - self.height() // 2)
        self.raise_()
        self.persist()

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

    def toggle(self, key):
        self.cfg[key] = not self.cfg[key]
        if key in ("topmost", "click_through"):
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

    def persist(self):
        self.cfg["x"], self.cfg["y"] = self.x(), self.y()
        save_config(self.cfg)


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
            self.setIcon(QtGui.QIcon(self.pet.pixmaps[0][0]))
        else:
            self.setIcon(self.pet.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))

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
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        cfg["path"] = sys.argv[1]

    pet = Pet(cfg)                 # 참조를 유지해야 창이 사라지지 않는다
    tray = Tray(pet)
    pet.tray = tray
    tray.refresh_icon()
    app.pet, app.tray = pet, tray  # 가비지 컬렉션 방지
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
