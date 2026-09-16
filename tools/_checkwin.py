# -*- coding: utf-8 -*-
import ctypes, json, os, sys, time
from ctypes import wintypes
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.WinDLL("user32")
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
found = []


def cb(h, l):
    if u.IsWindowVisible(h):
        b = ctypes.create_unicode_buffer(64)
        u.GetWindowTextW(h, b, 64)
        if b.value in ("桌宠", "桌宠控制台"):
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            wp = wintypes.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(wp))
            found.append("%s pid=%d (%d,%d) %dx%d" % (b.value, wp.value, r.left, r.top,
                                                      r.right - r.left, r.bottom - r.top))
    return True


u.EnumWindows(EP(cb), 0)
print("当前桌面上的桌宠窗口:")
for f in found:
    print("   ", f)
DATA = Path(os.environ["APPDATA"]) / "DeskPet"
print("pets.json:", (DATA / "pets.json").read_text(encoding="utf-8").replace(chr(10), " "))
cfg = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
print("config: character=%s mode=%s scale=%s" % (cfg.get("character"), cfg.get("mode"), cfg.get("scale")))
print("形象:", [p.parent.relative_to(DATA).as_posix() for p in (DATA / "assets").rglob("_frames.json")])
