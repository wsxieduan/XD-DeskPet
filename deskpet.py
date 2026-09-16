#!/usr/bin/env python3
"""deskpet.py —— 贴在 Windows 桌面上的桌宠

显示层级两种模式（右键菜单或控制台可切）：
  wallpaper  贴壁纸层：SetParent 到桌面的 WorkerW，被任何窗口盖住就看不见，
             只在露出壁纸时可见（你要的效果）
  topmost    始终置顶，浮在所有窗口上面

交互：拖拽换位置（位置记住） / 点击有反馈（动画 + 台词 + 轻响） / 右键菜单
"""
from __future__ import annotations

import ctypes
import json
import math
import random
import struct
import sys
import time
import traceback
import wave
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QFontMetrics, QLinearGradient,
                           QPainter, QPainterPath, QPixmap)
from PySide6.QtWidgets import QApplication, QMenu, QWidget

try:
    import winsound
except ImportError:
    winsound = None

import paths
import petlist

BASE = Path(__file__).resolve().parent          # 源码目录（只用于同目录模块导入）
APP_DIR = paths.APP                             # 程序目录（只读）
DATA_DIR = paths.DATA                           # 数据目录（可写，%APPDATA%\DeskPet）
ASSETS = APP_DIR / "assets"                     # 兼容旧引用；实际查找走 find_asset
CONFIG = paths.config_path()
PIDFILE = paths.pid_path()
BONDFILE = paths.data_root() / "bond.json"
paths.setup_model_env()

SCALE_STEPS = [("小", 0.7), ("中", 1.0), ("大", 1.4)]     # 快捷键式的三档预设
SCALE_MIN, SCALE_MAX = 0.4, 3.0        # 自由缩放的范围：再小看不清、再大糊满屏
ZOOM_STEP = 1.06                       # Ctrl+滚轮滚一格（120）的倍率
ZOOM_DEBOUNCE_MS = 250                 # 缩放停稳多久后做一次真正的重采样
HANDLE_SHOW_MS = 5000                  # 「调整大小」手柄显示多久
HANDLE_SIZE = 18                       # 手柄边长（逻辑像素）

# 互动音效的四类触发点（阿酉《需求卡-音效与联系人》功能一）。
# 每一类可以绑多个音效，触发时随机播一个 —— 和台词池同一个思路。
# 配置写在 config.json：{"sounds": {"click": ["sounds/pop.wav"], ...}}，
# 路径用 paths.find_asset 解析（用户上传的放数据目录 assets/sounds/，同名优先）。
SFX_EVENTS = ("click", "grab", "land", "spawn")
SFX_LABELS = {"click": "点击", "grab": "抓起", "land": "落地", "spawn": "出现"}
SFX_FALLBACK = "sounds/boop.wav"

# 桌宠之间"一起玩"的共享计划（阿酉需求卡功能二的简化版）：
# 控制台或任一只桌宠写一份计划文件，被绑定的两只各自按时间算自己该在圆周的哪个相位。
# 为什么用文件而不是两只互相喊话：谁负责算圆心、谁先开口都容易打架；
# 一份计划 + 各自算相位，天然同步、也不会死锁（阿酉说的"单一调度器"的最小实现）。
BOND_RADIUS = 110          # 一起转圈的半径（逻辑像素）
BOND_SECONDS = 20.0        # 转多久
BOND_SPEED = 0.8           # 角速度（弧度/秒），约 2.5 圈
BOND_TICK_MS = 120         # 每只多久看一眼计划
# 转速预设（弧度/秒）：0.45 约 7 秒一圈，2.6 约 2.4 秒一圈 —— 后者就是主人说的"魔性"
BOND_SPEEDS = [("慢", 0.45), ("中", 0.8), ("快", 1.5), ("魔性", 2.6)]
SPIN_PAD = 1.45            # 整只跟着翻转时，绘制区要放大到外接正方形，不然四个角会被裁掉
BUBBLE_FONT_PX = 13
BUBBLE_TAIL = 7
BUBBLE_PAD_X, BUBBLE_PAD_Y = 12, 7
BUBBLE_MS = 2200
MAX_BUBBLE_W_RATIO = 0.42      # 气泡最宽占屏幕宽度的比例，超出就折行
MAX_BUBBLE_LINES = 4           # 最多几行，再多就截断加省略号

TRACK_MS = {
    "idle": 190,
    "waving": 110,
    "jumping": 95,
    "running": 90,
    "running-left": 80,
    "running-right": 80,
    "waiting": 170,
    "review": 150,
    "failed": 150,
}
REACT_PREFER = ["waving", "jumping", "review", "failed"]

LINES = [
    "呀——被摸头了～",
    "再摸一下也不是不行",
    "唔，痒痒的",
    "今天也要加油哦！",
    "我一直在这儿呢",
    "你忙你的，我看着",
    "这一下，记在小本本上了",
    "摸摸可以，小鱼干更好",
    "我在听呢，你说",
    "呼——差点没站稳",
]

# ------------------------------------------------------------------ 桌面层
user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW, SWP_FRAMECHANGED = 0x1, 0x2, 0x10, 0x40, 0x20
HWND_BOTTOM = 1
WM_SPAWN_WORKER = 0x052C
_DESKTOP_HOST = None      # 缓存的桌面宿主窗口，避免每次重申 z 序都全量枚举
GWL_EXSTYLE, WS_EX_NOACTIVATE = -20, 0x08000000
WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = 0x00000080, 0x00040000

# 64 位下必须声明 argtypes/restype，否则 HWND 会被 ctypes 当成 32 位 int 截断，
# SetParent 会静默失败（踩过一次）。
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                       wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                       ctypes.POINTER(wintypes.DWORD)]
user32.SendMessageTimeoutW.restype = wintypes.LPARAM
user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
user32.SetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindow.restype = wintypes.BOOL
user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
user32.SetWindowLongW.restype = wintypes.LONG


def find_desktop_host():
    """找到桌面的壁纸层窗口：优先 WorkerW，退回 Progman。"""
    progman = user32.FindWindowW("Progman", None)
    res = wintypes.DWORD()
    if progman:
        for wparam, lparam in ((0x0D, 0x01), (0x00, 0x00)):
            user32.SendMessageTimeoutW(progman, WM_SPAWN_WORKER, wparam, lparam,
                                        0x0000, 1000, ctypes.byref(res))
    hits = []

    def cb(hwnd, _lparam):
        if user32.FindWindowExW(hwnd, 0, "SHELLDLL_DefView", None):
            w = user32.FindWindowExW(0, hwnd, "WorkerW", None)
            if w:
                hits.append(w)
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return hits[0] if hits else progman


