#!/usr/bin/env python3
"""petctl.pyw —— 桌宠控制台

  · 一键显示 / 关闭桌宠
  · 切换显示层级（只贴壁纸 / 始终置顶）、形象、大小、音效
  · 上传图片生成新桌宠（静态 / 点击有反应 / 完整动态），带预览和抠图强度调节
  · 开机自启开关
关窗口 = 收进托盘。单实例。

注意：所有子进程调用都必须带 CREATE_NO_WINDOW。这是个 GUI 进程（pythonw，没有控制台），
调控制台程序时 Windows 会给它新建一个控制台窗口 —— 就是之前"疯狂闪黑窗口"的原因。
判断桌宠是否在跑改用 ctypes 直接查进程，连子进程都不开。
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

import traceback

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QImage, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtCore import QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QColorDialog, QComboBox,
                               QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QGridLayout, QListWidget, QListWidgetItem, QMenu, QMessageBox,
                               QPushButton, QRadioButton, QScrollArea, QSystemTrayIcon,
                               QVBoxLayout, QWidget)

try:
    import winsound                      # 试听用（和桌宠本体同一套，只认 WAV）
except ImportError:
    winsound = None

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
import paths
import petlist

paths.migrate_from_app_dir()          # 首次运行：把老版本散在程序目录的数据搬到 %APPDATA%
paths.setup_model_env()               # 让 rembg 用随包的模型，而不是联网下载

APP_DIR = paths.APP
ASSETS = APP_DIR / "assets"           # 内置素材（只读）
CONFIG = paths.config_path()
PIDFILE = paths.pid_path()
NAMES = paths.data_root() / "assets" / "user" / "names.json"
KILLER = APP_DIR / "tools" / "kill-pets.ps1"
ICON = paths.find_asset("icon.ico") or (ASSETS / "icon.ico")
SERVER_NAME = "deskpet-console-single-instance"

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
NO_WIN = CREATE_NO_WINDOW | DETACHED_PROCESS

# 互动音效的四类触发点（和 deskpet.SFX_EVENTS 对应）
SFX_EVENTS = [("click", "点击"), ("grab", "抓起"), ("land", "落地"), ("spawn", "出现")]

# 一起转圈的转速预设（弧度/秒，和 deskpet.BOND_SPEEDS 对应）
BOND_SPEEDS = [("慢", 0.45), ("中", 0.8), ("快", 1.5), ("魔性", 2.6)]

SCALE_STEPS = [("小", 0.7), ("中", 1.0), ("大", 1.4)]
MOTION_MODES = [("完全静止（就一张图）", "still"),
                ("静态 + 点击有反应", "reactive"),
                ("完整动态（待机浮动 + 跳跃 + 摇摆）", "full")]
LITE_MODE = False

CUT_MODES = [("智能 AI（推荐，背景再乱也行）", "ai"),
             ("快速算法（秒出，纯色底才干净）", "algo"),
             # 加这条是因为自动抠图对"角色和背景颜色接近 / 本来就是场景图"的图片
             # 在原理上就分不开 —— 与其让用户对着花掉的边缘较劲，不如给一个"直接用原图"的出口。
             ("不抠图（原图直接用，适合已经是透明底的图）", "none")]
GAP_LEVELS = [("关闭（只去外圈背景）", "off"),
              ("保守（只清小缝隙）", "low"),
              ("标准（推荐）", "normal"),
              ("强力（连大块夹缝一起清）", "strong")]
STRENGTHS = [("柔和（保留更完整的边缘）", "soft"),
             ("标准（推荐）", "normal"),
             ("严格（背景有杂色时用，边缘会略硬）", "strong")]

PY = Path(sys.executable)
PYW = PY.with_name("pythonw.exe") if PY.name.lower() == "python.exe" else PY

# ---------------------------------------------------------------- 进程检测
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                     ctypes.POINTER(wintypes.FILETIME),
                                     ctypes.POINTER(wintypes.FILETIME),
                                     ctypes.POINTER(wintypes.FILETIME)]
kernel32.GetProcessTimes.restype = wintypes.BOOL


def proc_creation(pid: int) -> int:
    """进程创建时刻（100ns 单位）。0 = 问不到。

    为什么要它：pid 是会被系统**复用**的。光看"这个 pid 活着、而且是 python.exe"
    就可能杀掉一个完全不相干的进程；把它和 pet.pid 里记的创建时刻对一下就能识破。"""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return 0
    try:
        c, e, k, u = (wintypes.FILETIME(), wintypes.FILETIME(),
                      wintypes.FILETIME(), wintypes.FILETIME())
        if not kernel32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                        ctypes.byref(k), ctypes.byref(u)):
            return 0
        return (int(c.dwHighDateTime) << 32) | int(c.dwLowDateTime)
    except Exception:
        return 0
    finally:
        kernel32.CloseHandle(h)


def _accepted_exe_names() -> set:
    """哪些可执行文件名算"是我们的进程"。

    这里踩过一个把三个症状串在一起的坑：原来只认名字里含 "python"，
    但打包后进程是 DeskPet.exe —— 于是 pid_alive 永远返回 False，导致：
      ① 控制台永远显示"她不在"；
      ② apply() 里 "if pet_running(): 重启" 从不成立 → 改行为开关不生效；
      ③ stop_pet() 直接 return → 关不掉她。
    一个判断写错，三个功能一起坏。"""
    names = {"python.exe", "pythonw.exe", "deskpet.exe", "deskpet-lite.exe"}
    try:
        names.add(Path(sys.executable).name.lower())
    except Exception:
        pass
    return names


def pid_alive(pid: int) -> bool:
    """不开子进程直接问系统：这个 pid 还活着吗，而且是我们自己的可执行文件吗。"""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != STILL_ACTIVE:
            return False
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            name = Path(buf.value).name.lower()
            return name in _accepted_exe_names()
        return True
    finally:
        kernel32.CloseHandle(h)


def read_pid_info():
    """pet.pid 里记的是 "<pid> <创建时刻>"（老格式只有一个 pid，也认）。
    创建时刻用来识破 pid 复用，见 proc_creation()。"""
    try:
        parts = PIDFILE.read_text().strip().split()
        pid = int(parts[0])
        created = int(parts[1]) if len(parts) > 1 else 0
        return pid, created
    except Exception:
        return None, 0


def read_pid():
    return read_pid_info()[0]


def pet_running(pet_id: str | None = None) -> bool:
    """不传 pet_id = 单宠物模式（看 pet.pid）；传了就查那只实例的 pid。"""
    if pet_id:
        p = petlist.get_pet(pet_id) or {}
        pid = p.get("pid")
        return bool(pid) and pid_alive(int(pid))
    pid, created = read_pid_info()
    if pid is None or not pid_alive(pid):
        return False
    # 记了创建时刻就核对一下：pid 被复用的话这里会对不上，不能当成"她还活着"
    return (not created) or proc_creation(pid) == created


def running_pets() -> list:
    return [p for p in petlist.load_pets() if pet_running(p.get("id"))]


# ---------------------------------------------------------------- 配置 / 形象
_CFG_CACHE = {"mtime": None, "data": {}}


def load_cfg() -> dict:
    """按 mtime 缓存：refresh() 每秒跑一次，没必要每秒读盘（阿酉 review P1-2）。"""
    try:
        mt = CONFIG.stat().st_mtime_ns
    except Exception:
        return {}
    if _CFG_CACHE["mtime"] == mt:
        return _CFG_CACHE["data"]
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    _CFG_CACHE["mtime"] = mt
    _CFG_CACHE["data"] = data
    return data


def ui_sleep(seconds: float) -> None:
    """GUI 线程里的等待：让窗口保持"活着"（能重绘、能拖动、能点别的）。

    外部测试 BUG-3：apply()/on_add_pet()/show_pet() 等槽函数里直接 time.sleep，
    最坏 5s+ 整个控制台冻结、标题栏挂"未响应"。上传流水线线程化过，
    这批是同类残留 —— 但这些等待天然是串行步骤（停了才能再启），
    全面异步化改动太大，所以取最小修复：等待期间周期性 processEvents。
    只在 Qt 事件循环里才有意义；CLI 模式（无 QApplication）退回普通 sleep。"""
    app = QApplication.instance()
    if app is None:
        time.sleep(seconds)
        return
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


def save_cfg(cfg: dict) -> None:
    # 原子写：桌宠同时也在写这个文件，非原子写会让对方读到半截 JSON。
    # 写失败必须留痕（外部测试 BUG-1/BUG-5）：异常冒给 Qt 槽的话，
    # pythonw 下 stderr 是 None，一个字都不会留下，用户只看到"没生效"。
    try:
        paths.atomic_write_text(CONFIG, json.dumps(cfg, indent=2, ensure_ascii=False))
    except Exception as e:
        try:
            d = BASE / "logs"
            d.mkdir(exist_ok=True)
            with open(d / "ctl.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%H:%M:%S") + "  [save_cfg] 写 config.json 失败: %r\n" % (e,))
        except Exception:
            pass
        raise
    _CFG_CACHE["mtime"] = None      # 让本进程的缓存失效


def load_names() -> dict:
    try:
        return json.loads(NAMES.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_names(d: dict) -> None:
    NAMES.parent.mkdir(parents=True, exist_ok=True)
    paths.atomic_write_text(NAMES, json.dumps(d, indent=2, ensure_ascii=False))


# 内置形象的显示名：素材目录名是英文 id，界面上直接显示"nailong"太难看了。
# 用户自己传的形象走 names.json（上传时填的名字）。
BUILTIN_NAMES = {paths.DEFAULT_CHARACTER: "奶龙"}

_CHARS_CACHE = {"at": 0.0, "data": []}


def characters() -> list[tuple[str, str]]:
    """3 秒内不重复递归扫盘。素材一多，每秒 glob 一次会越来越慢。"""
    now = time.time()
    if now - _CHARS_CACHE["at"] < 3.0 and _CHARS_CACHE["data"]:
        return _CHARS_CACHE["data"]
    names = load_names()
    out = []
    seen = set()
    # 内置素材在程序目录、用户上传的在数据目录，两个根都扫；同名以数据目录优先
    for root in paths.asset_roots():
        if not root.exists():
            continue
        for mf in sorted(root.glob("**/_frames.json")):
            rel = mf.parent.relative_to(root).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            out.append((names.get(rel) or BUILTIN_NAMES.get(rel) or rel, rel))
    _CHARS_CACHE["at"] = now
    _CHARS_CACHE["data"] = out
    return out


def start_pet(pet_id: str | None = None) -> None:
    if pet_running(pet_id):
        return
    # 打包后是"单 exe 双模式"：同一个 exe 用 --pet 进桌宠分支
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--pet"]
    else:
        cmd = [str(PYW), str(BASE / "deskpet.py")]
    if pet_id:
        cmd += ["--id", pet_id]
    subprocess.Popen(cmd, cwd=str(APP_DIR), creationflags=NO_WIN, close_fds=True)


def start_all_pets() -> None:
    petlist.ensure_first()
    for p in petlist.load_pets():
        start_pet(p.get("id"))


def kill_pid(pid: int) -> bool:
    """杀一个桌宠进程 —— **本进程一律跳过**。

    为什么要有这道闸：单实例桌宠、以及"进程内 new 出来的 DeskPet"（测试脚本、
    以后可能的控制台内预览）都会把自己的 pid 写进 pets.json / pet.pid。
    如果那正好是**当前进程**的 pid，照杀就是自己把自己干掉 ——
    进程静默退出、没有堆栈、退出码还是 0（这个坑踩了两次：test-sounds 和 test-bond）。"""
    if not pid:
        return False
    if int(pid) == os.getpid():
        print("[petctl] pet.pid 指向本进程，跳过（不自杀）", flush=True)
        return False
    h = kernel32.OpenProcess(PROCESS_TERMINATE, False, int(pid))
    if not h:
        return False
    kernel32.TerminateProcess(h, 0)
    kernel32.CloseHandle(h)
    return True


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
                               wintypes.LPARAM]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]


def stray_pet_pids() -> list:
    """找"没人管"的桌宠进程：桌面上开着标题为「桌宠」的窗口，但 pets.json / pet.pid 里都没有它。

    为什么需要它：老版本有个 bug —— 多实例也往 pet.pid 里写自己的 pid，
    控制台于是把"某只实例在跑"误判成"单宠物那只在跑"，改一次设置就多拉起一只。
    修好之后，用户桌面上可能还留着之前攒下来的孤儿，点「关闭所有桌宠」时应该真的一起收掉。"""
    out = []
    # 已知的桌宠 pid：pets.json 里的每一条 + pet.pid（单实例那只）+ 本进程自己。
    # 少了这一步会误伤：任何"进程内 new 出来的 DeskPet"（测试脚本、以后的控制台预览）
    # 都开着一个标题为「桌宠」的窗口，会被当成孤儿直接 TerminateProcess ——
    # 而且如果那个窗口属于**当前进程**，就是自己把自己杀掉（test-bond 就这么死的）。
    known = {os.getpid()}
    try:
        for p in petlist.load_pets():
            if p.get("pid"):
                known.add(int(p["pid"]))
        pid0, _ = read_pid_info()
        if pid0:
            known.add(int(pid0))
    except Exception:
        pass

    def cb(h, l):
        try:
            if not user32.IsWindowVisible(h):
                return True
            buf = ctypes.create_unicode_buffer(64)
            user32.GetWindowTextW(h, buf, 64)
            if buf.value == "桌宠":                     # 桌宠窗口的标题就是这两个字
                wp = wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
                if wp.value and int(wp.value) not in known:
                    out.append(int(wp.value))
        except Exception:
            pass
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return sorted(set(out))


def stop_all_pets() -> None:
    for p in petlist.load_pets():
        stop_pet(p.get("id"))
    stop_pet()          # 顺手把单宠物模式那只也收掉
    for pid in stray_pet_pids():      # 再扫一遍：历史遗留的孤儿也要收掉
        kill_pid(pid)


PROCESS_TERMINATE = 0x0001
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def stop_pet(pet_id: str | None = None) -> None:
    """优先只杀 pet.pid（或指定实例）里那个进程 —— 精准，不用冷启动 PowerShell。
    按名字扫全盘杀有误伤风险：这台机器上还跑着别的 python 程序（阿酉 review P1-3）。"""
    if pet_id:
        p = petlist.get_pet(pet_id) or {}
        pid = p.get("pid")
        if pid and pid_alive(int(pid)):
            kill_pid(int(pid))          # 内部有"不杀自己"的闸
        petlist.update_pet(pet_id, pid=None)
        return
    pid, _created = read_pid_info()
    if pid is None:
        return
    if pid_alive(pid):
        kill_pid(pid)                    # 内部有闸：pid 指向本进程就跳过（不自杀）
        for _ in range(30):              # 等她真的退干净再返回，不然紧接着 start 会撞车
            if not pid_alive(pid):
                break
            ui_sleep(0.05)
    try:
        PIDFILE.unlink()
    except Exception:
        pass
    return
    # 兜底：清理命令行里带 deskpet 的残留（例如手动启动过、pid 文件丢了）。
    # 打包后 tools/ 不一定随包，所以这条是非必需的。
    if KILLER.exists():
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(KILLER)],
                       capture_output=True, text=True, timeout=25, creationflags=CREATE_NO_WINDOW)
        time.sleep(0.4)


def startup_dir() -> Path:
    return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def autostart_on() -> bool:
    return (startup_dir() / "deskpet.lnk").exists()


def set_autostart(on: bool) -> None:
    lnk = startup_dir() / "deskpet.lnk"
    if on:
        # 开机启动的是控制台本身（带 --autostart）：它会把自己收进托盘并顺手拉起桌宠，
        # 这样开机后既有托盘图标可以开关，她也在桌面上。启动的都是 pythonw，不会有黑窗口。
        ps = ("$ws=New-Object -ComObject WScript.Shell;"
              "$l=$ws.CreateShortcut('" + str(lnk) + "');"
              "$l.TargetPath='" + str(PYW) + "';"
              "$l.Arguments='\"" + str(BASE / "petctl.pyw") + "\" --autostart';"
              "$l.WorkingDirectory='" + str(BASE) + "';"
              "$l.IconLocation='" + str(ICON) + "';$l.Save()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=25, creationflags=CREATE_NO_WINDOW)
    else:
        try:
            lnk.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------- 图像工具
def pil_to_pixmap(im) -> QPixmap:
    im = im.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    qimg = QImage(data, im.width, im.height, im.width * 4, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


def checker_image(size, cell=12):
    from PIL import Image, ImageDraw
    w, h = size
    q = Image.new("RGB", (w, h), (236, 236, 236))
    d = ImageDraw.Draw(q)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if ((x // cell) + (y // cell)) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(204, 204, 204))
    return q


def preview_over_checker(im, box) -> QPixmap:
    t = im.copy()
    t.thumbnail(box, 1)
    bg = checker_image(t.size)
    bg.paste(t, (0, 0), t)
    return pil_to_pixmap(bg)


# ---------------------------------------------------------------- 上传对话框
class ImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        import petmaker
        self.petmaker = petmaker
        self.path: Path | None = None
        self.views: list = []
        self._gen = 0            # 代数：每发起一次处理就 +1，回来的旧结果直接丢
        self._busy_work = False  # 有任务在跑（按钮禁用、预览显示"处理中"）
        self.setWindowTitle("添加新桌宠")
        self.setStyleSheet(QSS)
        self.setFixedWidth(460)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(9)

        tip = QLabel("选一张角色图。要求：一个角色、背景干净（纯色/白底最好）、人物完整不被裁切。\n"
                     "支持 PNG / JPG / WebP / BMP / GIF / TIFF，单边不超过 4096px，文件不超过 24MB。")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        root.addWidget(tip)

        # 选完图先给"这张图适不适合"的结论 —— 选错图是白块问题的根源，
        # 与其事后硬抠，不如事前说清楚。
        self.lb_grade = QLabel("")
        self.lb_grade.setWordWrap(True)
        self.lb_grade.setStyleSheet(
            "QLabel{background:#141b2e;border:1px solid #2c3a58;border-radius:6px;"
            "padding:8px;color:#c8d4f0}")
        self.lb_grade.hide()
        root.addWidget(self.lb_grade)

        row = QHBoxLayout()
        self.btn_pick = QPushButton("选择图片…")
        self.btn_pick.clicked.connect(self.pick)
        row.addWidget(self.btn_pick)
        self.lb_path = QLabel("还没选")
        self.lb_path.setObjectName("hint")
        row.addWidget(self.lb_path, 1)
        root.addLayout(row)

        # —— 额外姿势 / 动图（可选）：每类动作可以给一张不同的图，
        #    给动图（GIF/APNG/动态 WebP）就直接用它的帧，连抠图都不用做。
        root.addWidget(self._lab("额外姿势 / 动图（可选，不给就自动生成）"))
        self.slot_paths = {"jumping": None, "running": None}
        self.slot_labels = {}
        for key, title in (("jumping", "点击反馈"), ("running", "拖拽 / 走动")):
            r0 = QHBoxLayout()
            lab = QLabel(title)
            lab.setObjectName("status")
            lab.setFixedWidth(74)
            r0.addWidget(lab)
            lb = QLabel("（自动生成）")
            lb.setObjectName("hint")
            self.slot_labels[key] = lb
            r0.addWidget(lb, 1)
            b1 = QPushButton("选择")
            b1.clicked.connect(lambda _=False, k=key: self.pick_slot(k))
            r0.addWidget(b1)
            b2 = QPushButton("清除")
            b2.clicked.connect(lambda _=False, k=key: self.clear_slot(k))
            r0.addWidget(b2)
            root.addLayout(r0)
        hint2 = QLabel("支持 GIF / APNG / 动态 WebP —— 动图的每一帧会直接当动画用，不做抠图。"
                       "透明底的动图效果最好；如果动图本身带场景背景，也会原样显示"
                       "（看起来像一张会动的贴纸）。")
        hint2.setObjectName("hint")
        hint2.setWordWrap(True)
        root.addWidget(hint2)

        body = QHBoxLayout()
        self.lb_preview = QLabel()
        self.lb_preview.setFixedSize(230, 300)
        self.lb_preview.setAlignment(Qt.AlignCenter)
        self.lb_preview.setStyleSheet("background:#0b1020;border:1px solid #2c3a58;border-radius:6px")
        body.addWidget(self.lb_preview)
        col = QVBoxLayout()
        col.addWidget(self._lab("角色（一张图里有多个角色时选哪个）"))
        self.cb_view = QComboBox()
        self.cb_view.currentIndexChanged.connect(self.refresh_preview)
        col.addWidget(self.cb_view)
        col.addWidget(self._lab("抠图方式"))
        self.cb_cut = QComboBox()
        for label, val in CUT_MODES:
            if LITE_MODE and val == "ai":
                continue                     # 精简版没有 AI 链，别给用户一个点了报错的选项
            self.cb_cut.addItem(label, val)
        self.cb_cut.currentIndexChanged.connect(self.reload)
        col.addWidget(self.cb_cut)
        col.addWidget(self._lab("夹缝清理（发丝缝 / 脖子边的空隙）"))
        self.cb_gap = QComboBox()
        for label, val in GAP_LEVELS:
            self.cb_gap.addItem(label, val)
        self.cb_gap.setCurrentIndex(2)
        self.cb_gap.currentIndexChanged.connect(self.on_gap_changed)
        col.addWidget(self.cb_gap)
        col.addWidget(self._lab("抠图强度（只有快速算法用得上）"))
        self.cb_strength = QComboBox()
        for label, val in STRENGTHS:
            self.cb_strength.addItem(label, val)
        self.cb_strength.setCurrentIndex(1)
        self.cb_strength.currentIndexChanged.connect(self.reload)
        col.addWidget(self.cb_strength)
        col.addWidget(self._lab("动态档位"))
        self.cb_motion = QComboBox()
        for label, val in MOTION_MODES:
            self.cb_motion.addItem(label, val)
        self.cb_motion.setCurrentIndex(2)
        col.addWidget(self.cb_motion)
        col.addWidget(self._lab("名字"))
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("给她起个名字")
        col.addWidget(self.ed_name)
        col.addStretch(1)
        body.addLayout(col, 1)
        root.addLayout(body)

        self.lb_info = QLabel("")
        self.lb_info.setObjectName("hint")
        self.lb_info.setWordWrap(True)
        root.addWidget(self.lb_info)

        btns = QHBoxLayout()
        btns.addStretch(1)
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        btns.addWidget(b_cancel)
        self.b_ok = QPushButton("生成桌宠")
        self.b_ok.setEnabled(False)
        self.b_ok.clicked.connect(self.accept_import)
        btns.addWidget(self.b_ok)
        root.addLayout(btns)

    def _lab(self, t):
        lab = QLabel(t)
        lab.setObjectName("status")
        return lab

    def pick_slot(self, key):
        f, _ = QFileDialog.getOpenFileName(
            self, "给「%s」选一张图（可以是动图）" % key, str(Path.home()),
            "图片 (*.png *.jpg *.jpeg *.webp *.gif *.bmp *.apng)")
        if not f:
            return
        self.slot_paths[key] = Path(f)
        try:
            seq, durs = self.petmaker.load_sequence(Path(f))
            tag = "动图 %d 帧" % len(seq) if len(seq) > 1 else "静态图"
        except Exception as e:
            tag = "读不了：" + str(e)[:40]
        self.slot_labels[key].setText(self.slot_paths[key].name + "（" + tag + "）")

    def clear_slot(self, key):
        self.slot_paths[key] = None
        self.slot_labels[key].setText("（自动生成）")

    def on_gap_changed(self):
        self._gap_touched = True      # 用户自己动过就不再自动改
        self.reload()

    def pick(self):
        self._gap_touched = False
        f, _ = QFileDialog.getOpenFileName(
            self, "选择角色图片", str(Path.home()),
            "图片 (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff)")
        if not f:
            return
        self.path = Path(f)
        self._anim_frames = None
        self._anim_durs = None
        self.lb_path.setText(self.path.name)
        if not self.ed_name.text().strip():
            self.ed_name.setText(self.path.stem[:20])
        self.reload()

    def reject(self):
        """关掉对话框 = 放弃这次上传。代数推一格，正在跑的任务回来时会被丢掉，
        免得往一个已经关掉的窗口上写东西（也就不用等 AI 跑完才能关窗口）。"""
        self._gen += 1
        super().reject()

    def closeEvent(self, event):
        self._gen += 1
        super().closeEvent(event)

    # ------------------------------------------------------ 上传：忙碌状态 / 日志
    def _log(self, msg: str) -> None:
        """上传流水线原来一条日志都不打，卡住了完全没法事后定位（阿酉 BUG 卡 §4）。
        这里按 ctl.log 的风格记：每一步的耗时下次直接能看。"""
        try:
            d = BASE / "logs"
            d.mkdir(exist_ok=True)
            with open(d / "ctl.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%H:%M:%S") + "  " + msg + chr(10))
        except Exception:
            pass

    def _set_busy(self, on: bool, text: str = "") -> None:
        """处理中就把按钮禁掉、预览区写"处理中"，而不是用 setOverrideCursor ——
        override cursor 是全局栈，和"多线程 + 嵌套事件循环"混用容易留下永久沙漏。"""
        self._busy_work = on
        self.btn_pick.setEnabled(not on)
        self.ed_name.setEnabled(not on)
        if on:
            self.lb_preview.setPixmap(QPixmap())
            self.lb_preview.setText(text or "处理中…")
            self.b_ok.setEnabled(False)
        else:
            self.b_ok.setEnabled(bool(self.views))

    def reload(self):
        if self.path is None:
            return
        try:
            # 动图：不做抠图 —— 直接用它的帧。动画贴纸基本都自带透明底。
            try:
                seq, durs = self.petmaker.load_sequence(self.path)
            except Exception:
                seq, durs = [], None
            if len(seq) > 1:
                self._gen += 1                       # 作废还在跑的抠图任务
                self._anim_frames, self._anim_durs = seq, durs
                self.views = [seq[0]]
                self._warnings = []
                self._info = {"mode": "anim", "frames": len(seq)}
                self.lb_grade.setStyleSheet(
                    "QLabel{background:#122a20;border:1px solid #3fbf7f;border-radius:6px;padding:9px;}")
                self.lb_grade.setText(
                    "<b style='color:#5fe0a0'>✔ 检测到动图（%d 帧）</b><br>"
                    "<span style='color:#9fb0d9'>· 会直接拿它的帧当待机动画，<b>不需要抠图</b></span><br>"
                    "<span style='color:#e8eeff'>→ 这是效果最好的上传方式：动画贴纸通常本来就是透明底</span>"
                    % len(seq))
                self.lb_grade.show()
                self.cb_view.blockSignals(True)
                self.cb_view.clear()
                self.cb_view.addItem("动图")
                self.cb_view.blockSignals(False)
                self._after_load()
                return
            self._anim_frames = None
            self._anim_durs = None
        except Exception:
            self._anim_frames = None
            self._anim_durs = None
        # 重活（分析 + 抠图 + 切角色）丢到工作线程，主线程立刻返回 —— 界面全程能拖能点
        self._gen += 1
        gen = self._gen
        mode = self.cb_cut.currentData()
        gap = self.cb_gap.currentData()
        strength = self.cb_strength.currentData()
        self._log("上传: 开始处理 gen=%d 文件=%s 抠图方式=%s" % (gen, self.path.name, mode))
        self._set_busy(True, "正在处理…\n（第一次用 AI 抠图要加载模型，可能要几十秒）")
        start_import_job(lambda: self._work_cut(mode, gap, strength),
                         lambda payload, g=gen: self._on_cut_done(g, payload),
                         lambda msg, g=gen: self._on_cut_failed(g, msg))

    # ------------------------------------------------------ 上传：工作线程里跑的活
    def _work_cut(self, mode: str, gap: str, strength: str) -> dict:
        """**只碰 PIL / numpy / 文件**，绝不碰 Qt 对象（这是工作线程）。"""
        t0 = time.time()
        if mode == "none":
            # 不抠图：原图什么样，桌宠就什么样。
            # 自动抠图对"角色和背景颜色接近 / 本来就是场景图"的图原理上就分不开，
            # 与其让用户跟边缘较劲，不如给一个"直接用"的出口。
            from PIL import Image as _Image
            src = _Image.open(self.path).convert("RGBA")
            return {"views": self.petmaker.split_views(src, 3) or [src],
                    "warnings": [], "info": {"mode": "none"}, "seconds": time.time() - t0}
        suit = self.petmaker.suitability(self.path)
        if not suit["info"].get("ok", True):
            return {"invalid": "；".join(suit["info"].get("warnings", []))}
        if mode == "ai":
            ok_ai, why = self.petmaker.ai_status()
            if not ok_ai:
                return {"no_ai": why}
            res = self.petmaker.cutout_ai(self.path, max_side=1600, gap_level=gap)
        else:
            res = self.petmaker.cutout(self.path, strength, max_side=1600)
        return {"views": self.petmaker.split_views(res.image, 3) or [res.image],
                "warnings": list(res.warnings), "info": res.info, "grade": suit,
                "seconds": time.time() - t0}

    def _on_cut_done(self, gen: int, payload: dict) -> None:
        if gen != self._gen:
            self._log("上传: 丢弃过期结果 gen=%d（当前 %d）" % (gen, self._gen))
            return
        self._set_busy(False)
        self._log("上传: 处理完成 gen=%d 用时 %.1fs 模式=%s"
                  % (gen, payload.get("seconds", 0), payload.get("info", {}).get("mode")))
        if "invalid" in payload:
            self.lb_info.setText("不能使用：" + payload["invalid"])
            self.lb_preview.setText("")
            self.b_ok.setEnabled(False)
            return
        if "no_ai" in payload:
            if LITE_MODE:
                self.lb_info.setText(
                    "这个版本<b>不含 AI 抠图</b>。最省事的办法：先用任意抠图工具"
                    "（手机相册自带的都行）出一张<b>透明底的 PNG</b>再上传，"
                    "一个白块都不会有。或者改用下面的「快速算法」。")
            else:
                self.lb_info.setText("AI 抠图组件异常：" + payload["no_ai"] + "（可改用快速算法）")
            self.b_ok.setEnabled(False)
            return
        self.views = payload["views"]
        self._warnings = payload["warnings"]
        self._info = payload["info"]
        if payload["info"].get("mode") == "none":
            self.lb_grade.setStyleSheet(
                "QLabel{background:#1b2334;border:1px solid #6f8fd0;border-radius:6px;padding:9px;}")
            self.lb_grade.setText(
                "<b style='color:#9ecbff'>● 不抠图：原图直接用</b><br>"
                "<span style='color:#9fb0d9'>· 背景会一起显示（桌宠会是一块方形/原图轮廓）</span><br>"
                "<span style='color:#e8eeff'>→ 想要干净边缘：先用手机相册或任意抠图工具"
                "出一张<b>透明底 PNG</b>，再用「智能 AI」</span>")
            self.lb_grade.show()
        else:
            self._show_grade(payload["grade"])
        self._after_load()

    def _on_cut_failed(self, gen: int, msg: str) -> None:
        if gen != self._gen:
            return
        self._set_busy(False)
        self._log("上传: 处理失败 gen=%d %s" % (gen, msg))
        self.lb_info.setText("处理失败：" + msg)
        self.lb_preview.setText("")
        self.b_ok.setEnabled(False)

    def _after_load(self):
        self.cb_view.blockSignals(True)
        self.cb_view.clear()
        if getattr(self, "_anim_frames", None):
            self.cb_view.addItem("动图（%d 帧）" % len(self._anim_frames))
        else:
            for i in range(len(self.views)):
                self.cb_view.addItem("第 %d 个角色" % (i + 1))
        self.cb_view.setCurrentIndex(0)
        self.cb_view.blockSignals(False)
        self.refresh_preview()

    GRADE_STYLE = {
        "A": ("#12301f", "#4ad07a", "✔"),
        "B": ("#1a2a1a", "#9ad06a", "●"),
        "C": ("#33260f", "#e8b04a", "▲"),
        "D": ("#331218", "#ff6b7a", "✘"),
    }

    def _show_grade(self, suit):
        bg, fg, mark = self.GRADE_STYLE.get(suit["grade"], self.GRADE_STYLE["B"])
        html = ("<b style='color:%s'>%s 这张图：%s</b><br>" % (fg, mark, suit["label"]))
        # 角色自己有大片接近背景色的区域时，自动把夹缝清理关掉 —— 这类图清理必然误伤
        ratio = (suit.get("info") or {}).get("near_bg_ratio", 0.0)
        if not getattr(self, "_gap_touched", False):
            want = 0 if ratio > 0.18 else 2
            if self.cb_gap.currentIndex() != want:
                self.cb_gap.blockSignals(True)
                self.cb_gap.setCurrentIndex(want)
                self.cb_gap.blockSignals(False)
                if want == 0:
                    html += ("<span style='color:#9fb0d9'>· 已自动把「夹缝清理」设为关闭 —— "
                             "这类图开清理会把浅色部分一起清掉</span><br>")
        for r in suit["reasons"]:
            html += "<span style='color:#9fb0d9'>· " + r + "</span><br>"
        for a in suit["advice"]:
            html += "<span style='color:#e8eeff'>→ " + a + "</span><br>"
        if suit["grade"] in ("C", "D"):
            html += ("<span style='color:#9fb0d9'>· 抠不干净也不必勉强：把「抠图方式」"
                     "改成<b>不抠图</b>就能直接用原图，或者先抠好再传。</span><br>")
        self.lb_grade.setText(html)
        self.lb_grade.setStyleSheet(
            "QLabel{background:%s;border:1px solid %s;border-radius:6px;padding:9px;}" % (bg, fg))
        self.lb_grade.show()

    def refresh_preview(self):
        if not self.views:
            return
        i = max(0, min(self.cb_view.currentIndex(), len(self.views) - 1))
        v = self.views[i]
        self.lb_preview.setPixmap(preview_over_checker(v, (222, 292)))
        s, band = self.petmaker.halo_score(v, want_band=True)
        msgs = list(getattr(self, "_warnings", []))
        info = getattr(self, "_info", {})
        detail = "角色 %dx%d" % v.size
        if info.get("mode") == "ai":
            detail += "　AI 模型：" + str(info.get("model"))
        elif info.get("mode") == "none":
            detail += "　不抠图，原图直接用"
        elif info.get("mode") == "alpha":
            detail += "　原图自带透明通道，直接使用"
        else:
            detail += "　背景色 %s，干净度 %.0f%%" % (info.get("bg"), 100 * info.get("bg_uniform", 0))
            detail += "　透明掉的夹缝 %d 处" % info.get("gaps_transparent", 0)
        detail += "　残留白边指标 %.3f（越低越干净）" % s
        if msgs:
            detail += "\n注意：" + "；".join(msgs)
        detail += "\n预览是棋盘格底 —— 白边和残留背景在这里一眼就能看出来。"
        self.lb_info.setText(detail)
        self.b_ok.setEnabled(True)

    def accept_import(self):
        if not self.views or self._busy_work:
            return
        i = max(0, min(self.cb_view.currentIndex(), len(self.views) - 1))
        img = self.views[i]
        name = self.ed_name.text().strip() or "我的桌宠"
        # 中文文件名 sanitize 之后可能只剩几个数字，那不算合法 id，退回时间戳
        pet_id = re.sub(r"[^a-z0-9]+", "-", self.path.stem.lower()).strip("-")[:24]
        if not re.search(r"[a-z]", pet_id):
            pet_id = "pet-" + time.strftime("%m%d%H%M%S")
        mode = self.cb_motion.currentData()
        anim = getattr(self, "_anim_frames", None)
        # 组槽位：待机（动图则整套帧 + 每帧时长；静态则用切好的立绘） + 用户额外给的姿势图
        slots = {"idle": anim or img}
        slot_ms = {}
        if anim and getattr(self, "_anim_durs", None) and len(self._anim_durs) == len(anim):
            slot_ms["idle"] = list(self._anim_durs)
        for tr in ("jumping", "running"):
            p = (self.slot_paths or {}).get(tr)
            if p:
                slots[tr] = p
        # 生成同样丢线程：110 帧动图要逐帧变换 + 落盘，在主线程里做照样会卡（阿酉 BUG 卡）
        self._gen += 1
        gen = self._gen
        self._log("上传: 开始生成 gen=%d 档位=%s 待机帧数=%s"
                  % (gen, mode, len(anim) if anim else 1))
        self._set_busy(True, "正在生成桌宠…")
        start_import_job(lambda: self._do_generate(slots, mode, pet_id, name, slot_ms),
                         lambda res, g=gen: self._on_generate_done(g, res),
                         lambda msg, g=gen: self._on_generate_failed(g, msg))

    def _do_generate(self, slots: dict, mode: str, pet_id: str, name: str,
                     slot_ms: dict) -> dict:
        """生成 + 落盘（同样在工作线程里，不碰 Qt）。"""
        t0 = time.time()
        tracks, ms = self.petmaker.build_from_slots(slots, mode, slot_ms=slot_ms)
        final = self.petmaker.frames_to_files(tracks, self.petmaker.TARGET_H)
        # frames_to_files 只裁剪缩放、不改帧数，所以时长数组可以直接沿用；
        # install 里还有一道 len(per) == len(names) 的兜底，对不上就退回默认节奏。
        self.petmaker.install(paths.asset_root_for_write(), pet_id, final, ms=ms)
        names = load_names()
        names["user/" + pet_id] = name
        save_names(names)
        return {"pet_id": "user/" + pet_id, "seconds": time.time() - t0,
                "tracks": {k: len(v) for k, v in final.items()},
                "ms_lens": {k: len(v) for k, v in (ms or {}).items()}}

    def _on_generate_done(self, gen: int, res: dict) -> None:
        if gen != self._gen:
            self._log("上传: 丢弃过期的生成结果 gen=%d（当前 %d）" % (gen, self._gen))
            return
        self._log("上传: 生成完成 gen=%d 用时 %.1fs 轨道=%s 时长数组=%s"
                  % (gen, res["seconds"], res["tracks"], res["ms_lens"]))
        self.pet_id = res["pet_id"]
        self.accept()

    def _on_generate_failed(self, gen: int, msg: str) -> None:
        if gen != self._gen:
            return
        self._set_busy(False)
        self._log("上传: 生成失败 gen=%d %s" % (gen, msg))
        self.lb_info.setText("生成失败：" + msg)


# ---------------------------------------------------------------- 上传用的工作线程
# 阿酉 BUG 卡（P0）：上传流水线原来整条跑在 GUI 线程里。完整版第一次用 AI 抠图要
# 加载 168MB 模型（10~60 秒），Windows 超过约 5 秒不处理消息就把窗口标成"未响应"，
# 用户看到的就是"一上传角色控制台就卡死"。
# 现在把 analyze / cutout / split_views / make_frames 全丢到**单线程池**里：
#   · 单线程 → 天然串行，rembg 的 session 不用加锁，也不会几个任务一起抢内存；
#   · 结果回主线程时用"代数(gen)"对账 → 用户连切档位时，过期结果直接丢掉，不会串图。
_IMPORT_POOL = QThreadPool()
_IMPORT_POOL.setMaxThreadCount(1)


# 保活表：PySide6 里把 QRunnable 交给 QThreadPool 之后，如果 Python 这边不持有引用，
# 这个对象（连同它的信号对象）会被回收 —— 表现是"任务跑了、结果永远回不来"。
# 实测：不留引用时 done 信号一次都收不到（tools/probe-job.py 里就是这个对照实验）。
_IMPORT_JOBS: list = []


class _ImportJob(QRunnable):
    """把一段不碰 Qt 的重活丢到工作线程，结果用信号送回主线程。"""

    class _Sig(QObject):
        done = Signal(object)
        failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn
        self.sig = _ImportJob._Sig()

    def run(self):
        try:
            self.sig.done.emit(self._fn())
        except Exception as e:                       # noqa: BLE001
            traceback.print_exc()
            self.sig.failed.emit(str(e))


def start_import_job(fn, on_done, on_fail) -> None:
    """起一个上传任务：结果回主线程；任务对象保活到结果送达为止。"""
    job = _ImportJob(fn)
    _IMPORT_JOBS.append(job)

    def _drop(*_a):
        # 闭包持有 job，所以清理表也不会让它在中途被回收
        try:
            _IMPORT_JOBS.remove(job)
        except ValueError:
            pass

    job.sig.done.connect(_drop)
    job.sig.failed.connect(_drop)
    job.sig.done.connect(on_done)
    job.sig.failed.connect(on_fail)
    _IMPORT_POOL.start(job)


def to_color(c) -> QColor:
    """QColor 不接受 list —— [r,g,b] 要手动展开（踩过：QVariant must be holding a QColor）"""
    if isinstance(c, (list, tuple)):
        return QColor(int(c[0]), int(c[1]), int(c[2]))
    return QColor(c)


BUBBLE_DIR = paths.data_root() / "assets" / "bubbles"   # 用户加的图片气泡写数据目录
DEFAULT_LINES = ["呀——被摸头了～", "再摸一下也不是不行", "唔，痒痒的", "今天也要加油哦！",
                 "我一直在这儿呢", "你忙你的，我看着", "这一下，记在小本本上了",
                 "摸摸可以，小鱼干更好", "我在听呢，你说", "呼——差点没站稳"]


class BubbleEditor(QDialog):
    """点击台词编辑器：可以加任意多条文字，也可以放图片，点她的时候随机挑一条。"""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = [dict(x) for x in items]
        self.setWindowTitle("点击台词")
        self.setStyleSheet(QSS)
        self.setMinimumWidth(460)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(9)

        tip = QLabel("点她的时候从下面这些里随机挑一条。可以是文字，也可以是图片（会显示在对话框里）。\n"
                     "全部删光就等于用内置台词。")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        root.addWidget(tip)

        self.list = QListWidget()
        self.list.setMinimumHeight(240)
        self.list.setStyleSheet("QListWidget{background:#131c36;border:1px solid #2c3a58;border-radius:6px}")
        root.addWidget(self.list)

        row = QHBoxLayout()
        b_txt = QPushButton("＋ 文字")
        b_txt.clicked.connect(self.add_text)
        row.addWidget(b_txt)
        b_img = QPushButton("＋ 图片")
        b_img.clicked.connect(self.add_image)
        row.addWidget(b_img)
        b_edit = QPushButton("编辑")
        b_edit.clicked.connect(self.edit_item)
        row.addWidget(b_edit)
        b_del = QPushButton("删除")
        b_del.clicked.connect(self.del_item)
        row.addWidget(b_del)
        b_reset = QPushButton("恢复内置")
        b_reset.clicked.connect(self.reset_default)
        row.addWidget(b_reset)
        row.addStretch(1)
        root.addLayout(row)

        btns = QHBoxLayout()
        btns.addStretch(1)
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        btns.addWidget(b_cancel)
        b_ok = QPushButton("保存")
        b_ok.clicked.connect(self.accept)
        btns.addWidget(b_ok)
        root.addLayout(btns)
        self._refresh()

    def _refresh(self):
        self.list.clear()
        if not self.items:
            self.list.addItem("（空 —— 使用内置台词）")
            return
        for it in self.items:
            if it.get("type") == "image":
                self.list.addItem("［图片］ " + str(it.get("file", "")))
            else:
                self.list.addItem("［文字］ " + str(it.get("text", "")))

    def _current(self):
        i = self.list.currentRow()
        return i if 0 <= i < len(self.items) else -1

    def add_text(self):
        from PySide6.QtWidgets import QInputDialog
        t, ok = QInputDialog.getText(self, "加一条文字", "她冒出来的话：")
        if ok and t.strip():
            self.items.append({"type": "text", "text": t.strip()})
            self._refresh()

    def add_image(self):
        f, _ = QFileDialog.getOpenFileName(self, "选一张图片（会显示在对话框里）", str(Path.home()),
                                           "图片 (*.png *.jpg *.jpeg *.webp *.gif *.bmp)")
        if not f:
            return
        src = Path(f)
        BUBBLE_DIR.mkdir(parents=True, exist_ok=True)
        # 统一缩到不超过 480px，避免气泡里塞一张 4K 图
        try:
            from PIL import Image as _I
            im = _I.open(src).convert("RGBA")
            if max(im.size) > 480:
                k = 480 / float(max(im.size))
                im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), _I.LANCZOS)
            name = "bub-" + time.strftime("%m%d%H%M%S") + ".png"
            im.save(BUBBLE_DIR / name)
        except Exception:
            name = "bub-" + time.strftime("%m%d%H%M%S") + src.suffix.lower()
            shutil.copy2(src, BUBBLE_DIR / name)
        self.items.append({"type": "image", "file": "bubbles/" + name})
        self._refresh()

    def edit_item(self):
        i = self._current()
        if i < 0 or self.items[i].get("type") != "text":
            return
        from PySide6.QtWidgets import QInputDialog
        t, ok = QInputDialog.getText(self, "改这条文字", "她冒出来的话：", text=self.items[i].get("text", ""))
        if ok and t.strip():
            self.items[i]["text"] = t.strip()
            self._refresh()

    def del_item(self):
        i = self._current()
        if i >= 0:
            self.items.pop(i)
            self._refresh()

    def reset_default(self):
        self.items = []
        self._refresh()


class ColorButton(QPushButton):
    """一个显示当前颜色、点开取色器的按钮。"""
    def __init__(self, color, on_change):
        super().__init__()
        self._c = to_color(color)
        self._cb = on_change
        self.setFixedSize(52, 22)
        self.clicked.connect(self._pick)
        self._sync()

    def _sync(self):
        self.setStyleSheet("QPushButton{background:%s;border:1px solid #5a6a90;border-radius:5px;}"
                           "QPushButton:hover{border-color:#4d6bfe;}" % self._c.name())

    def color(self):
        return self._c

    def set_color(self, c):
        self._c = to_color(c)
        self._sync()

    def _pick(self):
        c = QColorDialog.getColor(self._c, self, "选择颜色")
        if c.isValid():
            self._c = c
            self._sync()
            self._cb()


class BubblePreview(QWidget):
    """按桌宠同样的画法画一个示例气泡，改颜色即时可见。"""
    def __init__(self):
        super().__init__()
        self.setFixedHeight(52)
        self.bg = QColor(19, 28, 54)
        self.fg = QColor(234, 239, 255)
        self.border = QColor(126, 152, 255)

    def set_colors(self, bg, fg, border):
        self.bg, self.fg, self.border = to_color(bg), to_color(fg), to_color(border)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        text = "今天也要加油哦！"
        f = QFont("Microsoft YaHei UI", 10)
        p.setFont(f)
        fm = QFontMetrics(f)
        bw = fm.horizontalAdvance(text) + 26
        bh = fm.height() + 12
        x = (self.width() - bw) / 2.0
        y = 6.0
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        path.addRoundedRect(QRectF(x, y, bw, bh), bh / 2, bh / 2)
        cx = self.width() / 2.0
        path.moveTo(cx - 7, y + bh - 1)
        path.lineTo(cx, y + bh + 7)
        path.lineTo(cx + 7, y + bh - 1)
        path.closeSubpath()
        top = QColor(min(255, int(self.bg.red() * 1.45 + 18)),
                     min(255, int(self.bg.green() * 1.45 + 18)),
                     min(255, int(self.bg.blue() * 1.45 + 18)))
        g = QLinearGradient(0, y, 0, y + bh)
        g.setColorAt(0.0, top)
        g.setColorAt(1.0, self.bg)
        p.setPen(self.border)
        p.setBrush(QBrush(g))
        p.drawPath(path)
        p.setPen(self.fg)
        p.drawText(QRectF(x, y, bw, bh), Qt.AlignCenter, text)


QSS = """
QWidget { background:#0f1524; color:#e8eeff; font-family:'Microsoft YaHei UI'; font-size:12px; }
QLabel#title { font-size:15px; font-weight:600; color:#ffffff; }
QLabel#status { color:#9fb0d9; }
QLabel#hint { color:#6f80a8; font-size:11px; }
QPushButton#toggle { background:#4d6bfe; border:none; border-radius:8px; padding:12px;
                     font-size:14px; font-weight:600; color:white; }
