import ctypes
from ctypes import wintypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.WinDLL("user32")
for fn, at, rt in (("WindowFromPoint",[wintypes.POINT],wintypes.HWND),
                   ("GetClassNameW",[wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],ctypes.c_int),
                   ("GetWindowTextW",[wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],ctypes.c_int),
                   ("GetWindowLongW",[wintypes.HWND, ctypes.c_int],wintypes.LONG),
                   ("GetWindowRect",[wintypes.HWND, ctypes.POINTER(wintypes.RECT)],wintypes.BOOL),
                   ("GetWindowThreadProcessId",[wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],wintypes.DWORD),
                   ("IsWindowVisible",[wintypes.HWND],wintypes.BOOL)):
    f = getattr(u, fn); f.argtypes = at; f.restype = rt
out = []
h = u.WindowFromPoint(wintypes.POINT(1808, 1037))
b = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, b, 256)
t = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, t, 256)
r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
d = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(d))
ex = u.GetWindowLongW(h, -20)
out.append("命中的窗口: %s [%s] pid=%d rect=%s exstyle=0x%08x visible=%s" % (
    b.value, t.value, d.value, (r.left,r.top,r.right,r.bottom), ex, u.IsWindowVisible(h)))
out.append("  WS_EX_TRANSPARENT(点击穿透) = %s" % bool(ex & 0x20))
out.append("  WS_EX_LAYERED     = %s" % bool(ex & 0x80000))
import subprocess
rr = subprocess.run(["powershell","-NoProfile","-Command",
  "Get-CimInstance Win32_Process -Filter \"ProcessId=%d\" | ForEach-Object { $_.Name + \" | \" + $_.ExecutablePath }" % d.value],
  capture_output=True, text=True, creationflags=0x08000000)
out.append("  进程: " + rr.stdout.strip())
# 多点采样
for pt in ((900,700),(300,300),(1808,1037),(1700,700)):
    hh = u.WindowFromPoint(wintypes.POINT(*pt))
    bb = ctypes.create_unicode_buffer(256); u.GetClassNameW(hh, bb, 256)
    dd = wintypes.DWORD(); u.GetWindowThreadProcessId(hh, ctypes.byref(dd))
    out.append("  点%s -> %s pid=%d" % (pt, bb.value, dd.value))
open(r"C:/Users/Lenovo/Desktop/FullTest/hit.txt","w",encoding="utf-8").write(chr(10).join(out))
print("ok")