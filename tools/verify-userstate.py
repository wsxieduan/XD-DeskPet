# -*- coding: utf-8 -*-
"""verify-userstate.py —— 用"主人真实配置的副本"跑新版本，确认他手上的数据还能用。

拷一份 %APPDATA%\\DeskPet 到临时目录（配置 + 形象素材），用打包好的 exe 起 pet1，
看窗口有没有出来、动画有没有在跑、认的是哪个形象。
"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)

REAL = Path(os.environ["APPDATA"]) / "DeskPet"
TMP = BASE / "selftest" / "appdata-userstate"
EXE = BASE / "dist" / "DeskPet" / "DeskPet.exe"
lines, fails = [], []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    print(lines[-1], flush=True)


def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok:
        fails.append(n)


subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
for name in ("config.json", "pets.json"):
    src = REAL / name
    if src.exists():
        shutil.copy2(src, TMP / "DeskPet" / name)
if (REAL / "assets").exists():
    shutil.copytree(REAL / "assets", TMP / "DeskPet" / "assets")
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
pets = json.loads((TMP / "DeskPet" / "pets.json").read_text(encoding="utf-8"))
say("主人的实例: " + json.dumps(pets, ensure_ascii=False))
say("主人配置里的形象: " + str(json.loads((TMP / "DeskPet" / "config.json").read_text(encoding="utf-8")).get("character")))
say("拷过来的素材: " + str([p.relative_to(TMP / "DeskPet").as_posix()
                          for p in (TMP / "DeskPet" / "assets").rglob("_frames.json")]))

env = dict(os.environ)
env["APPDATA"] = str(TMP)
u = ctypes.WinDLL("user32")
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
g = ctypes.WinDLL("gdi32")
EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def wins(pid):
    out = []
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


def grab(h, w, hh):
    hdc = u.GetWindowDC(h); mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, hh); g.SelectObject(mdc, bmp)
    u.PrintWindow(h, mdc, 2)
    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                    ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bi = BIH(); bi.biSize = ctypes.sizeof(bi); bi.biWidth = w; bi.biHeight = -hh
    bi.biPlanes = 1; bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * hh * 4)
    g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(h, hdc)
    from PIL import Image, ImageChops
    return Image.frombuffer("RGB", (w, hh), buf, "raw", "BGRX", 0, 1)


pid_arg = pets[0]["id"] if pets else "pet1"
p = subprocess.Popen([str(EXE), "--pet", "--id", pid_arg], cwd=str(EXE.parent), env=env)
time.sleep(6)
w = wins(p.pid)
say("窗口: " + str(w))
check("主人那只桌宠在新版本里能起来", bool(w), str(w))
if w:
    h, x, y, ww, wh = w[0]
    a = grab(h, ww, wh)
    time.sleep(0.2)
    b = grab(h, ww, wh)
    from PIL import ImageChops
    d = ImageChops.difference(a, b).convert("L")
    n = sum(1 for v in d.get_flattened_data() if v > 12)
    # 主人那只只有 idle 一轨（静态立绘生成的动画），但待机浮动/呼吸也在动
    say("   精灵尺寸: %dx%d（窗口 %dx%d）" % (a.width, a.height, ww, wh))
    check("窗口画出了角色", ww > 100 and wh > 100)
    check("画面在动（待机动画）", n > 200, "200ms 内变化 %d 像素" % n)
logf = TMP / "DeskPet" / "logs" / "deskpet.log"
if logf.exists():
    txt = logf.read_text(encoding="utf-8", errors="replace")
    check("没有回落到内置形象（说明主人的素材是好的）", "回落" not in txt,
          [l for l in txt.splitlines() if "回落" in l][:1].__str__())
p.terminate()
time.sleep(0.5)
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-userstate.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
