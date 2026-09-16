# -*- coding: utf-8 -*-
"""诊断 2：用 PrintWindow 直接抓桌宠窗口自己的内容，判断到底"应用冻住了"还是"窗口被盖住"。
同时查一下桌宠窗口那个位置的屏幕上层窗口是谁。"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
from PIL import Image
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)

BASE = Path(r"D:/dsh/deskpet")
EXE = Path(sys.argv[1]) if len(sys.argv) > 1 else (BASE / "dist" / "DeskPet-Lite" / "DeskPet.exe")
TMP = BASE / "selftest" / "appdata-pw"
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / "config.json").write_text(json.dumps(
    {"character": "nailong", "x": 20, "y": 300, "scale": 1.6, "sound": False}), encoding="utf-8")

u = ctypes.WinDLL("user32")
g = ctypes.WinDLL("gdi32")
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
u.WindowFromPoint.argtypes = [wintypes.POINT]
u.WindowFromPoint.restype = wintypes.HWND
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

def hwnds(pid):
    out = []
    EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid and u.IsWindowVisible(h):
            r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 20:
                out.append((h, r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True
    u.EnumWindows(EP(cb), 0)
    return out

def grab_window(h, w, hh):
    hdc = u.GetWindowDC(h)
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, hh)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(h, mdc, 2)          # PW_RENDERFULLCONTENT
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(bi); bi.biWidth = w; bi.biHeight = -hh
    bi.biPlanes = 1; bi.biBitCount = 32; bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * hh * 4)
    g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(h, hdc)
    return Image.frombuffer("RGBA", (w, hh), buf, "raw", "BGRA", 0, 1)

subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
env = dict(os.environ); env["APPDATA"] = str(TMP)
p = subprocess.Popen([str(EXE), "--pet"], cwd=str(EXE.parent), env=env)
time.sleep(4)
ws = hwnds(p.pid)
print("窗口:", ws)
if not ws:
    p.kill(); sys.exit()
h, x, y, w, hh = ws[0]
pt = wintypes.POINT(x + w // 2, y + hh // 2)
top = u.WindowFromPoint(pt)
wp = wintypes.DWORD(); u.GetWindowThreadProcessId(top, ctypes.byref(wp))
cb = ctypes.create_unicode_buffer(128); u.GetClassNameW(top, cb, 128)
tb = ctypes.create_unicode_buffer(256); u.GetWindowTextW(top, tb, 256)
print("桌宠中心点上层的窗口: hwnd=%d pid=%d class=%s title=%r  是桌宠自己=%s"
      % (top, wp.value, cb.value, tb.value, top == h or wp.value == p.pid))

imgs = []
for i in range(6):
    img = grab_window(h, w, hh)
    imgs.append(img)
    if i:
        from PIL import ImageChops
        d = ImageChops.difference(img.convert("RGB"), imgs[i-1].convert("RGB")).convert("L")
        n = sum(1 for v in d.get_flattened_data() if v > 12)
        print("  第%d次 PrintWindow：与上次差 %d 像素" % (i, n))
    time.sleep(0.2)
# 内容里有多少非透明像素（判断窗口是不是画了东西）
a = imgs[-1].getchannel("A")
nz = sum(1 for v in a.get_flattened_data() if v > 8)
print("  窗口内容非空像素:", nz, "/", w * hh)
p.terminate()
