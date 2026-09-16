"""zcheck.py —— 不依赖屏幕可见性的验证：她是否正插在 Progman 后面（z 序）"""
import ctypes, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
u = ctypes.WinDLL("user32")
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
for fn, at, rt in (
    ("EnumWindows", [EnumProc, wintypes.LPARAM], wintypes.BOOL),
    ("GetClassNameW", [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
    ("GetWindowRect", [wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
    ("GetWindowThreadProcessId", [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
    ("IsWindowVisible", [wintypes.HWND], wintypes.BOOL),
    ("FindWindowW", [wintypes.LPCWSTR, wintypes.LPCWSTR], wintypes.HWND),
):
    f = getattr(u, fn); f.argtypes = at; f.restype = rt

def cls(h):
    b = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, b, 256); return b.value

subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(BASE / "tools" / "kill-pets.ps1")],
               capture_output=True, creationflags=0x08000000)
time.sleep(1.2)
import json
cfg = json.loads((paths.config_path()).read_text(encoding="utf-8"))
cfg.update({"mode": "desktop", "character": "oc/view1", "scale": 1.0, "x": 0, "y": 340})
(paths.config_path()).write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
lf = open(BASE / "selftest" / "zcheck.log", "w", encoding="utf-8")
p = subprocess.Popen([sys.executable, str(BASE / "deskpet.py")], cwd=str(BASE),
                     stdout=lf, stderr=subprocess.STDOUT)
time.sleep(4.0)

import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)
pid = ctl.read_pid()
say("桌宠 pid = %s  运行中 = %s" % (pid, ctl.pet_running()))

top = []
def cb(h, l):
    top.append(h); return True
u.EnumWindows(EnumProc(cb), 0)
say("顶层窗口总数 = %d（EnumWindows 按 z 序从上到下）" % len(top))

progman = u.FindWindowW("Progman", None)
idx_progman = top.index(progman) if progman in top else -1
pet_idx = -1
pet_hwnd = None
# 进程里有一堆 Qt 的隐藏辅助窗口（ThemeChangeObserver 之类），
# 要挑"可见 + 尺寸像她"的那个，否则会认错（踩过一次）
for i, h in enumerate(top):
    d = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(d))
    if d.value != pid or not cls(h).startswith("Qt"):
        continue
    r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    w_, h_ = r.right - r.left, r.bottom - r.top
    if u.IsWindowVisible(h) and 100 <= w_ <= 800 and 100 <= h_ <= 900:
        pet_idx, pet_hwnd = i, h
        break

say("Progman 在 z 序中的位置 = %d" % idx_progman)
say("桌宠窗口在 z 序中的位置 = %d (hwnd=%s)" % (pet_idx, pet_hwnd))
if pet_idx >= 0 and idx_progman >= 0:
    r = wintypes.RECT(); u.GetWindowRect(pet_hwnd, ctypes.byref(r))
    say("她的窗口矩形 = (%d,%d,%d,%d) 可见=%s" % (r.left, r.top, r.right, r.bottom,
                                                u.IsWindowVisible(pet_hwnd)))
    delta = idx_progman - pet_idx
    say("Progman 的位次 - 她的位次 = %d" % delta)
    if delta == 1:
        say("判定: ✅ 她紧贴在 Progman 正上方 —— 桌面之上、其他所有窗口之下。点击能到她，窗口能盖住她。")
    elif delta > 1:
        say("判定: ⚠️ 她上面还夹着 %d 个窗口（可能是锁屏/输入法之类，属正常）" % (delta - 1))
    else:
        say("判定: ❌ 她在 Progman 下面，会被桌面盖住")

say()
say("z 序里她附近的窗口（从她往上 6 个）：")
for i in range(max(0, pet_idx - 3), min(len(top), pet_idx + 4)):
    mark = "  <== 她" if i == pet_idx else ("  <== Progman" if i == idx_progman else "")
    vis = "可见" if u.IsWindowVisible(top[i]) else "隐藏"
    say("   [%3d] %-38s %s%s" % (i, cls(top[i])[:38], vis, mark))

p.terminate()
Path(BASE / "selftest" / "report-zcheck.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