def window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def push_to_bottom(hwnd: int) -> None:
    """"贴在壁纸上"的实现：把它插到 Progman（桌面窗口）的正上方。

    z 序上就是：桌面 < 她 < 其他所有窗口。于是露出壁纸时看得见她，
    任何普通窗口都能盖住她；同时她又比桌面图标层高，鼠标点击点得到她。

    两个坑：
      1) 网上常见的做法是 SetParent 到 Progman/WorkerW。实测本机 Windows 11
         build 26200 上这条路已废：挂进去后 IsWindowVisible 为真，但一个像素都不合成。
      2) 用 HWND_BOTTOM 压到最底也不行 —— 那样她会落到桌面图标层(SysListView32)
         下面，看得见但**点不到**（WindowFromPoint 返回 SysListView32）。
         必须插在 Progman 之后，而不是最底。"""
    global _DESKTOP_HOST
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
    # host 缓存起来：find_desktop_host() 要枚举所有顶层窗口 + 向 Progman 广播两次，
    # 每 500ms 做一遍太浪费（阿酉 review N3）。失效了才重新找。
    if _DESKTOP_HOST and not user32.IsWindow(_DESKTOP_HOST):
        _DESKTOP_HOST = None
    if not _DESKTOP_HOST:
        _DESKTOP_HOST = find_desktop_host()
    after = _DESKTOP_HOST if _DESKTOP_HOST else HWND_BOTTOM
    user32.SetWindowPos(hwnd, after, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


# ------------------------------------------------------------------ 素材
def load_frames(character: str) -> dict[str, list[QPixmap]]:
    # 素材可能在内置目录，也可能在用户数据目录，find_asset 按 DATA 优先查
    manifest_file = paths.find_asset(character + "/_frames.json")
    root = manifest_file.parent if manifest_file else (ASSETS / character)
    if manifest_file is None or not manifest_file.exists():
        raise SystemExit("找不到素材清单：" + character + "/_frames.json")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    tracks = {}
    per_ms = {}
    for t, val in manifest.items():
        # 两种格式都支持：["a.png", ...] 或 {"files": [...], "ms": [...]}
        if isinstance(val, dict):
            names = val.get("files") or []
            if val.get("ms"):
                per_ms[t] = list(val["ms"])
        else:
            names = val or []
        if names:
            tracks[t] = [QPixmap(str(root / n)) for n in names]
    if "idle" not in tracks:
        raise SystemExit("素材损坏：这个形象缺少 idle 轨道（" + str(manifest_file) + "）")
    return tracks, per_ms


def list_characters() -> list[tuple[str, str]]:
    """扫描 assets 下所有带 _frames.json 的目录。"""
    out = []
    for mf in sorted(ASSETS.glob("**/_frames.json")):
        rel = mf.parent.relative_to(ASSETS).as_posix()
        out.append((rel, rel))
    return out


def make_boop(path: Path) -> None:
    if path.exists():
        return
    rate, ms = 22050, 120
    n = rate * ms // 1000
    data = bytearray()
    for i in range(n):
        t = i / rate
        freq = 900 + 700 * (t / (ms / 1000))
        env = min(1.0, i / 200) * max(0.0, 1 - i / n) ** 1.6
        data += struct.pack("<h", int(12000 * env * math.sin(2 * math.pi * freq * t)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(bytes(data))



# ------------------------------------------------------------------ 行为系统
# 参考 Petra 的行为设计（漫游 / 躲避鼠标 / 拖拽惯性 / 拖文件回收），
# 这些都是纯逻辑，跟渲染技术无关，但对"她还活着"的手感影响最大。

ROAM_MIN_MS, ROAM_MAX_MS = 9000, 26000      # 两次漫游之间的间隔范围
ROAM_SPEED = 2.2                            # 每步像素（30ms 一步 ≈ 73px/s）
ROAM_STEP_MS = 30
FLEE_DIST = 130                             # 光标进入这个距离就躲
FLEE_DISTANCE = 210                         # 一躲躲多远
INERTIA_FRICTION = 0.88                     # 拖拽惯性每帧衰减
INERTIA_GAIN = 0.014                        # 速度→初速的换算（调这个控制"滑多远"）
# 手感标定：快速拖动约 1100px/s 时，滑行总距离 ≈ v0/(1-f) = 1100*0.014/0.12 ≈ 128px。
# 第一版用了 0.05/0.90，滑了 453px 直接飞到屏幕另一头，太重了。


def recycle_paths(paths: list[str]) -> bool:
    """把文件丢进回收站（不是直接删）。用 SHFileOperation，无第三方依赖。"""
    if not paths:
        return False
    try:
        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND),
                        ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR),
                        ("pTo", wintypes.LPCWSTR),
                        ("fFlags", wintypes.WORD),
                        ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p),
                        ("lpszProgressTitle", wintypes.LPCWSTR)]
        FO_DELETE = 3
        FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT = 0x0040, 0x0010, 0x0004
        buf = "\0".join(paths) + "\0\0"
        op = SHFILEOPSTRUCTW(None, FO_DELETE, buf, None,
                             FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT,
                             False, None, None)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
        shell32.SHFileOperationW.restype = ctypes.c_int
        return shell32.SHFileOperationW(ctypes.byref(op)) == 0
    except Exception as e:
        print("丢回收站失败:", e, flush=True)
        return False


