# -*- coding: utf-8 -*-
"""诊断：打包后的控制台加 --autostart 到底有没有活着、有没有窗口。"""
import ctypes, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)

BASE = Path(r"D:/dsh/deskpet")
EXE = BASE / "dist" / "DeskPet-Lite" / "DeskPet.exe"
TMP = BASE / "selftest" / "appdata-diag"
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)

u = ctypes.WinDLL("user32")
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

def wins(pid):
    out = []
    EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid:
            r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
            b = ctypes.create_unicode_buffer(128); u.GetClassNameW(h, b, 128)
            out.append("%s %dx%d 可见=%s" % (b.value, r.right - r.left, r.bottom - r.top, bool(u.IsWindowVisible(h))))
        return True
    u.EnumWindows(EP(cb), 0)
    return out

env = dict(os.environ); env["APPDATA"] = str(TMP)
for args in (["--autostart"], []):
    print("=== 启动参数 %s ===" % args)
    p = subprocess.Popen([str(EXE)] + args, cwd=str(EXE.parent), env=env)
    time.sleep(6)
    print("  进程存活:", p.poll() is None, "退出码:", p.poll())
    for w in wins(p.pid):
        print("   窗口:", w)
    # 数据目录
    for f in sorted((TMP / "DeskPet").rglob("*")):
        print("   ", f.relative_to(TMP).as_posix(), f.stat().st_size)
    p.kill()
    time.sleep(1.5)
