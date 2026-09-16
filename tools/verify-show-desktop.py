"""verify-show-desktop.py —— 模拟 Win+D 露出桌面，确认她真的在桌面上"""
import ctypes, json, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
from PIL import Image, ImageChops, ImageGrab

BASE = Path(r"D:/dsh/deskpet")
OUT = BASE / "selftest"
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

u = ctypes.WinDLL("user32", use_last_error=True)
u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]; u.FindWindowW.restype = wintypes.HWND
u.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

WM_COMMAND, MIN_ALL, MIN_ALL_UNDO = 0x0111, 419, 416
shell = u.FindWindowW("Shell_TrayWnd", None)
say("任务栏窗口:", shell)

def minimize_all():
    u.SendMessageW(shell, WM_COMMAND, MIN_ALL, 0)
def undo_minimize():
    u.SendMessageW(shell, WM_COMMAND, MIN_ALL_UNDO, 0)

def kill():
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(BASE / "tools" / "kill-pets.ps1")],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)

def start():
    subprocess.Popen(["pythonw", str(BASE / "deskpet.py")], cwd=str(BASE),
                     creationflags=0x00000008 | 0x08000000)
    time.sleep(3.2)

cfg = json.loads((paths.config_path()).read_text(encoding="utf-8"))
x, y = cfg.get("x", 1406), cfg.get("y", 494)
DPI = 1.5
BOX = (int(x * DPI) - 10, int(y * DPI) - 10, int((x + 211) * DPI) + 10, int((y + 358) * DPI) + 10)
say("她应该在(逻辑坐标):", (x, y), " 截取区域(物理):", BOX)
say()

try:
    say("1) 模拟 Win+D 露出桌面（所有窗口最小化）")
    minimize_all(); time.sleep(2.5)
    with_pet = ImageGrab.grab(bbox=BOX).convert("RGB")
    with_pet.save(OUT / "desktop-with-pet.png")

    say("2) 临时关掉桌宠，再截同一块区域")
    kill(); time.sleep(0.8)
    without = ImageGrab.grab(bbox=BOX).convert("RGB")
    without.save(OUT / "desktop-without-pet.png")

    n = sum(1 for p in ImageChops.difference(with_pet, without).convert("L").get_flattened_data() if p > 20)
    say("   有她 vs 没她 的像素差异 =", n)
    say("   ->", "她确实在桌面上 ✓" if n > 3000 else "没看到（需要排查）✗")

    say("3) 把桌宠重新启动")
    start()
finally:
    say("4) 恢复所有窗口（撤销最小化）")
    undo_minimize()
    time.sleep(1.0)

cfg = json.loads((paths.config_path()).read_text(encoding="utf-8"))
say()
say("最终配置:", cfg)
(OUT / "report-showdesktop.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