# ------------------------------------------------------------------ 桌宠
class DeskPet(QWidget):
    def __init__(self, pet_id: str | None = None) -> None:
        super().__init__()
        self.cfg = self.load_cfg()
        # 全局设置（行为/台词/对话配色/层级/音量）来自 config.json，所有桌宠共享；
        # 形象/位置/大小是"这一只"的，来自 pets.json 的条目。
        # pet_id=None 表示单宠物模式（开发态和旧行为，保持兼容）。
        self.pet_id = pet_id
        if pet_id:
            petlist.ensure_first()
            entry = petlist.get_pet(pet_id) or {}
        else:
            entry = {}
        self._entry = entry
        self.mode = self.cfg.get("mode", "desktop")
        self.sound_on = bool(self.cfg.get("sound", True))
        self.character = (entry.get("character") or self.cfg.get("character")
                          or paths.DEFAULT_CHARACTER)
        # 大小：这一只的 > 全局的 > 形象自己的默认值（内置形象帧小，需要放大一点）
        # 夹到合法区间：自由缩放存的是任意浮点，手改过配置文件也不能让她缩没或糊满屏
        self.scale = max(SCALE_MIN, min(SCALE_MAX, float(
            entry.get("scale") or self.cfg.get("scale")
            or petlist.CHAR_SCALE.get(self.character, 1.0))))
        # 自由缩放（阿酉需求卡）：交互期间只改尺寸不重采样，停稳 250ms 再真正重采样
        self._fast = False                 # True = 当前画面上是 painter 缩放，还没重采样
        self._zoom_timer = QTimer(self)
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.timeout.connect(self._zoom_settle)
        self._handle_until = 0.0           # 手柄显示到这个时刻（time.monotonic）
        self._handle_timer = QTimer(self)
        self._handle_timer.setSingleShot(True)
        self._handle_timer.timeout.connect(self.update)
        self._resizing = False
        self._resize_start = None
        self._zoom_hint = None             # 上一次显示的百分比，避免每移动一像素就重排气泡

        try:
            self.raw, self.frame_ms = load_frames(self.character)
        except SystemExit as e:
            # 形象素材不在了（用户删过、或者换了台机器只把 config 搬过来了）：
            # 回落到内置形象，而不是直接起不来 —— 用户该看到的是"变成默认形象了"，
            # 不是"桌宠启动失败"。控制台那边同理，选不中的形象会退回列表第一项。
            if self.character == paths.DEFAULT_CHARACTER:
                raise
            print("形象素材缺失（%s），回落到内置形象：%s" % (self.character, e), flush=True)
            self.character = paths.DEFAULT_CHARACTER
            self.raw, self.frame_ms = load_frames(self.character)
        self.frames: dict[str, list[QPixmap]] = {}
        # 音效是生成出来的，写到可写的数据目录
        self.boop = paths.asset_root_for_write() / "boop.wav"
        if self.sound_on:
            make_boop(self.boop)

        self.setWindowTitle("桌宠")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        # 刻意不用 Qt.Tool：那会让 Qt 额外建一个隐藏的 QWindowToolSaveBits 辅助窗口，
        # 导致 winId() 拿到的不是真正可见的那个窗口，SetParent 会挂错对象。
        # 不占任务栏改由 WS_EX_TOOLWINDOW 实现（见 apply_layer）。
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.mode == "topmost")

        react = [t for t in REACT_PREFER if t in self.raw]
        self.react_tracks = react or ["idle"]

        self.bubble_text: str | None = None
        self.bubble_image: str | None = None
        self.track = "idle"
        self.index = 0
        self.once_then: str | None = None
        self._press: QPoint | None = None
        self._win_at_press = QPoint()
        self._dragging = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.hide_bubble)

        bh = self.cfg.get("behavior") or {}
        self.beh_roam = bool(bh.get("roam", True))
        self.beh_flee = bool(bh.get("flee", True))
        self.beh_inertia = bool(bh.get("inertia", True))
        self.beh_recycle = bool(bh.get("recycle", True))

        self.theme_color = self._extract_theme()
        self.bub_bg, self.bub_fg, self.bub_border = self._bubble_palette()
        self._load_bubbles()
        self._load_sounds()
        self.apply_scale()
        self.play("idle")
        self.restore_pos()
        self.write_pid()
        self._init_behavior()

    # -------------------------------------------------------------- 配置
    def load_cfg(self) -> dict:
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_cfg(self) -> None:
        """只把自己负责的字段写回去，其余键以磁盘上的最新值为准。

        为什么不能整份覆盖：桌宠在漫游、拖拽、惯性停下时都会调用这里，
        而它手里只有**启动那一刻**的配置快照。整份写回去的话，控制台刚改的
        「行为开关 / 台词 / 对话配色」会被这份旧快照覆盖掉 ——
        用户看到的现象就是"关了过一会自己又勾上了"（经典的 lost update）。
        原子写只解决"读到半截文件"，解决不了"用旧值覆盖新值"，两件事都要做。"""
        if self.pet_id:
            # 多实例：只有"位置/大小/形象"是这一只的，写进它自己的条目；
            # 全局设置一律不碰，免得覆盖控制台刚改的东西。
            try:
                petlist.update_pet(self.pet_id, character=self.character,
                                   x=self.x(), y=self.y(), scale=self.scale)
            except Exception:
                pass
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = dict(self.cfg)
        if self.pet_id:
            data.pop("x", None)
            data.pop("y", None)
        data.update({"scale": self.scale, "mode": self.mode,
                     "character": self.character, "sound": self.sound_on,
                     "x": self.x(), "y": self.y(),
                     # 把实际推导出来的对话框颜色写回去，控制台拿它做预览，保证所见即所得
                     "bubble_resolved": {
                         "bg": [self.bub_bg.red(), self.bub_bg.green(), self.bub_bg.blue()],
                         "fg": [self.bub_fg.red(), self.bub_fg.green(), self.bub_fg.blue()],
                         "border": [self.bub_border.red(), self.bub_border.green(),
                                    self.bub_border.blue()],
                         "theme": [self.theme_color.red(), self.theme_color.green(),
                                   self.theme_color.blue()],
                     }})
        try:
            paths.atomic_write_text(CONFIG, json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def write_pid(self) -> None:
        """记下自己的 pid。

        **多实例绝不写 pet.pid**：pet.pid 是"单宠物模式那一只"的标志，
        控制台的 apply() 靠它决定要不要重启单宠物那只。多实例也往里写的话，
        控制台会把"某只实例在跑"误判成"单宠物那只在跑"，于是改任一设置都会
        额外拉起一只 —— 用户看到的就是"点一下开关，桌面上又多冒出一只桌宠"（踩过）。"""
        pid = ctypes.windll.kernel32.GetCurrentProcessId()
        try:
            if self.pet_id:
                petlist.update_pet(self.pet_id, pid=int(pid))
            else:
                # 连创建时刻一起记：pid 会被系统复用，光记 pid 有可能误杀别的进程
                PIDFILE.write_text("%d %d" % (pid, _proc_creation()), encoding="utf-8")
        except Exception:
            pass

    # -------------------------------------------------------------- 音效
    def _load_sounds(self) -> None:
        """把 config 里绑定的音效解析成真实路径；空的/找不到的回落内置 boop。

        每次现读磁盘（不用 self.cfg 那份启动快照）：控制台改完绑定是写文件 + 重启桌宠，
        但"重启"这一步万一没走到（比如手动改配置文件），现读能立刻生效，不会用旧绑定。"""
        conf = self.load_cfg().get("sounds") or {}
        self.sfx: dict = {}
        for ev in SFX_EVENTS:
            found = []
            for rel in (conf.get(ev) or []):
                p = paths.find_asset(str(rel))
                if p is not None and p.exists():
                    found.append(p)
            if not found:
                p = paths.find_asset(SFX_FALLBACK)
                if p is not None and p.exists():
                    found.append(p)
            self.sfx[ev] = found

    def play_sfx(self, event: str) -> None:
        """播一个互动音效。没开音效 / 没绑 / 文件没了都静默跳过 ——
        音效是锦上添花，绝不能因为它让桌宠出问题。"""
        if not self.sound_on or winsound is None:
            return
        pool = self.sfx.get(event) or []
        if not pool:
            return
        pick = random.choice(pool)
        # 打一行日志：日志是唯一能"从外面验证到底播了哪个"的手段
        print("音效(%s): %s" % (event, pick.name), flush=True)
        try:
            winsound.PlaySound(str(pick),
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception as e:
            print("音效播放失败:", e, flush=True)

    # -------------------------------------------------------------- 台词
    def _load_bubbles(self) -> None:
        """点击时冒出来的东西：文字或图片，从 config.json 的 bubbles 读。
        没配过就用内置台词。每个条目 {"type":"text","text":...} 或 {"type":"image","file":...}"""
        self.bubble_items = []
        self.bubble_pixmaps = {}
        for it in (self.cfg.get("bubbles") or []):
            if not isinstance(it, dict):
                continue
            if it.get("type") == "image":
                rel = it.get("file") or ""
                found = paths.find_asset(rel)
                pm = QPixmap(str(found)) if found else QPixmap()
                if pm.isNull():
                    continue
                self.bubble_pixmaps[rel] = pm
                self.bubble_items.append(("image", rel))
            elif it.get("type") == "text" and str(it.get("text", "")).strip():
                self.bubble_items.append(("text", str(it["text"]).strip()))
        if not self.bubble_items:
            self.bubble_items = [("text", t) for t in LINES]

    def _pick_bubble(self):
        return random.choice(self.bubble_items)

    # -------------------------------------------------------------- 配色
    def _extract_theme(self) -> QColor:
        """从待机图的像素里挑出角色的主色调：按色相分桶，取占比最高那一桶的平均色。
        只统计"够鲜艳、够亮"的像素，避免被大面积黑线稿和白色高光带偏。"""
        pm = self.raw.get("idle", [None])[0]
        if pm is None:
            return QColor(126, 152, 255)
        img = pm.toImage()
        step = max(1, min(img.width(), img.height()) // 160)
        buckets = {}
        for y in range(0, img.height(), step):
            for x in range(0, img.width(), step):
                c = img.pixelColor(x, y)
                if c.alpha() < 200:
                    continue
                h, s, v, _ = c.getHsv()
                if h < 0 or s < 55 or v < 60:
                    continue
                e = buckets.setdefault(h // 30, [0, 0, 0, 0, 0.0])
                e[0] += c.red()
                e[1] += c.green()
                e[2] += c.blue()
                e[3] += 1
                e[4] += s / 255.0
        if not buckets:
            return QColor(126, 152, 255)
        # 不是"哪种颜色像素最多"，而是"哪种颜色又多又鲜艳" —— 否则大面积灰褐色
        # 会把角色真正的主题色压下去（比如双色发里那一抹亮色）
        k = max(buckets, key=lambda i: buckets[i][3] * (buckets[i][4] / buckets[i][3]) ** 2.2)
        e = buckets[k]
        col = QColor(e[0] // e[3], e[1] // e[3], e[2] // e[3])
        h, s, v, _ = col.getHsv()
        if s < 90:                       # 饱和度保底，保证气泡有颜色而不是一片灰
            col = QColor.fromHsv(h, 105, max(150, v))
        return col

    def _bubble_palette(self):
        """对话框三个颜色。auto=True 由角色主色推导，否则用配置里的自定义值。"""
        cfg = self.cfg.get("bubble") or {}
        if cfg.get("auto", True):
            # 保留角色主色的"色相"，只调饱和度和明度：
            # 背景 = 深色玻璃（暗但看得出是什么颜色），边框 = 同色相提亮，
            # 文字 = 同色相的极浅色（近白，保证可读）。
            t = self.theme_color
            h, s, v, _ = t.getHsv()
            if h < 0:
                h = 220
            s = max(s, 130)                       # 饱和度保底，别做成一片灰
            # 明度压到 52/255：再亮一点文字对比度就掉到 WCAG AA 线以下了（实测 4.18）
            bg = QColor.fromHsv(h, int(s * 0.62), 52)
            bg.setAlpha(238)
            bd = QColor.fromHsv(h, min(255, int(s * 1.15)), min(255, int(v * 0.55 + 120)))
            bd.setAlpha(220)
            fg = QColor.fromHsv(h, int(s * 0.15), 255)
        else:
            def pick(key, default):
                v = cfg.get(key) or default
                try:
                    return QColor(int(v[0]), int(v[1]), int(v[2]))
                except Exception:
                    return QColor(*default)
            bg = pick("bg", [19, 28, 54])
            bg.setAlpha(240)
            fg = pick("fg", [234, 239, 255])
            bd = pick("border", [126, 152, 255])
            bd.setAlpha(220)
        return bg, fg, bd

    # -------------------------------------------------------------- 行为
    def _init_behavior(self) -> None:
        self.facing = 1                     # 1 朝右 / -1 朝左
        self._walk_target = None
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._walk_step)

        self._roam_timer = QTimer(self)
        self._roam_timer.setSingleShot(True)
        self._roam_timer.timeout.connect(self._maybe_roam)

        self._flee_timer = QTimer(self)
        self._flee_timer.timeout.connect(self._check_cursor)

        self.setAcceptDrops(True)           # 拖文件到她身上 = 丢进回收站
        self._schedule_roam()
        if self.beh_flee:
            self._flee_timer.start(180)
        # 和伙伴一起转圈：定时读共享计划（没绑定/没计划时是空转，开销可忽略）
        self._bond_active = False
        self._bond_rot = 0.0          # 整只翻转的角度（度）
        self._spin = False
        self._bond_timer = QTimer(self)
        self._bond_timer.timeout.connect(self._bond_tick)
        self._bond_timer.start(BOND_TICK_MS)

    def _busy(self) -> bool:
        """这些状态下不该自己乱跑：正在被拖、正在播放反馈动画、正在说话。"""
        return bool(self._dragging or self.bubble_text or self.bubble_image
                    or self._press is not None)

    def _schedule_roam(self) -> None:
        if self.beh_roam:
            self._roam_timer.start(random.randint(ROAM_MIN_MS, ROAM_MAX_MS))

    def _screen_rect(self):
        s = QApplication.primaryScreen().availableGeometry()
        return s

    # ------------------------------------------------------------ 和伙伴一起玩
    def _sprite_center(self):
        """精灵中心在屏幕上的坐标。"""
        return (self.x() + self.sprite_x + self.sprite_w // 2,
                self.y() + self.bubble_h + self.sprite_h // 2)

    def _set_spin(self, on: bool) -> None:
        """开/关"整只跟着翻转"。尺寸变了必须重采样一次（一分钟一次的开销，无所谓）。"""
        if on == getattr(self, "_spin", False):
            return
        foot = self._foot_screen_pos()
        self._spin = on
        self.apply_scale(resample=True)
        nx = foot.x() - (self.sprite_x + self.sprite_w // 2)
        ny = foot.y() - (self.bubble_h + self.sprite_h)
        s = self._screen_rect()
        self.move(max(s.left(), min(int(nx), s.right() - self.win_w)),
                  max(s.top(), min(int(ny), s.bottom() - self.win_h)))
        self.update()

    def _bond_tick(self) -> None:
        """按共享计划把自己摆到圆周上。用户正在拖她时，人优先。"""
        active = False
        try:
            plan = json.loads(BONDFILE.read_text(encoding="utf-8"))
            pair = plan.get("pair") or []
            now = time.time()
            if self.pet_id in pair and now <= float(plan.get("t0", 0)) + float(plan.get("duration", 0)):
                active = self._bond_step(plan, now)
        except Exception:
            active = False
        if self._bond_active and not active:
            self._bond_active = False
            self._bond_rot = 0.0
            self._set_spin(False)
            self.play("idle")
            self.facing = 1
            self.save_cfg()
            self._schedule_roam()
        self._bond_active = active

    def _bond_step(self, plan: dict, now: float) -> bool:
        if self._dragging or self._press is not None or self._walk_target is not None:
            return False        # 正在被拖 / 正在躲鼠标 / 正在溜达：高优先级行为先做完
        ang = (float(plan.get("angle0", 0.0))
               + float(plan.get("speed", BOND_SPEED)) * (now - float(plan.get("t0", now)))
               + float((plan.get("offsets") or {}).get(self.pet_id, 0.0)))
        cx, cy = (plan.get("center") or [0, 0])[:2]
        r = float(plan.get("radius", BOND_RADIUS))
        tcx = float(cx) + r * math.cos(ang)
        tcy = float(cy) + r * math.sin(ang)
        x = int(tcx - (self.sprite_x + self.sprite_w // 2))
        y = int(tcy - (self.bubble_h + self.sprite_h // 2))
        s = self._screen_rect()
        x = max(s.left(), min(x, s.right() - self.win_w))
        y = max(s.top(), min(y, s.bottom() - self.win_h))
        self.move(x, y)
        self.facing = 1 if math.cos(ang + 1.57) >= 0 else -1     # 朝着切线方向
        # 整只跟着翻转（主人要的"魔性"效果）：角度就是公转角度，转半圈就是倒过来的
        self._set_spin(bool(plan.get("spin", True)))
        self._bond_rot = math.degrees(ang) if self._spin else 0.0
        if self.track not in ("running", "running-left", "running-right"):
            self.play("running")
        self.update()
        return True

    def start_bond_plan(self) -> bool:
        """发起一次"和伙伴一起转圈"：写计划文件，两只会各自读到。

        圆心取两只当前位置的中点（伙伴的窗口尺寸我不知道，用它的存的位置估个偏移就够 ——
        圆心只是个共享参考点，两只是按"自己该在圆周哪一点"精确落位的）。"""
        if not self.pet_id:
            return False
        me = petlist.get_pet(self.pet_id) or {}
        mate_id = me.get("bond")
        if not mate_id:
            return False
        mate = petlist.get_pet(mate_id) or {}
        my_cx, my_cy = self._sprite_center()
        ot_cx = float(mate.get("x", my_cx)) + 110.0
        ot_cy = float(mate.get("y", my_cy)) + 240.0
        cx, cy = (my_cx + ot_cx) / 2.0, (my_cy + ot_cy) / 2.0
        s = self._screen_rect()
        cx = max(s.left() + BOND_RADIUS + 140, min(cx, s.right() - BOND_RADIUS - 140))
        cy = max(s.top() + BOND_RADIUS + 140, min(cy, s.bottom() - BOND_RADIUS - 140))
        cfg = self.load_cfg()          # 转速/翻转跟着控制台的设置走
        plan = {"pair": [self.pet_id, mate_id], "center": [cx, cy], "radius": BOND_RADIUS,
                "angle0": 0.0, "t0": time.time(),
                "speed": float(cfg.get("bond_speed") or BOND_SPEED),
                "spin": bool(cfg.get("bond_spin", True)),
                "duration": BOND_SECONDS,
                "offsets": {self.pet_id: 0.0, mate_id: math.pi}}
        try:
            paths.atomic_write_text(BONDFILE, json.dumps(plan))
        except Exception as e:
            print("写不了计划文件:", e, flush=True)
            return False
        print("一起转圈: %s + %s 圆心 (%.0f, %.0f) 半径 %.0f" % (
            self.pet_id, mate_id, cx, cy, BOND_RADIUS), flush=True)
        return True

    def _maybe_roam(self) -> None:
        self._schedule_roam()
        if not self.beh_roam or self._busy() or self._walk_target is not None:
            return
        if self._bond_active:
            return                       # 正在和伙伴一起玩，别自己溜达走开
        if self.track != "idle":
            return
        s = self._screen_rect()
        tx = random.randint(s.left() + 10, max(s.left() + 11, s.right() - self.win_w - 10))
        ty = self.y() + random.randint(-40, 40)
        ty = max(s.top() + 10, min(ty, s.bottom() - self.win_h - 10))
        self._start_walk(tx, ty, ROAM_SPEED)

    def _start_walk(self, tx: int, ty: int, speed: float) -> None:
        self._walk_target = (tx, ty)
        self._walk_speed = speed
        self.hide_bubble()
        self._walk_timer.start(ROAM_STEP_MS)

    def _walk_step(self) -> None:
        if self._walk_target is None:
            self._walk_timer.stop()
            return
        tx, ty = self._walk_target
        x, y = self.x(), self.y()
        dx, dy = tx - x, ty - y
        dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
        if dist <= self._walk_speed + 1:
            self.move(tx, ty)
            self._walk_target = None
            self._walk_timer.stop()
            self.facing = 1
            self.play("idle")
            self.save_cfg()
            return
        step = self._walk_speed / dist
        self.facing = 1 if dx >= 0 else -1
        self.move(int(x + dx * step), int(y + dy * step))
        if self.track not in ("running", "running-left", "running-right"):
            self.play("running")

    def _check_cursor(self) -> None:
        if not self.beh_flee or self._busy() or self._press is not None:
            return
        if self._walk_target is not None:
            return
        cur = self.cursor().pos()
        cx = self.x() + self.win_w // 2
        cy = self.y() + self.bubble_h + self.sprite_h // 2
        d = ((cur.x() - cx) ** 2 + (cur.y() - cy) ** 2) ** 0.5
        if d > FLEE_DIST:
            return
        # 朝反方向躲开，并夹在屏幕内
        s = self._screen_rect()
        ux, uy = (cx - cur.x()) / max(1.0, d), (cy - cur.y()) / max(1.0, d)
        tx = int(cx + ux * FLEE_DISTANCE)
        ty = int(cy + uy * FLEE_DISTANCE * 0.4)
        tx = max(s.left() + 6, min(tx - self.win_w // 2, s.right() - self.win_w - 6))
        ty = max(s.top() + 6, min(ty - self.win_h // 2, s.bottom() - self.win_h - 6))
        print("被摸到了，躲开 -> (%d,%d)" % (tx, ty), flush=True)
        self._start_walk(tx, ty, ROAM_SPEED * 2.1)

    def reload_palette(self) -> None:
        self.bub_bg, self.bub_fg, self.bub_border = self._bubble_palette()
        self.update()

    # -------------------------------------------------------------- 布局
    def apply_scale(self, resample: bool = True) -> None:
        """重算尺寸；resample=True 时顺带把所有帧重采样一遍。

        resample=False 是给"正在缩放"的交互用的（Ctrl+滚轮 / 拖右下角手柄）：
        只改尺寸，绘制时直接把原图按目标矩形画（painter 缩放）；
        停稳 ZOOM_DEBOUNCE_MS 之后由 _zoom_settle() 真正重采样一次。
        不这么做的话，每滚一格都要把三条轨道几十帧全部 SmoothTransformation 一遍，
        连续缩放会肉眼可见地卡（阿酉需求卡第 2 条）。"""
        screen = self.screen() or QApplication.primaryScreen()
        self.dpr = float(screen.devicePixelRatio()) if screen is not None else 1.0
        self._fast = not resample
        if resample:
            self.frames = {}
            for track, pixmaps in self.raw.items():
                scaled = []
                for pm in pixmaps:
                    w = max(1, int(round(pm.width() * self.scale * self.dpr)))
                    h = max(1, int(round(pm.height() * self.scale * self.dpr)))
                    sp = pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    sp.setDevicePixelRatio(self.dpr)
                    scaled.append(sp)
                self.frames[track] = scaled

        base = self.raw["idle"][0]
        # 转圈时整只跟着翻转：绘制区放大到外接正方形，免得转到 45° 时四个角被窗口裁掉
        pad = SPIN_PAD if getattr(self, "_spin", False) else 1.0
        self.sprite_w = int(round(base.width() * self.scale * pad))
        self.sprite_h = int(round(base.height() * self.scale * pad))
        self.sprite_base_w = int(round(base.width() * self.scale))
        self.sprite_base_h = int(round(base.height() * self.scale))

        font = QFont("Microsoft YaHei UI", BUBBLE_FONT_PX)
        fm = QFontMetrics(font)
        text_h = fm.height() + BUBBLE_PAD_Y * 2 + BUBBLE_TAIL
        text_w = max((fm.horizontalAdvance(v) for k, v in self.bubble_items if k == "text"),
                     default=0) + BUBBLE_PAD_X * 2

        # 图片气泡：按最大 220x140（逻辑像素）等比缩放。
        # 快速路径（缩放交互中）不重采样图片气泡，沿用上一次的尺寸 ——
        # 反正停稳之后马上会走一遍完整流程。
        if resample:
            self.bubble_scaled = {}
            img_w = img_h = 0
            for rel, pm in self.bubble_pixmaps.items():
                w = min(220.0, float(pm.width()) * self.scale)
                h = w * pm.height() / max(1, pm.width())
                if h > 140.0:
                    h = 140.0
                    w = h * pm.width() / max(1, pm.height())
                self.bubble_scaled[rel] = pm.scaled(max(1, int(w * self.dpr)),
                                                    max(1, int(h * self.dpr)),
                                                    Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.bubble_scaled[rel].setDevicePixelRatio(self.dpr)
                img_w = max(img_w, int(w))
                img_h = max(img_h, int(h))
            self.img_bubble_w = img_w + BUBBLE_PAD_X * 2
            self.img_bubble_h = img_h + BUBBLE_PAD_Y * 2

        # 基准尺寸：按"配置里最长的那条台词"和最大的图片算。
        # 但真正显示时可能收到更长的文字（比如拖文件时的文件名、余额之类的动态内容），
        # 所以下面还有一套按内容重算的逻辑 —— 只按配置算一次是不够的，
        # 用户看到的就是"文字太长被截断"。
        self.base_text_w = text_w
        self.text_bubble_h = text_h
        self.bubble_h = max(text_h, self.img_bubble_h + BUBBLE_TAIL)
        self.win_w = max(self.sprite_w, text_w, self.img_bubble_w)
        self.win_h = self.sprite_h + self.bubble_h
        self.sprite_x = (self.win_w - self.sprite_w) // 2
        self._bubble_lines = None
        self.setFixedSize(self.win_w, self.win_h)

    # -------------------------------------------------------------- 自由缩放
    # 阿酉需求卡《自由缩放》：
    #   ① 锚点必须是"脚底中心"，否则一缩放她就往上/下飘；
    #   ② 交互期间防抖，别每滚一格就把几十帧重采样一遍；
    #   ③ 范围钳制 [0.4, 3.0]；
    #   ④ 三档预设保留，自定义值要能显示出来。
    def _foot_screen_pos(self) -> QPoint:
        """精灵"脚底中心"在屏幕上的坐标 —— 缩放的锚点。"""
        return QPoint(self.x() + self.sprite_x + self.sprite_w // 2,
                      self.y() + self.bubble_h + self.sprite_h)

    def _zoom_to(self, new_scale: float, resample: bool = False) -> bool:
        """缩放到 new_scale，并保证脚底中心钉在原地。返回是否真的变了。"""
        new_scale = max(SCALE_MIN, min(SCALE_MAX, float(new_scale)))
        if abs(new_scale - self.scale) < 1e-4:
            return False
        foot = self._foot_screen_pos()
        self.scale = new_scale
        self.apply_scale(resample=resample)
        # apply_scale 只改窗口尺寸，不碰位置 —— 位置要按新尺寸反推回来
        nx = foot.x() - (self.sprite_x + self.sprite_w // 2)
        ny = foot.y() - (self.bubble_h + self.sprite_h)
        s = self._screen_rect()
        # 贴到屏幕边时夹取优先：放不下就把她整体拉回屏幕内（脚底会挪一点）。
        # 这是有意的 —— 缩放到 3 倍时窗口可能比留下的空间还高，
        # 宁可脚底挪几像素，也不能让她半个身子在屏幕外点不到。
        nx = max(s.left(), min(int(nx), s.right() - self.win_w))
        ny = max(s.top(), min(int(ny), s.bottom() - self.win_h))
        self.move(nx, ny)
        self.update()
        return True

    def _zoom_settle(self) -> None:
        """缩放停稳：真正重采样一次并落盘（期间画面上一直用的是 painter 缩放）。"""
        foot = self._foot_screen_pos()
        self.apply_scale(resample=True)
        nx = foot.x() - (self.sprite_x + self.sprite_w // 2)
        ny = foot.y() - (self.bubble_h + self.sprite_h)
        s = self._screen_rect()
        self.move(max(s.left(), min(int(nx), s.right() - self.win_w)),
                  max(s.top(), min(int(ny), s.bottom() - self.win_h)))
        self.save_cfg()
        self.update()

    def _zoom_feedback(self) -> None:
        """缩放时在头顶显示当前百分比（百分数变了才重排气泡，不然每次鼠标移动都要重排）。"""
        pct = int(round(self.scale * 100))
        if pct != self._zoom_hint:
            self._zoom_hint = pct
            self.show_bubble("%d%%" % pct, ms=900)

    def wheelEvent(self, event) -> None:
        """Ctrl + 滚轮 = 自由缩放（第一级）。不按 Ctrl 时滚轮什么也不做。"""
        if not (event.modifiers() & Qt.ControlModifier):
            event.ignore()
            return
        notches = event.angleDelta().y() / 120.0
        if not notches:
            event.ignore()
            return
        if self._zoom_to(self.scale * (ZOOM_STEP ** notches)):
            self._zoom_feedback()
            self._zoom_timer.start(ZOOM_DEBOUNCE_MS)
        event.accept()

    def _handle_rect(self) -> QRect | None:
        """「调整大小」手柄的位置（精灵右下角）；不在显示期就返回 None。"""
        if time.monotonic() >= self._handle_until:
            return None
        x = self.sprite_x + self.sprite_w - HANDLE_SIZE - 2
        y = self.bubble_h + self.sprite_h - HANDLE_SIZE - 2
        return QRect(max(0, x), max(0, y), HANDLE_SIZE, HANDLE_SIZE)

    def show_resize_handle(self) -> None:
        """把缩放手柄亮出来 HANDLE_SHOW_MS 毫秒（右键菜单 / 控制台提示用）。"""
        self._handle_until = time.monotonic() + HANDLE_SHOW_MS / 1000.0
        self._handle_timer.start(HANDLE_SHOW_MS)
        self.update()

    def _draw_resize_handle(self, painter: QPainter) -> None:
        r = self._handle_rect()
        if r is None:
            return
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(20, 28, 52, 190))
        painter.drawRoundedRect(r, 4, 4)
        painter.setPen(QColor(150, 190, 255, 235))
        # 一个斜向双箭头，一眼看出"这里能拖大小"
        x0, y0 = r.right() - 4, r.bottom() - 4
        for k in range(3):
            off = k * 4
            painter.drawLine(x0 - off, y0, x0, y0 - off)
        painter.drawLine(r.left() + 5, r.bottom() - 5, r.right() - 5, r.top() + 5)
        painter.restore()

    def _dist(self, a: QPoint, b: QPoint) -> float:
        return math.hypot(a.x() - b.x(), a.y() - b.y())

    # -------------------------------------------------------------- 气泡排版
    def _wrap_text(self, text: str, max_w: int) -> list:
        """按像素宽度折行。逐字符累加，中英文混排都适用。"""
        fm = QFontMetrics(QFont("Microsoft YaHei UI", BUBBLE_FONT_PX))
        lines, cur = [], ""
        for ch in text:
            if ch == "\n":
                lines.append(cur)
                cur = ""
                continue
            if not cur or fm.horizontalAdvance(cur + ch) <= max_w:
                cur += ch
            else:
                lines.append(cur)
                cur = ch
        lines.append(cur)
        return lines or [""]

    def _layout_for_bubble(self, text=None) -> None:
        """按这次要显示的内容重算窗口大小；精灵在屏幕上的位置保持不变（不然气泡一长她就往下跳）。"""
        fm = QFontMetrics(QFont("Microsoft YaHei UI", BUBBLE_FONT_PX))
        scr = self._screen_rect()
        max_w = max(180, int(scr.width() * MAX_BUBBLE_W_RATIO))

        lines = None
        if text:
            lines = self._wrap_text(text, max(120, max_w - BUBBLE_PAD_X * 2))
            if len(lines) > MAX_BUBBLE_LINES:          # 太长就截断，别糊满屏幕
                lines = lines[:MAX_BUBBLE_LINES]
                lines[-1] = lines[-1][:-1] + "…"
        self._bubble_lines = lines

        tw = max((fm.horizontalAdvance(ln) for ln in lines), default=0) + BUBBLE_PAD_X * 2 if lines else 0
        th = (fm.height() * len(lines) + BUBBLE_PAD_Y * 2) if lines else 0
        need_w = max(self.base_text_w, min(tw, max_w), self.img_bubble_w)
        need_bh = max(self.text_bubble_h, (th + BUBBLE_TAIL) if lines else 0,
                      self.img_bubble_h + BUBBLE_TAIL)

        if need_w == self.win_w and self.sprite_h + need_bh == self.win_h:
            return
        # 记住精灵当前在屏幕上的左脚位置，重排后把它挪回去
        sprite_left = self.x() + self.sprite_x
        sprite_top = self.y() + self.bubble_h
        self.bubble_h = need_bh
        self.win_w = max(need_w, self.sprite_w)
        self.win_h = self.sprite_h + self.bubble_h
        self.sprite_x = (self.win_w - self.sprite_w) // 2
        self.setFixedSize(self.win_w, self.win_h)
        s = self._screen_rect()
        nx = max(s.left(), min(sprite_left - self.sprite_x, s.right() - self.win_w))
        ny = max(s.top(), min(sprite_top - self.bubble_h, s.bottom() - self.win_h))
        self.move(int(nx), int(ny))

    def restore_pos(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        src = self._entry if self.pet_id else self.cfg
        x = int(src.get("x", screen.right() - self.win_w - 40))
        y = int(src.get("y", screen.bottom() - self.win_h - 40))
        x = max(screen.left(), min(x, screen.right() - self.win_w))
        y = max(screen.top(), min(y, screen.bottom() - self.win_h))
        self.move(x, y)
        self.save_cfg()

    # -------------------------------------------------------------- 动画
    def play(self, track: str, once_then: str | None = None) -> None:
        if track not in self.frames:
            track = "idle"
        self.track = track
        self.index = 0
        self.once_then = once_then
        per = (self.frame_ms or {}).get(track)
        first = int(per[0]) if per and 16 <= int(per[0]) <= 5000 else TRACK_MS.get(track, 150)
        self.timer.start(first)
        self.update()

    def tick(self) -> None:
        frames = self.frames[self.track]
        self.index += 1
        if self.index >= len(frames):
            if self.once_then is None:
                self.index = 0
            else:
                nxt = self.once_then
                self.once_then = None
                self.play(nxt)
                return
        # 动图自带的每帧时长（GIF 的 duration）优先于默认节奏
        per = (self.frame_ms or {}).get(self.track)
        if per and self.index < len(per):
            ms = int(per[self.index])
            if 16 <= ms <= 5000:
                self.timer.setInterval(ms)
        self.update()

    # -------------------------------------------------------------- 交互
    def react(self) -> None:
        kind, value = self._pick_bubble()
        if kind == "image":
            self.show_image_bubble(value)
        else:
            self.show_bubble(value)
        self.play(random.choice(self.react_tracks), once_then="idle")
        self.play_sfx("click")

    def show_bubble(self, text: str, ms: int = BUBBLE_MS) -> None:
        print("气泡(文字):", text, flush=True)
        self._layout_for_bubble(text)      # 按这次的内容重排气泡（长文件名也能完整显示）
        self.bubble_text = text
        self.bubble_image = None
        self.bubble_timer.start(ms)
        self.update()

    def show_image_bubble(self, rel: str) -> None:
        print("气泡(图片):", rel, flush=True)
        self._layout_for_bubble(None)
        self.bubble_text = None
        self.bubble_image = rel
        self.bubble_timer.start(BUBBLE_MS)
        self.update()

    def hide_bubble(self) -> None:
        self.bubble_text = None
        self.bubble_image = None
        self.update()

    def in_sprite(self, pos: QPoint) -> bool:
        return pos.y() >= self.bubble_h

    def mousePressEvent(self, event) -> None:
        local = event.position().toPoint()
        # 手柄优先：它在精灵区域内，先判它，否则会被"拖动"吃掉
        hb = self._handle_rect()
        if event.button() == Qt.LeftButton and hb is not None and hb.contains(local):
            self._resizing = True
            anchor = self._foot_screen_pos()
            cur = self.cursor().pos()
            # 径向缩放：以脚底为锚，鼠标离脚底越远越大
            self._resize_start = (anchor, max(24.0, self._dist(cur, anchor)), self.scale)
            self._handle_until = time.monotonic() + HANDLE_SHOW_MS / 1000.0
            self._handle_timer.start(HANDLE_SHOW_MS)
            self._walk_target = None
            self._walk_timer.stop()
            event.accept()
            return
        if event.button() == Qt.LeftButton and self.in_sprite(local):
            self._press = self.cursor().pos()          # 用系统光标坐标，重新 SetParent 后依然可靠
            self._win_at_press = self.pos()
            self._dragging = False
            self._drag_vel = (0.0, 0.0)
            self._last_sample = None
            self._walk_target = None                   # 抓住她的时候停止自动走动
            self._walk_timer.stop()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._resizing and self._resize_start is not None:
            anchor, d0, s0 = self._resize_start
            cur = self.cursor().pos()
            d = max(24.0, self._dist(cur, anchor))
            if self._zoom_to(s0 * d / d0):
                self._zoom_feedback()
                self._zoom_timer.start(ZOOM_DEBOUNCE_MS)
            event.accept()
            return
        if self._press is None:
            return
        cur = self.cursor().pos()
        now = time.time()
        if getattr(self, "_last_sample", None) is not None:
            lp, lt = self._last_sample
            dt = now - lt
            if dt > 0.001:
                self._drag_vel = ((cur.x() - lp.x()) / dt, (cur.y() - lp.y()) / dt)
        self._last_sample = (cur, now)
        delta = cur - self._press
        if not self._dragging and delta.manhattanLength() > 4:
            self._dragging = True
            self.play("running")
            self.play_sfx("grab")
            self.hide_bubble()
        if self._dragging:
            self.move(self._win_at_press + delta)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._resizing:
            self._resizing = False
            self._resize_start = None
            self._zoom_timer.start(0)      # 立刻重采样一次并落盘
            self._handle_until = time.monotonic() + HANDLE_SHOW_MS / 1000.0
            self._handle_timer.start(HANDLE_SHOW_MS)
            event.accept()
            return
        if self._press is None:
            return
        if self._dragging:
            self.play("idle")
            self.play_sfx("land")
            self.save_cfg()
            self._start_inertia()
        else:
            self.react()
        self._press = None
        self._dragging = False
        self._last_sample = None
        event.accept()

    def _start_inertia(self) -> None:
        """松手后的惯性滑行：按拖拽速度继续滑一段并衰减。
        这是"她有重量"的关键手感 —— Petra 那条清单里成本最低、体感提升最明显的一项。"""
        if not self.beh_inertia:
            self._schedule_roam()
            return
        vx, vy = getattr(self, "_drag_vel", (0.0, 0.0))
        speed = (vx * vx + vy * vy) ** 0.5
        if speed < 180:                      # 慢慢放下就不滑了
            self._schedule_roam()
            return
        vx = max(-1600.0, min(1600.0, vx)) * INERTIA_GAIN
        vy = max(-1600.0, min(1600.0, vy)) * INERTIA_GAIN
        self._inertia = [vx, vy]
        if not hasattr(self, "_inertia_timer"):
            self._inertia_timer = QTimer(self)
            self._inertia_timer.timeout.connect(self._inertia_step)
        self.facing = 1 if vx >= 0 else -1
        if abs(vx) > 40 and self.track == "idle":
            self.play("running")
        self._inertia_timer.start(16)

    def _inertia_step(self) -> None:
        s = self._screen_rect()
        x, y = self.x() + self._inertia[0], self.y() + self._inertia[1]
        x = max(s.left(), min(x, s.right() - self.win_w))
        y = max(s.top(), min(y, s.bottom() - self.win_h))
        self.move(int(x), int(y))
        self._inertia[0] *= INERTIA_FRICTION
        self._inertia[1] *= INERTIA_FRICTION
        if (self._inertia[0] ** 2 + self._inertia[1] ** 2) ** 0.5 < 8:
            self._inertia_timer.stop()
            self.facing = 1
            self.play("idle")
            self.save_cfg()
            self._schedule_roam()

    # -------------------------------------------------------------- 拖文件回收
    def dragEnterEvent(self, event) -> None:
        # 手柄亮着的时候挂起拖放：那块区域正好在手柄旁边，缩放手势和"拖文件进来"会打架
        if self._handle_rect() is not None:
            return
        if self.beh_recycle and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if self.beh_recycle and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not (self.beh_recycle and event.mimeData().hasUrls()):
            return
        paths = []
        for u in event.mimeData().urls():
            p = u.toLocalFile()
            if p:
                paths.append(p)
        if not paths:
            return
        event.acceptProposedAction()
        ok = recycle_paths(paths)
        name = paths[0].replace("\\", "/").rsplit("/", 1)[-1]
        more = "" if len(paths) == 1 else " 等 %d 个文件" % len(paths)
        self.show_bubble(("吃掉啦：" + name + more) if ok else ("咬不动：" + name))
        self.play("jumping", once_then="idle")

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#131c36;color:#eaefff;border:1px solid #4d6bfe;padding:4px}"
                           "QMenu:item{padding:5px 22px;border-radius:4px}"
                           "QMenu:item:selected{background:#4d6bfe}")
        for label, mode in (("只贴在壁纸上（被窗口盖住就看不见）", "desktop"),
                            ("始终置顶（浮在所有窗口上面）", "topmost")):
            act = QAction(label + ("  ✓" if self.mode == mode else ""), self)
            act.triggered.connect(lambda _=False, m=mode: self.set_mode(m))
            menu.addAction(act)
        menu.addSeparator()
        size_menu = menu.addMenu("大小")
        for label, value in SCALE_STEPS:
            act = QAction(label + ("  ✓" if abs(value - self.scale) < 1e-6 else ""), self)
            act.triggered.connect(lambda _=False, v=value: self.set_scale(v))
            size_menu.addAction(act)
        if not any(abs(value - self.scale) < 1e-6 for _, value in SCALE_STEPS):
            # 自由缩放出来的值：菜单里要能看见，不然用户不知道当前是多少
            cur = QAction("自定义 %d%%  ✓" % round(self.scale * 100), self)
            cur.setEnabled(False)
            size_menu.addAction(cur)
        if self.pet_id and (petlist.get_pet(self.pet_id) or {}).get("bond"):
            mate = (petlist.get_pet(self.pet_id) or {}).get("bond")
            act_bond = QAction("和「%s」一起转圈" % mate, self)
            act_bond.triggered.connect(self.start_bond_plan)
            menu.addAction(act_bond)
            menu.addSeparator()
        size_menu.addSeparator()
        act_handle = QAction("调整大小（拖右下角的小方块，或 Ctrl+滚轮）", self)
        act_handle.triggered.connect(self.show_resize_handle)
        size_menu.addAction(act_handle)
        menu.addSeparator()
        quit_act = QAction("关闭桌宠", self)
        quit_act.triggered.connect(QApplication.quit)
        menu.addAction(quit_act)
        menu.exec(event.globalPos())

    def set_scale(self, value: float) -> None:
        self.scale = value
        self.apply_scale()
        self.play("idle")
        self.save_cfg()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.save_cfg()
        # 层级切换靠重新挂载，最稳
        QApplication.exit(77)

    # -------------------------------------------------------------- 绘制
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if getattr(self, "_fast", False):
            # 缩放交互中：还没重采样，直接把原图按目标矩形画（painter 负责缩放）
            raw = self.raw.get(self.track) or self.raw["idle"]
            self._draw_sprite(painter, raw[min(self.index, len(raw) - 1)], stretch=True)
            if self.bubble_text or self.bubble_image:
                self.draw_bubble(painter)
            self._draw_resize_handle(painter)
            return
        frames = self.frames.get(self.track) or self.frames["idle"]
        self._draw_sprite(painter, frames[min(self.index, len(frames) - 1)])
        if self.bubble_text or self.bubble_image:
            self.draw_bubble(painter)
        self._draw_resize_handle(painter)

    def _draw_sprite(self, painter: QPainter, pm, stretch: bool = False) -> None:
        """把一帧画进精灵区。

        stretch=True 是缩放交互期间的快速路径（原图直接拉伸到目标框）；
        转圈时（_bond_rot 非 0）整只绕自己的中心旋转 —— 转 180° 就是倒过来的那个效果，
        绘制区在 apply_scale 里已经放大过 SPIN_PAD 倍，所以四个角不会被裁掉。"""
        rot = getattr(self, "_bond_rot", 0.0)
        flip = getattr(self, "facing", 1) < 0
        # 注意：翻转模式（_spin）下绘制区被放大了 SPIN_PAD 倍，精灵必须**居中**画，
        # 否则旋转 0° 时贴在左上角、旋转 180° 时又回到中心，看起来就是"转的时候乱跳"
        # （这个 bug 是被 test-bond-spin 的像素比对抓出来的）。
        if not rot and not stretch and not getattr(self, "_spin", False):
            painter.save()
            if flip:
                # 只有一个朝向的立绘：往左走时水平翻转（气泡不翻，文字才可读）
                painter.translate(self.sprite_x + self.sprite_w, self.bubble_h)
                painter.scale(-1, 1)
                painter.drawPixmap(0, 0, pm)
            else:
                painter.drawPixmap(self.sprite_x, self.bubble_h, pm)
            painter.restore()
            return
        w = getattr(self, "sprite_base_w", self.sprite_w)
        h = getattr(self, "sprite_base_h", self.sprite_h)
        cx = self.sprite_x + self.sprite_w / 2.0
        cy = self.bubble_h + self.sprite_h / 2.0
        painter.save()
        painter.translate(cx, cy)
        if rot:
            painter.rotate(rot)
        if flip:
            painter.scale(-1, 1)
        if stretch:
            # 快速路径：绘制区就是"当前缩放后的尺寸"，直接铺满
            painter.drawPixmap(int(-self.sprite_w / 2), int(-self.sprite_h / 2),
                               int(self.sprite_w), int(self.sprite_h), pm)
        else:
            painter.drawPixmap(int(-w / 2), int(-h / 2), int(w), int(h), pm)
        painter.restore()

    def draw_bubble(self, painter: QPainter) -> None:
        font = QFont("Microsoft YaHei UI", BUBBLE_FONT_PX)
        fm = QFontMetrics(font)
        text = self.bubble_text or ""
        lines = self._bubble_lines
        if self.bubble_image:
            bw = self.img_bubble_w
            bh = self.img_bubble_h
        elif lines:
            bw = max((fm.horizontalAdvance(ln) for ln in lines), default=0) + BUBBLE_PAD_X * 2
            bh = fm.height() * len(lines) + BUBBLE_PAD_Y * 2
        else:
            bw = fm.horizontalAdvance(text) + BUBBLE_PAD_X * 2
            bh = fm.height() + BUBBLE_PAD_Y * 2
        bx = (self.win_w - bw) // 2
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        path.addRoundedRect(QRect(bx, 0, bw, bh), bh / 2, bh / 2)
        cx = self.win_w // 2
        path.moveTo(cx - BUBBLE_TAIL, bh - 1)
        path.lineTo(cx, bh + BUBBLE_TAIL)
        path.lineTo(cx + BUBBLE_TAIL, bh - 1)
        path.closeSubpath()
        # 上浅下深的渐变，做出一点玻璃质感
        top = QColor(min(255, int(self.bub_bg.red() * 1.45 + 18)),
                     min(255, int(self.bub_bg.green() * 1.45 + 18)),
                     min(255, int(self.bub_bg.blue() * 1.45 + 18)),
                     self.bub_bg.alpha())
        grad = QLinearGradient(0, 0, 0, bh)
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, self.bub_bg)
        painter.setPen(self.bub_border)
        painter.setBrush(QBrush(grad))
        painter.drawPath(path)
        if self.bubble_image:
            pm = self.bubble_scaled.get(self.bubble_image)
            if pm is not None:
                painter.drawPixmap(int(bx + (bw - pm.width() / self.dpr) / 2),
                                   int((bh - pm.height() / self.dpr) / 2), pm)
        else:
            painter.setFont(font)
            painter.setPen(self.bub_fg)
            if lines and len(lines) > 1:
                for li, ln in enumerate(lines):
                    painter.drawText(QRect(bx, BUBBLE_PAD_Y + li * fm.height(), bw, fm.height()),
                                     Qt.AlignCenter, ln)
            else:
                painter.drawText(QRect(bx, 0, bw, bh), Qt.AlignCenter, text)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 出场音效只响一次（切换显示层级会重挂载，showEvent 会再来一遍）
        if not getattr(self, "_spawn_sfx_done", False):
            self._spawn_sfx_done = True
            self.play_sfx("spawn")
        QTimer.singleShot(80, self.apply_layer)

    def apply_layer(self) -> None:
        hwnd = int(self.winId())
        # 不占任务栏 / 不进 Alt-Tab
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              (style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        print("layer: hwnd=%d class=%s exstyle=0x%x" % (
            hwnd, window_class(hwnd), user32.GetWindowLongW(hwnd, GWL_EXSTYLE)), flush=True)
        if self.mode == "desktop":
            push_to_bottom(hwnd)
            if not hasattr(self, "bottom_timer"):
                self.bottom_timer = QTimer(self)
                self.bottom_timer.timeout.connect(lambda: push_to_bottom(int(self.winId())))
            self.bottom_timer.start(1500)     # 定期重申，防止被别的事件顶上来
        elif hasattr(self, "bottom_timer"):
            self.bottom_timer.stop()


def _proc_creation() -> int:
    """本进程的创建时刻（100ns），和 petctl.proc_creation 对应。取不到就返回 0。"""
    try:
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k.OpenProcess(0x1000, False, ctypes.windll.kernel32.GetCurrentProcessId())
        c, e, kt, u = (wintypes.FILETIME(), wintypes.FILETIME(),
                       wintypes.FILETIME(), wintypes.FILETIME())
        if not h or not k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                          ctypes.byref(kt), ctypes.byref(u)):
            return 0
        k.CloseHandle(h)
        return (int(c.dwHighDateTime) << 32) | int(c.dwLowDateTime)
    except Exception:
        return 0


def _setup_log() -> None:
    """用 pythonw 启动时没有控制台，日志会全部丢掉。写文件，出问题才能查。"""
    try:
        d = paths.log_dir()
        log = d / "deskpet.log"
        try:
            if log.exists() and log.stat().st_size > 1024 * 1024:
                log.replace(d / "deskpet.log.old")     # 长期挂机不会无限涨
        except Exception:
            pass
        f = open(log, "a", encoding="utf-8", buffering=1)
        sys.stdout = f
        sys.stderr = f
        try:
            import os
            ppid = os.getppid()
            pname = ""
            try:
                import ctypes as _c
                k = _c.WinDLL("kernel32", use_last_error=True)
                h = k.OpenProcess(0x1000, False, ppid)
                if h:
                    buf = _c.create_unicode_buffer(512)
                    sz = _c.wintypes.DWORD(512) if hasattr(_c, "wintypes") else None
                    from ctypes import wintypes as _w
                    sz = _w.DWORD(512)
                    k.QueryFullProcessImageNameW(h, 0, buf, _c.byref(sz))
                    pname = buf.value
                    k.CloseHandle(h)
            except Exception:
                pass
            extra = "  父进程=%d %s" % (ppid, pname)
        except Exception:
            extra = ""
        print("\n===== 启动 " + time.strftime("%Y-%m-%d %H:%M:%S") + extra + " =====")
    except Exception:
        pass


def main() -> int:
    _setup_log()
    # --id <petid>：以"多桌宠实例"身份运行（控制台召唤多只时用）
    pet_id = None
    if "--id" in sys.argv:
        k = sys.argv.index("--id")
        if k + 1 < len(sys.argv):
            pet_id = sys.argv[k + 1]
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    while True:
        try:
            pet = DeskPet(pet_id)
        except SystemExit as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "桌宠启动失败", str(e))
            return 1
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            traceback.print_exc()
            QMessageBox.critical(None, "桌宠启动失败", str(e))
            return 1
        pet.show()
        code = app.exec()
        # 只清理"自己写的那个" pet.pid：多实例不碰它，
        # 否则一只实例退出就会把单宠物那只的 pid 抹掉（控制台就再也关不掉它了）。
        if not pet_id:
            try:
                if PIDFILE.read_text(encoding="utf-8").strip().split()[0] == str(
                        ctypes.windll.kernel32.GetCurrentProcessId()):
                    PIDFILE.unlink()
            except Exception:
                pass
        if code != 77:            # 77 = 用户切换了显示层级，重新挂载再来一次
            return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        raise
