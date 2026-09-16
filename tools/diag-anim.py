# -*- coding: utf-8 -*-
"""诊断：exe 直接 --pet 时动画有没有在动（逐秒采样截图 + 读日志）。"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
from PIL import Image, ImageChops, ImageGrab
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)

BASE = Path(r"D:/dsh/deskpet")
EXE = BASE / "dist" / "DeskPet-Lite" / "DeskPet.exe"
TMP = BASE / "selftest" / "appdata-anim"
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / "config.json").write_text(json.dumps(
    {"character": "nailong", "x": 20, "y": 300, "scale": 1.6, "sound": False}), encoding="utf-8")

u = ctypes.WinDLL("user32")
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]

def wins(pid):
    out = []
    EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid and u.IsWindowVisible(h):
            r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 20:
                out.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True
    u.EnumWindows(EP(cb), 0)
    return out

subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
env = dict(os.environ); env["APPDATA"] = str(TMP)
p = subprocess.Popen([str(EXE), "--pet"], cwd=str(EXE.parent), env=env,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
time.sleep(4)
w = wins(p.pid)
print("窗口:", w)
if not w:
    print("没有窗口，stdout:", p.communicate(timeout=3)[0][:500])
    sys.exit()
x, y, ww, wh = w[0]
box = (x - 2, y - 2, x + ww + 2, y + wh + 2)
prev = None
for i in range(8):
    img = ImageGrab.grab(bbox=box).convert("RGB")
    if prev is not None:
        d = ImageChops.difference(img, prev).convert("L")
        n = sum(1 for v in d.get_flattened_data() if v > 20)
        print("  第%d次采样：与上一次差 %d 像素" % (i, n))
    prev = img
    time.sleep(0.25)
p.terminate()
try:
    out = p.communicate(timeout=5)[0].decode("utf-8", "replace")
except Exception:
    p.kill(); out = ""
print("stdout 末尾:", out.strip()[-800:])
log = TMP / "DeskPet" / "logs" / "deskpet.log"
if log.exists():
    print("=== deskpet.log ===")
    print(log.read_text(encoding="utf-8", errors="replace")[-1500:])
