import ctypes, json, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

# 关键：不开 DPI 感知的话，Windows 会把传给 WindowFromPoint / SetCursorPos 的坐标
# 当成逻辑坐标再乘缩放比，测出来的目标是错的（我第一版就栽在这）。
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

u = ctypes.WinDLL("user32")
for fn, at, rt in (
    ("WindowFromPoint", [wintypes.POINT], wintypes.HWND),
    ("GetClassNameW", [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
    ("GetWindowThreadProcessId", [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
    ("GetParent", [wintypes.HWND], wintypes.HWND),
    ("GetWindowRect", [wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
    ("GetAncestor", [wintypes.HWND, wintypes.UINT], wintypes.HWND),
):
    f = getattr(u, fn); f.argtypes = at; f.restype = rt

def cls(h):
    b = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, b, 256); return b.value

def owner_pid(h):
    d = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(d)); return d.value

subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force"],
               capture_output=True, creationflags=0x08000000)
time.sleep(1)
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(BASE / "tools" / "kill-pets.ps1")],
               capture_output=True, creationflags=0x08000000)
time.sleep(1.2)

X, Y, W, H = 0, 340, 211, 358
DPI = 1.5
cfg = json.loads((paths.config_path()).read_text(encoding="utf-8"))
cfg.update({"mode": "desktop", "character": "oc/view1", "scale": 1.0, "x": X, "y": Y})
(paths.config_path()).write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
lf = open(BASE / "selftest" / "dbg2.log", "w", encoding="utf-8")
p = subprocess.Popen([sys.executable, str(BASE / "deskpet.py")], cwd=str(BASE),
                     stdout=lf, stderr=subprocess.STDOUT)
time.sleep(4.0)

import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)
pid = ctl.read_pid()
say("桌宠 pid = %s，运行中 = %s" % (pid, ctl.pet_running()))

cx, cy = int((X + W/2) * DPI), int((Y + H*0.72) * DPI)
say("点击位置(物理) = (%d, %d)" % (cx, cy))
h = u.WindowFromPoint(wintypes.POINT(cx, cy))
say("WindowFromPoint 返回: hwnd=%s class=%s 属于 pid=%s" % (h, cls(h), owner_pid(h)))
say("   -> 这个点上的点击会被 [%s] 收走" % cls(h))
say()

say("该位置从下往上的窗口链:")
chain = []
cur = h
while cur:
    r = wintypes.RECT(); u.GetWindowRect(cur, ctypes.byref(r))
    chain.append("%s pid=%s rect=%s" % (cls(cur), owner_pid(cur), (r.left, r.top, r.right, r.bottom)))
    cur = u.GetParent(cur)
for c in chain:
    say("   " + c)

say()
say("Progman 的子窗口顺序（z 序，从高到低）:")
u.FindWindowW.argtypes=[wintypes.LPCWSTR,wintypes.LPCWSTR]; u.FindWindowW.restype=wintypes.HWND
u.FindWindowExW.argtypes=[wintypes.HWND,wintypes.HWND,wintypes.LPCWSTR,wintypes.LPCWSTR]
u.FindWindowExW.restype=wintypes.HWND
progman = u.FindWindowW("Progman", None)
ch = u.FindWindowExW(progman, 0, None, None)
while ch:
    r = wintypes.RECT(); u.GetWindowRect(ch, ctypes.byref(r))
    say("   %-34s rect=%s" % (cls(ch), (r.left, r.top, r.right, r.bottom)))
    ch = u.FindWindowExW(progman, ch, None, None)

p.terminate()
(BASE / "selftest" / "report-wfp.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
