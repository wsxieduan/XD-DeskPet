# -*- coding: utf-8 -*-
"""test-fallback.py —— config 里指着一个已经不存在的形象时，桌宠要回落到内置形象而不是起不来。"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
TMP = BASE / "selftest" / "appdata-fallback"
lines, fails = [], []
def say(*a):
    lines.append(" ".join(str(x) for x in a)); print(lines[-1], flush=True)
def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok: fails.append(n)

subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / "config.json").write_text(json.dumps(
    {"character": "user/does-not-exist", "x": 20, "y": 300, "scale": 1.0, "sound": False}),
    encoding="utf-8")
env = dict(os.environ); env["APPDATA"] = str(TMP)
p = subprocess.Popen([sys.executable, str(BASE / "deskpet.py")], cwd=str(BASE), env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)
u = ctypes.WinDLL("user32")
u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
found = []
def cb(h, l):
    wp = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(wp))
    if wp.value == p.pid and u.IsWindowVisible(h):
        r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        if r.right - r.left > 20:
            found.append((r.right - r.left, r.bottom - r.top))
    return True
u.EnumWindows(EP(cb), 0)
check("形象不存在时桌宠照样起来了", bool(found), str(found))
log = TMP / "DeskPet" / "logs" / "deskpet.log"
txt = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
check("日志里说明了回落到内置形象", "回落到内置形象" in txt,
      [l for l in txt.splitlines() if "回落" in l][:1].__str__())
# 窗口宽 = max(精灵宽, 气泡文字宽)，所以用高度判断更准：
# 精灵 160*1.0*1.5 = 240 物理像素，再加气泡区（约 60）≈ 300。
check("回落后按内置形象的尺寸渲染（精灵 240 + 气泡区）",
      bool(found) and 280 <= found[0][1] <= 330 and found[0][0] >= 240, str(found))
p.terminate(); time.sleep(0.5)
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-fallback.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
