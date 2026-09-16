import ctypes
from ctypes import wintypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
u = ctypes.WinDLL("user32")
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
for fn, at, rt in (("EnumWindows",[EnumProc, wintypes.LPARAM],wintypes.BOOL),
                   ("GetClassNameW",[wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],ctypes.c_int),
                   ("GetWindowTextW",[wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],ctypes.c_int),
                   ("GetWindowRect",[wintypes.HWND, ctypes.POINTER(wintypes.RECT)],wintypes.BOOL),
                   ("GetWindowThreadProcessId",[wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],wintypes.DWORD),
                   ("IsWindowVisible",[wintypes.HWND],wintypes.BOOL)):
    f = getattr(u, fn); f.argtypes = at; f.restype = rt
out = []
def cb(h, l):
    if not u.IsWindowVisible(h):
        return True
    r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    if w >= 2500 and hh >= 1400:
        b = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, b, 256)
        t = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, t, 256)
        d = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(d))
        out.append("%-40s pid=%-7d title=%s" % (b.value, d.value, t.value[:40]))
    return True
u.EnumWindows(EnumProc(cb), 0)
open(r"D:/dsh/deskpet/selftest/fullscreen.txt", "w", encoding="utf-8").write(chr(10).join(out))
print("ok")
