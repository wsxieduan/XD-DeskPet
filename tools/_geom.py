# -*- coding: utf-8 -*-
import ctypes, json, os, sys
from ctypes import wintypes
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.WinDLL("user32")
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
rows = []


def cb(h, l):
    if u.IsWindowVisible(h):
        b = ctypes.create_unicode_buffer(64)
        u.GetWindowTextW(h, b, 64)
        if b.value in ("桌宠", "桌宠控制台"):
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            wp = wintypes.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(wp))
            rows.append("%s pid=%d 物理(%d,%d)-(%d,%d)" % (b.value, wp.value, r.left, r.top, r.right, r.bottom))
    return True


u.EnumWindows(EP(cb), 0)
print("窗口:", rows)
print("屏幕(物理):", u.GetSystemMetrics(0), "x", u.GetSystemMetrics(1))
ui = Path(os.environ["APPDATA"]) / "DeskPet" / "ui.json"
print("ui.json:", ui.read_text(encoding="utf-8") if ui.exists() else "（没有）")
