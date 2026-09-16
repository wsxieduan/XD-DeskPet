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
                   ("GetWindowRect",[wintypes.HWND, ctypes.POINTER(wintypes.RECT)],wintypes.BOOL),
                   ("GetWindowThreadProcessId",[wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],wintypes.DWORD),
                   ("IsWindowVisible",[wintypes.HWND],wintypes.BOOL),
                   ("FindWindowW",[wintypes.LPCWSTR, wintypes.LPCWSTR],wintypes.HWND),
                   ("WindowFromPoint",[wintypes.POINT],wintypes.HWND)):
    f = getattr(u, fn); f.argtypes = at; f.restype = rt

def cls(h):
    b = ctypes.create_unicode_buffer(256); u.GetClassNameW(h, b, 256); return b.value

out = []
# 找 DeskPet.exe 的进程
import subprocess, json
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'DeskPet.exe' } | ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"],
                   capture_output=True, text=True, creationflags=0x08000000)
procs = [l for l in r.stdout.strip().splitlines() if l.strip()]
pet_pid = None
for l in procs:
    if "--pet" in l:
        pet_pid = int(l.split("|")[0].strip())
out.append("exe 进程: " + str(procs))
out.append("桌宠模式 pid = %s" % pet_pid)

top = []
def cb(h, l):
    top.append(h); return True
u.EnumWindows(EnumProc(cb), 0)
progman = u.FindWindowW("Progman", None)
idx_pm = top.index(progman) if progman in top else -1
idx_pet = -1
pet_hwnd = None
for i, h in enumerate(top):
    d = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(d))
    if d.value != pet_pid or not cls(h).startswith("Qt"):
        continue
    rr = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(rr))
    if u.IsWindowVisible(h) and 100 <= rr.right - rr.left <= 900:
        idx_pet, pet_hwnd = i, h
        break
if pet_hwnd:
    rr = wintypes.RECT(); u.GetWindowRect(pet_hwnd, ctypes.byref(rr))
    out.append("她的窗口 rect=(%d,%d,%d,%d) 可见=%s  z序位次=%d  Progman位次=%d" % (
        rr.left, rr.top, rr.right, rr.bottom, u.IsWindowVisible(pet_hwnd), idx_pet, idx_pm))
    cx = (rr.left + rr.right) // 2
    cy = rr.top + int((rr.bottom - rr.top) * 0.75)
    hw = u.WindowFromPoint(wintypes.POINT(cx, cy))
    d = wintypes.DWORD(); u.GetWindowThreadProcessId(hw, ctypes.byref(d))
    out.append("点 (%d,%d) 会被 %s pid=%d 收走 -> %s" % (
        cx, cy, cls(hw), d.value, "✅ 是她" if d.value == pet_pid else "❌ 不是她"))
else:
    out.append("没找到她的窗口")
open(r"C:/Users/Lenovo/Desktop/DeskPetTest/verify.txt", "w", encoding="utf-8").write(chr(10).join(out))
print("ok")