QPushButton#toggle:hover { background:#5f7bff; }
QPushButton#toggle[on="false"] { background:#2a3550; color:#9fb0d9; }
QPushButton { background:#1b2438; border:1px solid #2c3a58; border-radius:6px; padding:6px 10px; }
QPushButton:hover { border-color:#4d6bfe; }
QPushButton:disabled { color:#55617f; border-color:#242f47; }
QComboBox, QLineEdit { background:#1b2438; border:1px solid #2c3a58; border-radius:6px; padding:5px 8px; }
QComboBox QAbstractItemView { background:#131c36; selection-background-color:#4d6bfe; }
QRadioButton, QCheckBox { padding:3px 0; }
QFrame#sep { background:#222d45; max-height:1px; }
"""


GEOM_FILE = paths.data_root() / "ui.json"


class Console(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("桌宠控制台")
        self.setWindowIcon(QIcon(str(ICON)))
        self.setStyleSheet(QSS)
        self._build()
        self._build_tray()
        self._fit_to_screen()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    # ------------------------------------------------------------ 窗口尺寸
    def _fit_to_screen(self) -> None:
        """保证整个窗口都在屏幕里。

        这之前是个真问题：功能越加越多，内容需要 1006px，而 1080p 屏的可用高度只有 912px，
        底部的按钮直接被切到屏幕外，用户既滚不动也拖不上来。现在：
          ① 内容放进滚动区（装不下就能滚）；
          ② 高度按可用屏幕高度夹住（还留 90px 给任务栏和标题栏）；
          ③ 尺寸和位置记进 ui.json，下次原样打开。
        """
        scr = QApplication.primaryScreen().availableGeometry()
        self.setMinimumWidth(340)
        self.setMaximumWidth(560)
        h_cap = max(360, scr.height() - 60)
        # 量内容高度要用滚动区里那个 inner 的 sizeHint，
        # 直接量 Console 拿到的是滚动区自己的（永远很小）
        try:
            content_h = self.scroll.widget().sizeHint().height()
        except Exception:
            content_h = self.sizeHint().height()
        want_w, want_h = 380, min(content_h, h_cap)
        geo = {}
        try:
            geo = json.loads(GEOM_FILE.read_text(encoding="utf-8"))
        except Exception:
            geo = {}
        w = int(geo.get("w", want_w)) if geo else want_w
        h = int(geo.get("h", want_h)) if geo else want_h
        w = max(340, min(w, 560))
        h = max(360, min(h, h_cap))
        x = geo.get("x")
        y = geo.get("y")
        if x is None or y is None:
            x = scr.right() - w - 60
            y = scr.top() + max(20, (scr.height() - h) // 2)
        x = max(scr.left(), min(int(x), scr.right() - w))
        y = max(scr.top(), min(int(y), scr.bottom() - h))
        self.setGeometry(int(x), int(y), w, h)
        print("控制台 %dx%d（内容需要 %dpx，可用 %dpx）" % (w, h, content_h, scr.height()),
              flush=True)

    def _save_geometry(self) -> None:
        try:
            paths.atomic_write_text(GEOM_FILE, json.dumps(
                {"x": self.x(), "y": self.y(), "w": self.width(), "h": self.height()},
                ensure_ascii=False))
        except Exception:
            pass

    def _build(self):
        # 外层只放一个滚动区，内容全塞进 inner —— 任何分辨率下都不会有"够不到的按钮"
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none}"
                                  "QScrollBar:vertical{background:#131c36;width:10px;border-radius:5px}"
                                  "QScrollBar::handle:vertical{background:#3a4a70;border-radius:5px;min-height:30px}"
                                  "QScrollBar::add-line,QScrollBar::sub-line{height:0}")
        inner = QWidget()
        inner.setObjectName("inner")
        inner.setStyleSheet("QWidget#inner{background:#0f1524}")
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll)

        root = QVBoxLayout(inner)
        root.setContentsMargins(12, 12, 12, 10)
        root.setSpacing(6)

        t = QLabel("桌宠控制台")
        t.setObjectName("title")
        root.addWidget(t)
        self.status = QLabel("")
        self.status.setObjectName("status")
        root.addWidget(self.status)

        # —— 多桌宠：列表 + 每只单独控制 ——
        # 之前只有"一只"的世界观，但桌面上本来就可能同时站着好几只（各自都能跑），
        # 控制台却管不了它们。既然这样不如做成一等功能。
        self.petlist_widget = QListWidget()
        self.petlist_widget.setFixedHeight(78)
        self.petlist_widget.setStyleSheet(
            "QListWidget{background:#131c36;border:1px solid #2c3a58;border-radius:6px}"
            "QListWidget::item{padding:4px 6px}"
            "QListWidget::item:selected{background:#4d6bfe}")
        self.petlist_widget.itemSelectionChanged.connect(self._on_pet_selected)
        root.addWidget(self.petlist_widget)

        rowp = QHBoxLayout()
        b_tog = QPushButton("显示 / 隐藏")
        b_tog.clicked.connect(self.on_toggle_selected)
        rowp.addWidget(b_tog)
        b_rm = QPushButton("移除")
        b_rm.clicked.connect(self.on_remove_pet)
        rowp.addWidget(b_rm)
        b_all = QPushButton("全部关闭")
        b_all.clicked.connect(self.on_stop_all)
        rowp.addWidget(b_all)
        root.addLayout(rowp)

        self.toggle = QPushButton("＋ 召唤一个桌宠")
        self.toggle.setObjectName("toggle")
        self.toggle.clicked.connect(self.on_add_pet)
        root.addWidget(self.toggle)

        # 伙伴绑定：给选中的那只挑一个"伴侣"，两只可以一起在桌面上转圈（简化版联动）
        rowb = QHBoxLayout()
        rowb.addWidget(self._lab("伴侣"))
        self.cb_bond = QComboBox()
        self.cb_bond.currentIndexChanged.connect(self.on_bond_change)
        rowb.addWidget(self.cb_bond, 1)
        # 转速挤在同一行里：控制台纵向空间紧张，能省一行是一行
        rowb.addWidget(self._lab("转速"))
        self.cb_bond_speed = QComboBox()
        for label, val in BOND_SPEEDS:
            self.cb_bond_speed.addItem(label, val)
        self.cb_bond_speed.setCurrentIndex(1)
        self.cb_bond_speed.setFixedWidth(72)
        self.cb_bond_speed.currentIndexChanged.connect(self.on_bond_opts)
        rowb.addWidget(self.cb_bond_speed)
        root.addLayout(rowb)

        rows = QHBoxLayout()
        self.btn_bond_play = QPushButton("一起转圈")
        self.btn_bond_play.setToolTip("两只围着同一个圆心转 20 秒（要靠在一起才看得见效果）")
        self.btn_bond_play.clicked.connect(self.on_bond_play)
        rows.addWidget(self.btn_bond_play)
        self.cb_bond_spin = QCheckBox("整只跟着翻转")
        self.cb_bond_spin.setToolTip("转圈时整个桌宠跟着转，转到半圈就是倒过来的（魔性来源）")
        self.cb_bond_spin.setChecked(True)
        self.cb_bond_spin.toggled.connect(self.on_bond_opts)
        rows.addWidget(self.cb_bond_spin, 1)
        root.addLayout(rows)
        root.addWidget(self._sep())

        root.addWidget(self._lab("显示层级"))
        self.rb_desktop = QRadioButton("只贴在壁纸上（露出壁纸时才看得见）")
        self.rb_top = QRadioButton("始终置顶（浮在所有窗口上面）")
        # 必须显式分组：Qt 的单选按钮默认按"同一个父控件"互斥，
        # 不分组的两个组会互相取消选中，每次刷新都触发一次 toggled —— 桌宠会被无限重启。
        self.grp_layer = QButtonGroup(self)
        self.grp_layer.addButton(self.rb_desktop)
        self.grp_layer.addButton(self.rb_top)
        self.rb_desktop.toggled.connect(self.on_layer)
        root.addWidget(self.rb_desktop)
        root.addWidget(self.rb_top)

        row = QHBoxLayout()
        row.addWidget(self._lab("形象"))
        self.cb_char = QComboBox()
        self.cb_char.currentIndexChanged.connect(self.on_char)
        row.addWidget(self.cb_char, 1)
        self.btn_add = QPushButton("＋ 上传")
        self.btn_add.clicked.connect(self.on_add)
        row.addWidget(self.btn_add)
        self.btn_del = QPushButton("删除")
        self.btn_del.clicked.connect(self.on_delete_char)
        row.addWidget(self.btn_del)
        root.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(self._lab("大小"))
        self.cb_scale = QComboBox()
        for label, val in SCALE_STEPS:
            self.cb_scale.addItem(label, val)
        self._custom_scale_item = False        # 下拉末尾是否有"自定义 xx%"那一项
        self.cb_scale.currentIndexChanged.connect(self.on_scale)
        row2.addWidget(self.cb_scale, 1)
        root.addLayout(row2)

        self.cb_sound = QCheckBox("开着音效")
        self.cb_sound.toggled.connect(self.on_sound)
        root.addWidget(self.cb_sound)

        # 音效绑定：按互动类型绑，每类可以绑多个（触发时随机播一个，和台词池一个思路）。
        # 默认折叠起来 —— 控制台内容已经 900px 出头了，这类"配一次就不动"的设置不该常驻占位。
        self.btn_sfx = QPushButton("互动音效（每类可绑多个，随机播一个）  ▸")
        self.btn_sfx.clicked.connect(self._toggle_sfx)
        root.addWidget(self.btn_sfx)
        self.sfx_box = QWidget()
        sfx_lay = QVBoxLayout(self.sfx_box)
        sfx_lay.setContentsMargins(0, 0, 0, 0)
        sfx_lay.setSpacing(4)
        self.sfx_box.setVisible(False)
        root.addWidget(self.sfx_box)
        self.sfx_status = {}
        for ev, label in SFX_EVENTS:
            r = QHBoxLayout()
            r.setSpacing(6)
            lab = QLabel(label)
            lab.setObjectName("status")
            lab.setFixedWidth(38)
            r.addWidget(lab)
            lb = QLabel("内置")
            lb.setObjectName("hint")
            self.sfx_status[ev] = lb
            r.addWidget(lb, 1)
            b1 = QPushButton("＋")
            b1.setFixedWidth(30)
            b1.setToolTip("添加 WAV 音效（可多选）")
            b1.clicked.connect(lambda _=False, e=ev: self.on_add_sound(e))
            b2 = QPushButton("▶")
            b2.setFixedWidth(30)
            b2.setToolTip("试听")
            b2.clicked.connect(lambda _=False, e=ev: self.on_preview_sound(e))
            b3 = QPushButton("清空")
            b3.setFixedWidth(48)
            b3.setToolTip("清空这一类的绑定，回到内置音效")
            b3.clicked.connect(lambda _=False, e=ev: self.on_clear_sound(e))
            for b in (b1, b2, b3):
                r.addWidget(b)
            sfx_lay.addLayout(r)
        root.addWidget(self._sep())
        root.addWidget(self._lab("行为"))
        # 两列排布，省一半纵向空间（一列排下来整个窗口会超出 1080p 屏）
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self.cb_roam = QCheckBox("自己在桌面溜达")
        self.cb_flee = QCheckBox("躲开鼠标")
        self.cb_inertia = QCheckBox("拖拽惯性")
        self.cb_recycle = QCheckBox("拖文件=回收站")
        for k, (cb, name) in enumerate(((self.cb_roam, "roam"), (self.cb_flee, "flee"),
                                        (self.cb_inertia, "inertia"),
                                        (self.cb_recycle, "recycle"))):
            cb.toggled.connect(lambda v, n=name: self._set_behavior(n, v))
            grid.addWidget(cb, k // 2, k % 2)
        root.addLayout(grid)
        root.addWidget(self._sep())

        self.cb_auto = QCheckBox("开机自动出现")
        self.cb_auto.toggled.connect(lambda v: set_autostart(bool(v)))
        root.addWidget(self.cb_auto)
        root.addWidget(self._sep())

        root.addWidget(self._lab("对话框（点她时头上冒出来的那个）"))
        self.rb_bub_auto = QRadioButton("跟随角色主色（自动）")
        self.rb_bub_custom = QRadioButton("自定义颜色")
        self.grp_bub = QButtonGroup(self)
        self.grp_bub.addButton(self.rb_bub_auto)
        self.grp_bub.addButton(self.rb_bub_custom)
        self.rb_bub_auto.toggled.connect(self.on_bubble_mode)
        root.addWidget(self.rb_bub_auto)
        root.addWidget(self.rb_bub_custom)
        rowc = QHBoxLayout()
        rowc.addWidget(self._lab("背景"))
        self.c_bg = ColorButton([19, 28, 54], self.on_bubble_color)
        rowc.addWidget(self.c_bg)
        rowc.addWidget(self._lab("文字"))
        self.c_fg = ColorButton([234, 239, 255], self.on_bubble_color)
        rowc.addWidget(self.c_fg)
        rowc.addWidget(self._lab("边框"))
        self.c_bd = ColorButton([126, 152, 255], self.on_bubble_color)
        rowc.addWidget(self.c_bd)
        rowc.addStretch(1)
        root.addLayout(rowc)
        self.preview = BubblePreview()
        root.addWidget(self.preview)
        rowb = QHBoxLayout()
        self.btn_bub = QPushButton("编辑点击台词…")
        self.btn_bub.clicked.connect(self.on_edit_bubbles)
        rowb.addWidget(self.btn_bub)
        self.lb_bub_count = QLabel("")
        self.lb_bub_count.setObjectName("hint")
        rowb.addWidget(self.lb_bub_count, 1)
        root.addLayout(rowb)
        root.addWidget(self._sep())

        hint = QLabel("左键拖动　·　点她有反应　·　Ctrl+滚轮 改大小　·　右键更多")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)
        row3 = QHBoxLayout()
        b_dir = QPushButton("打开文件夹")
        b_dir.clicked.connect(lambda: subprocess.Popen(["explorer", str(BASE)], creationflags=NO_WIN))
        row3.addWidget(b_dir)
        b_q = QPushButton("退出控制台")
        b_q.clicked.connect(self.on_quit)
        row3.addWidget(b_q)
        root.addLayout(row3)

    def _lab(self, t):
        lab = QLabel(t)
        lab.setObjectName("status")
        return lab

    def _sep(self):
        f = QFrame()
        f.setObjectName("sep")
        f.setFrameShape(QFrame.HLine)
        return f

    def _build_tray(self):
        self.tray = QSystemTrayIcon(QIcon(str(ICON)), self)
        self.tray.setToolTip("桌宠控制台")
        m = QMenu()
        self.act_show = QAction("召唤所有桌宠", self)
        self.act_show.triggered.connect(lambda: (start_all_pets(), time.sleep(0.6), self.refresh()))
        self.act_hide = QAction("关闭所有桌宠", self)
        self.act_hide.triggered.connect(lambda: (stop_all_pets(), ui_sleep(0.5), self.refresh()))
        a_console = QAction("打开控制台", self)
        a_console.triggered.connect(self.reveal)
        a_quit = QAction("退出控制台", self)
        a_quit.triggered.connect(self.on_quit)
        m.addAction(self.act_show)
        m.addAction(self.act_hide)
        m.addSeparator()
        m.addAction(a_console)
        m.addAction(a_quit)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: self.reveal() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()

    # ------------------------------------------------------------ 行为
    def refresh(self):
        # 同步界面期间一律忽略控件信号：只要漏掉一个，就会出现
        # "刷新 -> 控件变化 -> apply -> 重启桌宠 -> 再刷新" 的死循环。
        self._syncing = True
        try:
            self._refresh_inner()
        finally:
            self._syncing = False

    def _refresh_inner(self):
        petlist.ensure_first()
        pets = petlist.load_pets()
        names = dict(characters())
        sel = self._selected_pet()
        n_run = 0
        self.petlist_widget.blockSignals(True)
        self.petlist_widget.clear()
        for p in pets:
            pid = p.get("id")
            alive = pet_running(pid)
            n_run += 1 if alive else 0
            ch = p.get("character", "")
            label = "%s · (%d, %d) · %s" % (names.get(ch, ch), int(p.get("x", 0)),
                                            int(p.get("y", 0)),
                                            "● 运行中" if alive else "○ 未启动")
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, pid)
            self.petlist_widget.addItem(it)
        if self.petlist_widget.count():
            row = 0
            for i in range(self.petlist_widget.count()):
                if self.petlist_widget.item(i).data(Qt.UserRole) == sel:
                    row = i
                    break
            self.petlist_widget.setCurrentRow(row)
        self.petlist_widget.blockSignals(False)

        self.status.setText("● 桌面上有 %d 只（共 %d 只）" % (n_run, len(pets)) if pets
                            else "○ 还没有桌宠，点下面的按钮召唤一只")
        self.toggle.setText("＋ 召唤一个桌宠")
        self.act_show.setEnabled(n_run < len(pets))
        self.act_hide.setEnabled(n_run > 0)

        cfg = load_cfg()
        want = characters()
        if [self.cb_char.itemData(i) for i in range(self.cb_char.count())] != [v for _, v in want]:
            cur = cfg.get("character") or paths.DEFAULT_CHARACTER
            self.cb_char.blockSignals(True)
            self.cb_char.clear()
            for label, val in want:
                self.cb_char.addItem(label, val)
            i = self.cb_char.findData(cur)
            if i >= 0:
                self.cb_char.setCurrentIndex(i)
            self.cb_char.blockSignals(False)

        mode = cfg.get("mode", "desktop")
        self.rb_desktop.blockSignals(True)
        self.rb_top.blockSignals(True)
        self.rb_desktop.setChecked(mode != "topmost")
        self.rb_top.setChecked(mode == "topmost")
        self.rb_desktop.blockSignals(False)
        self.rb_top.blockSignals(False)

        # 没存过大小就用"这个形象的默认大小"：内置形象的帧是 160 高的原生尺寸
        # （源 GIF 就这么大），而用户自己传的形象会被统一到 320 高，
        # 所以内置形象的默认值要大一号，观感才和别的形象一致。
        dflt_scale = petlist.CHAR_SCALE.get(self.cb_char.currentData(), 1.0)
        sc = float(cfg.get("scale", dflt_scale))
        saved = "scale" in cfg
        if sel:
            # 选中了某一只就显示它自己的大小：自由缩放（Ctrl+滚轮 / 拖右下角手柄）
            # 改的是这一只，不是全局值
            pet_scale = (petlist.get_pet(sel) or {}).get("scale")
            if pet_scale is not None:
                sc = float(pet_scale)
                saved = True
        if not saved:
            # 头一次出现：把形象的默认大小对到最近的一档预设，
            # 别让全新安装一上来就显示「自定义 160%」（那个值是给自由缩放用的）
            sc = min((v for _, v in SCALE_STEPS), key=lambda v: abs(v - dflt_scale))
        # 自由缩放得到的是任意浮点：下拉里要显示成「自定义 128%」，
        # 否则会就近高亮成"大"，用户会以为自己的调整没生效（阿酉需求卡第 4 条）。
        custom = not any(abs(sc - v) < 0.02 for _, v in SCALE_STEPS)
        self.cb_scale.blockSignals(True)
        if custom:
            label = "自定义 %d%%" % round(sc * 100)
            if self._custom_scale_item:
                last = self.cb_scale.count() - 1
                self.cb_scale.setItemText(last, label)
                self.cb_scale.setItemData(last, sc)
            else:
                self.cb_scale.addItem(label, sc)
                self._custom_scale_item = True
            self.cb_scale.setCurrentIndex(self.cb_scale.count() - 1)
        else:
            if self._custom_scale_item:            # 回到预设就把自定义项删掉，别越攒越多
                self.cb_scale.removeItem(self.cb_scale.count() - 1)
                self._custom_scale_item = False
            si = min(range(len(SCALE_STEPS)), key=lambda i: abs(SCALE_STEPS[i][1] - sc))
            if si != self.cb_scale.currentIndex():
                self.cb_scale.setCurrentIndex(si)
        self.cb_scale.blockSignals(False)
        self.cb_sound.blockSignals(True)
        self.cb_sound.setChecked(bool(cfg.get("sound", True)))
        self.cb_sound.blockSignals(False)
        self.cb_auto.blockSignals(True)
        self.cb_auto.setChecked(autostart_on())
        self.cb_auto.blockSignals(False)
        beh = cfg.get("behavior") or {}
        for cb, key, dflt in ((self.cb_roam, "roam", True), (self.cb_flee, "flee", True),
                              (self.cb_inertia, "inertia", True),
                              (self.cb_recycle, "recycle", True)):
            cb.blockSignals(True)
            cb.setChecked(bool(beh.get(key, dflt)))
            cb.blockSignals(False)
        self._sync_bond(pets, sel)
        # 转速 / 翻转开关（存的是上一次的选择）
        sp = float(cfg.get("bond_speed") or 0.8)
        i = min(range(self.cb_bond_speed.count()),
                key=lambda k: abs(self.cb_bond_speed.itemData(k) - sp))
        self.cb_bond_speed.blockSignals(True)
        self.cb_bond_speed.setCurrentIndex(i)
        self.cb_bond_speed.blockSignals(False)
        self.cb_bond_spin.blockSignals(True)
        self.cb_bond_spin.setChecked(bool(cfg.get("bond_spin", True)))
        self.cb_bond_spin.blockSignals(False)
        self._sync_sounds(cfg)
        self._sync_bubble(cfg)
        nb = len(cfg.get("bubbles") or [])
        self.lb_bub_count.setText("当前 %d 条自定义台词" % nb if nb else "当前用内置台词")
        self.btn_del.setEnabled(self.cb_char.currentData() != paths.DEFAULT_CHARACTER)

    def apply(self, **changes):
        try:
            d = BASE / "logs"
            d.mkdir(exist_ok=True)
            with open(d / "ctl.log", "a", encoding="utf-8") as f:
                f.write(time.strftime("%H:%M:%S") + "  apply " + json.dumps(changes, ensure_ascii=False) + chr(10))
        except Exception:
            pass
        cfg = load_cfg()
        cfg.update(changes)
        save_cfg(cfg)
        # 全局设置改了（行为/台词/配色）：所有正在跑的实例都要重启才会生效。
        # 原来这里只判断"她"在不在 —— 多实例之后必须逐个来。
        alive = [p.get("id") for p in petlist.load_pets() if pet_running(p.get("id"))]
        if pet_running():
            stop_pet()
            start_pet()
        for pid_ in alive:
            stop_pet(pid_)
            start_pet(pid_)
        if alive or pet_running():
            time.sleep(0.6)
        self.refresh()

    # ------------------------------------------------------------ 多桌宠
    def _selected_pet(self):
        it = self.petlist_widget.currentItem()
        return it.data(Qt.UserRole) if it is not None else None

    def _on_pet_selected(self):
        pid = self._selected_pet()
        if not pid:
            return
        p = petlist.get_pet(pid) or {}
        for cb, val in ((self.cb_char, p.get("character")), (self.cb_scale, p.get("scale"))):
            if val is None:
                continue
            i = cb.findData(val) if cb is self.cb_char else min(
                range(cb.count()), key=lambda k: abs(cb.itemData(k) - float(val)))
            if i >= 0 and i != cb.currentIndex():
                cb.blockSignals(True)
                cb.setCurrentIndex(i)
                cb.blockSignals(False)

    # ------------------------------------------------------------ 伙伴绑定
    def _sync_bond(self, pets, sel) -> None:
        """把「伴侣」下拉刷新成"除自己以外的其它桌宠 + 不绑定"。"""
        cur = ((petlist.get_pet(sel) or {}).get("bond") if sel else None)
        want = [("（不绑定）", None)]
        for p in pets:
            if p.get("id") == sel:
                continue
            want.append(("%s · %s" % (p.get("id"), p.get("character", "")[:12]), p.get("id")))
        got = [self.cb_bond.itemData(i) for i in range(self.cb_bond.count())]
        if got != [w[1] for w in want]:
            self.cb_bond.blockSignals(True)
            self.cb_bond.clear()
            for label, val in want:
                self.cb_bond.addItem(label, val)
            self.cb_bond.blockSignals(False)
        i = self.cb_bond.findData(cur)
        self.cb_bond.setEnabled(bool(sel) and self.cb_bond.count() > 1)
        self.btn_bond_play.setEnabled(bool(cur))
        if i >= 0 and i != self.cb_bond.currentIndex():
            self.cb_bond.blockSignals(True)
            self.cb_bond.setCurrentIndex(i)
            self.cb_bond.blockSignals(False)

    def on_bond_opts(self):
        """转速 / 是否整只翻转：只影响"下一次发起"，所以直接写配置，不用重启桌宠。"""
        if self._busy():
            return
        cfg = load_cfg()
        cfg["bond_speed"] = float(self.cb_bond_speed.currentData())
        cfg["bond_spin"] = bool(self.cb_bond_spin.isChecked())
        save_cfg(cfg)

    def on_bond_change(self):
        if self._busy():
            return
        sel = self._selected_pet()
        if not sel:
            return
        mate = self.cb_bond.currentData()
        petlist.set_bond(sel, mate)
        _CHARS_CACHE["at"] = 0.0          # 列表标签无关，但顺手让缓存失效，下次立刻重读
        self.refresh()
        self.tray.showMessage("桌宠控制台",
                              "「%s」的伴侣设成 %s" % (sel, mate or "（无）"))

    def on_bond_play(self):
        """让选中的那只和它的伴侣围着同一个圆心转圈。

        计划写到数据目录的 bond.json：两只桌宠各自读它、各自按时间算自己该在圆周的哪一点 ——
        不需要两只互相通信，也不会出现"同时向对方打招呼"那种死锁。"""
        sel = self._selected_pet()
        if not sel:
            return
        p = petlist.get_pet(sel) or {}
        mate = p.get("bond")
        if not mate:
            QMessageBox.information(self, "还没选伴侣", "先在左边「伴侣」里选一只，再点「一起转圈」。")
            return
        q = petlist.get_pet(mate)
        if not q:
            QMessageBox.information(self, "伴侣不在了", "那只桌宠已经被移除了，重新选一只吧。")
            return
        for pid in (sel, mate):
            if not pet_running(pid):
                start_pet(pid)
        time.sleep(0.8)
        scr = QApplication.primaryScreen().availableGeometry()
        r = 110
        cx = (float(p.get("x", 0)) + float(q.get("x", 0))) / 2.0 + 110
        cy = (float(p.get("y", 0)) + float(q.get("y", 0))) / 2.0 + 240
        cx = max(scr.left() + r + 140, min(cx, scr.right() - r - 140))
        cy = max(scr.top() + r + 140, min(cy, scr.bottom() - r - 140))
        cfg = load_cfg()
        plan = {"pair": [sel, mate], "center": [cx, cy], "radius": r, "angle0": 0.0,
                "t0": time.time(),
                "speed": float(cfg.get("bond_speed") or 0.8),
                "spin": bool(cfg.get("bond_spin", True)),
                "duration": 20.0,
                "offsets": {sel: 0.0, mate: 3.141592653589793}}
        try:
            paths.atomic_write_text(paths.data_root() / "bond.json", json.dumps(plan))
        except Exception as e:
            QMessageBox.critical(self, "没写进去", str(e))
            return
        self.tray.showMessage("桌宠控制台", "「%s」和「%s」开始转圈（20 秒）" % (sel, mate))

    def on_add_pet(self):
        if self._busy():
            return
        petlist.ensure_first()
        idx = len(petlist.load_pets())
        x, y = petlist.free_spot(idx)
        p = petlist.add_pet(self.cb_char.currentData() or paths.DEFAULT_CHARACTER, x, y,
                            float(self.cb_scale.currentData() or 1.0))
        start_pet(p["id"])
        time.sleep(0.6)
        self.refresh()
        self.tray.showMessage("桌宠控制台", "召唤了一只（共 %d 只）" % len(petlist.load_pets()))

    def on_toggle_selected(self):
        pid = self._selected_pet()
        if not pid:
            return
        stop_pet(pid) if pet_running(pid) else start_pet(pid)
        ui_sleep(0.4)
        self.refresh()

    def on_remove_pet(self):
        pid = self._selected_pet()
        if not pid:
            return
        if pet_running(pid):
            stop_pet(pid)
        petlist.remove_pet(pid)
        self.refresh()

    def on_stop_all(self):
        stop_all_pets()
        time.sleep(0.5)
        self.refresh()

    def on_toggle(self):
        self.hide_pet() if pet_running() else self.show_pet()

    def show_pet(self):
        start_pet()
        time.sleep(0.6)
        self.refresh()

    def hide_pet(self):
        stop_pet()
        self.refresh()

    def _busy(self):
        return getattr(self, "_syncing", False)

    def on_sound(self, v):
        if self._busy():
            return
        self.apply(sound=bool(v))

    # ------------------------------------------------------------ 互动音效
    def _toggle_sfx(self) -> None:
        on = not self.sfx_box.isVisible()
        self.sfx_box.setVisible(on)
        self.btn_sfx.setText("互动音效（每类可绑多个，随机播一个）  " + ("▾" if on else "▸"))

    def _sync_sounds(self, cfg) -> None:
        """把当前绑定显示出来：内置 / N 个：名字…（找不到的文件不算数）"""
        snd = cfg.get("sounds") or {}
        for ev, _label in SFX_EVENTS:
            rels = [str(x) for x in (snd.get(ev) or [])]
            ok = [r for r in rels if paths.find_asset(r)]
            if not ok:
                self.sfx_status[ev].setText("内置")
                continue
            names = "、".join(Path(r).stem for r in ok[:2])
            self.sfx_status[ev].setText("%d 个：%s%s" % (len(ok), names, "…" if len(ok) > 2 else ""))

    def on_add_sound(self, ev: str) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择音效（只支持 WAV）",
                                                str(Path.home()), "音效 (*.wav)")
        if not files:
            return
        bad = [Path(f).name for f in files if Path(f).suffix.lower() != ".wav"]
        if bad:
            QMessageBox.information(
                self, "只支持 WAV",
                "这些不是 WAV，先跳过：\n" + "\n".join(bad[:5]) +
                "\n\n原因：播放用的是系统自带的 winsound，它只认 WAV。"
                "先用任意工具转成 WAV 再传就行（建议 1 秒以内的短音效，太长会盖住上一条）。")
        dst_dir = paths.asset_root_for_write() / "sounds"
        dst_dir.mkdir(parents=True, exist_ok=True)
        cfg = load_cfg()
        snd = dict(cfg.get("sounds") or {})
        cur = [str(x) for x in (snd.get(ev) or [])]
        added = 0
        for f in files:
            src = Path(f)
            if src.suffix.lower() != ".wav":
                continue
            dst = dst_dir / src.name
            try:
                if src.resolve() != dst.resolve():
                    shutil.copy2(src, dst)
            except Exception as e:
                QMessageBox.warning(self, "复制失败", "%s：%s" % (src.name, e))
                continue
            rel = "sounds/" + dst.name
            if rel not in cur:
                cur.append(rel)
                added += 1
        if not added:
            return
        snd[ev] = cur
        self.apply(sounds=snd)
        self.tray.showMessage("桌宠控制台",
                              "「%s」绑定了 %d 个音效" % (dict(SFX_EVENTS)[ev], added))

    def on_clear_sound(self, ev: str) -> None:
        cfg = load_cfg()
        snd = dict(cfg.get("sounds") or {})
        if not snd.get(ev):
            return
        snd[ev] = []
        self.apply(sounds=snd)
        self.tray.showMessage("桌宠控制台", "「%s」已恢复内置音效" % dict(SFX_EVENTS)[ev])

    def on_preview_sound(self, ev: str) -> None:
        """试听：优先按当前绑定随机挑一个，没绑就放内置 boop。"""
        import random as _random
        cfg = load_cfg()
        pool = [paths.find_asset(str(r)) for r in ((cfg.get("sounds") or {}).get(ev) or [])]
        pool = [p for p in pool if p]
        if not pool:
            p = paths.find_asset("sounds/boop.wav")
            pool = [p] if p else []
        if not pool:
            QMessageBox.information(self, "没有音效可听", "内置音效文件缺失（assets/sounds/）。")
            return
        if winsound is None:
            QMessageBox.information(self, "这台机器不能放音效", "winsound 不可用（非 Windows？）。")
            return
        try:
            winsound.PlaySound(str(_random.choice(pool)),
                               winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception as e:
            QMessageBox.warning(self, "播放失败", str(e))

    def _set_behavior(self, key, value):
        if self._busy():
            return
        beh = dict(load_cfg().get("behavior") or {})
        beh[key] = bool(value)
        self.apply(behavior=beh)
        # 写完立刻按磁盘回读校验：apply() 里会重启桌宠，桌宠启动时也会写 config，
        # 万一谁的写把这一项盖回去了，这里要能立刻发现并把界面拉回真实状态
        # ——"点了开关过一会儿自己又勾上"这种问题不能再靠用户肉眼发现。
        disk = (load_cfg().get("behavior") or {}).get(key)
        if disk is not None and bool(disk) != bool(value):
            try:
                with open(BASE / "logs" / "ctl.log", "a", encoding="utf-8") as f:
                    f.write(time.strftime("%H:%M:%S") + "  !! 行为开关没写进去: %s=%s 磁盘上=%s"
                            % (key, value, disk) + chr(10))
            except Exception:
                pass
            self.refresh()

    def on_layer(self):
        if self._busy():
            return
        self.apply(mode="topmost" if self.rb_top.isChecked() else "desktop")

    # ------------------------------------------------------------ 对话框配色
    def _current_bubble(self):
        def rgb(btn):
            c = btn.color()
            return [c.red(), c.green(), c.blue()]
        return {"auto": self.rb_bub_auto.isChecked(),
                "bg": rgb(self.c_bg), "fg": rgb(self.c_fg), "border": rgb(self.c_bd)}

    def on_bubble_mode(self):
        if self._busy() or getattr(self, "_bub_guard", False):
            return
        self.apply(bubble=self._current_bubble())

    def on_bubble_color(self):
        if self._busy():
            return
        # 手动改了颜色，就自动切到"自定义"
        self._bub_guard = True
        self.rb_bub_custom.setChecked(True)
        self.rb_bub_auto.setChecked(False)
        self._bub_guard = False
        self.apply(bubble=self._current_bubble())

    def _sync_bubble(self, cfg):
        bub = cfg.get("bubble") or {}
        auto = bool(bub.get("auto", True))
        resolved = cfg.get("bubble_resolved") or {}
        self._bub_guard = True
        self.rb_bub_auto.setChecked(auto)
        self.rb_bub_custom.setChecked(not auto)
        self._bub_guard = False

        if auto and resolved:
            bg = resolved.get("bg", [19, 28, 54])
            fg = resolved.get("fg", [234, 239, 255])
            bd = resolved.get("border", [126, 152, 255])
        else:
            bg = bub.get("bg") or [19, 28, 54]
            fg = bub.get("fg") or [234, 239, 255]
            bd = bub.get("border") or [126, 152, 255]
        self.c_bg.set_color(bg)
        self.c_fg.set_color(fg)
        self.c_bd.set_color(bd)
        self.preview.set_colors(bg, fg, bd)
        for w in (self.c_bg, self.c_fg, self.c_bd):
            w.setEnabled(not auto)

    def on_char(self):
        if self._busy():
            return
        sel = self._selected_pet()
        if sel and self.cb_char.currentData():
            petlist.update_pet(sel, character=self.cb_char.currentData())
            if pet_running(sel):
                stop_pet(sel)
                start_pet(sel)
            self.refresh()
        elif self.cb_char.currentData():
            self.apply(character=self.cb_char.currentData())

    def on_scale(self):
        if self._busy():
            return
        sel = self._selected_pet()
        if sel:
            petlist.update_pet(sel, scale=float(self.cb_scale.currentData()))
            if pet_running(sel):
                stop_pet(sel)
                start_pet(sel)
            self.refresh()
        else:
            self.apply(scale=self.cb_scale.currentData())

    def on_edit_bubbles(self):
        if self._busy():
            return
        items = load_cfg().get("bubbles") or []
        if not items:
            items = [{"type": "text", "text": t} for t in DEFAULT_LINES]
        dlg = BubbleEditor(items, self)
        if dlg.exec() == QDialog.Accepted:
            self.apply(bubbles=dlg.items)
            self.tray.showMessage("桌宠控制台", "点击台词已更新（共 %d 条）" % len(dlg.items))

    def on_delete_char(self):
        if self._busy():
            return
        rel = self.cb_char.currentData()
        if not rel:
            return
        if rel == paths.DEFAULT_CHARACTER:
            QMessageBox.information(self, "不能删除", "内置形象是兜底用的，删了就没人兜底了。")
            return
        label = self.cb_char.currentText()
        ans = QMessageBox.question(self, "删除形象",
                                   "确定删除「%s」吗？\n\n素材目录会被直接删掉，无法恢复。" % label,
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        found = paths.find_asset(rel + "/_frames.json")
        d = found.parent if found else (ASSETS / rel)
        try:
            if pet_running():
                stop_pet()
            shutil.rmtree(d, ignore_errors=True)
            names = load_names()
            names.pop(rel, None)
            save_names(names)
            _CHARS_CACHE["at"] = 0.0            # 让形象列表缓存立刻失效
            _CHARS_CACHE["data"] = []
            rest = characters()
            if rest:
                self.apply(character=rest[0][1])
            else:
                self.refresh()
            self.tray.showMessage("桌宠控制台", "已删除「%s」" % label)
        except Exception as e:
            QMessageBox.critical(self, "删除失败", str(e))

    def on_add(self):
        dlg = ImportDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.apply(character=dlg.pet_id)
            self.tray.showMessage("桌宠控制台", "新桌宠已生成并切换过去了")

    def on_quit(self):
        self.tray.hide()
        QApplication.quit()

    def reveal(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.isVisible():
            self._save_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.isVisible():
            self._save_geometry()

    def closeEvent(self, event):
        self._save_geometry()
        event.ignore()
        self.hide()
        if not getattr(self, "_hinted", False):
            self._hinted = True
            self.tray.showMessage("桌宠控制台", "已收进托盘，托盘图标双击可以再打开")


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    probe = QLocalSocket()
    probe.connectToServer(SERVER_NAME)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(300)
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    server.listen(SERVER_NAME)
    win = Console()

    def on_conn():
        s = server.nextPendingConnection()
        if s:
            s.readyRead.connect(win.reveal)
            s.disconnected.connect(s.deleteLater)   # 不然每次双击都漏一个 socket（阿酉 review P1-4）
            s.readyRead.connect(s.disconnectFromServer)
    server.newConnection.connect(on_conn)
    if "--autostart" in sys.argv:
        # 开机自启：拉起桌宠，自己只留在托盘
        win.show_pet()
        win.tray.showMessage("桌宠控制台", "桌宠已就位，双击托盘图标可以打开控制台")
    else:
        win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
