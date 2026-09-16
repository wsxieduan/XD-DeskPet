# -*- coding: utf-8 -*-
"""test-zoom-e2e.py —— 真机验证：真的按住 Ctrl 滚滚轮，桌宠会不会变大、脚底会不会动。

前面的 test-zoom.py 是进程内直接调 wheelEvent（验证逻辑），这个是用**真实输入**走一遍
（SetCursorPos + keybd_event + mouse_event），验证"操作系统真的把滚轮消息发给了贴在壁纸层的桌宠"。
"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
TMP = BASE / "selftest" / "appdata-zoom-e2e"
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
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
cfg_path = TMP / "DeskPet" / "config.json"
cfg_path.write_text(json.dumps({"character": "nailong", "x": 20, "y": 300, "scale": 1.0,
                                "sound": False, "behavior": {"roam": False, "flee": False}}),
                    encoding="utf-8")
env = dict(os.environ)
env["APPDATA"] = str(TMP)

u = ctypes.WinDLL("user32", use_last_error=True)
u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u.mouse_event.argtypes = [wintypes.DWORD] * 5
u.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def top_window_at(x, y):
    """光标位置最上层是谁 —— 锁屏（LockApp / "Windows 默认锁屏界面"）盖着的话，
    真实滚轮消息会被它吃掉，这时候测出来的是"环境不可用"，不是桌宠的 bug。"""
    pt = wintypes.POINT(x, y)
    h = u.WindowFromPoint(pt)
    if not h:
        return ""
    wp = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(wp))
    cls = ctypes.create_unicode_buffer(128)
    u.GetClassNameW(h, cls, 128)
    txt = ctypes.create_unicode_buffer(160)
    u.GetWindowTextW(h, txt, 160)
    return "%s|%s|pid=%d" % (cls.value, txt.value, wp.value)


u.WindowFromPoint.argtypes = [wintypes.POINT]
u.WindowFromPoint.restype = wintypes.HWND
u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]


def wins(pid):
    out = []

    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid and u.IsWindowVisible(h):
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 20:
                out.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    u.EnumWindows(EP(cb), 0)
    return out


p = subprocess.Popen([sys.executable, str(BASE / "deskpet.py")], cwd=str(BASE), env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)
w = wins(p.pid)
say("桌宠窗口: %s" % (w,))
if not w:
    check("桌宠起来了", False)
    p.kill()
    sys.exit()
x, y, ww, wh = w[0]
foot0 = (x + ww // 2, y + wh)          # 窗口底边中点 == 精灵脚底中心（精灵贴在窗口底部、水平居中）
say("初始：窗口 %dx%d @ (%d,%d)  脚底=%s  scale=%s" % (ww, wh, x, y, foot0, json.loads(cfg_path.read_text(encoding='utf-8')).get("scale")))

# 真光标移到精灵身上，按住 Ctrl 滚 3 格
u.SetCursorPos(x + ww // 2, y + wh - 40)
time.sleep(0.4)
top = top_window_at(x + ww // 2, y + wh - 40)
say("  光标位置最上层窗口: %s" % top)
if "LockApp" in top or "锁屏" in top or "LogonUI" in top:
    say("  ！锁屏盖在上面，真实滚轮会被它吃掉 —— 这次测不出结果（环境问题，不是桌宠的 bug）")
    p.terminate()
    (BASE / "selftest" / "report-zoom-e2e.txt").write_text(chr(10).join(lines), encoding="utf-8")
    print("环境不可用（锁屏）")
    sys.exit(0)
u.keybd_event(0x11, 0, 0, None)                     # VK_CONTROL down
for _ in range(3):
    u.mouse_event(0x0800, 0, 0, 120, 0)             # MOUSEEVENTF_WHEEL, +120
    time.sleep(0.08)
u.keybd_event(0x11, 0, 0x0002, None)                # VK_CONTROL up
time.sleep(1.2)                                     # 等防抖重采样 + 落盘
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
if float(cfg.get("scale", 1.0)) <= 1.05:
    # 真机滚轮偶尔会丢一两条消息（光标刚挪过去、窗口还没成为滚动目标）。
    # 重试一次：这仍然是"真实输入"，只是不让偶发丢消息变成假失败。
    say("   （第一次没接到滚轮消息，重试一遍）")
    u.SetCursorPos(x + ww // 2, y + wh - 40)
    time.sleep(0.4)
    u.keybd_event(0x11, 0, 0, None)
    for _ in range(4):
        u.mouse_event(0x0800, 0, 0, 120, 0)
        time.sleep(0.12)
    u.keybd_event(0x11, 0, 0x0002, None)
    time.sleep(1.2)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
w2 = wins(p.pid)
say("滚完：scale=%s  窗口=%s" % (cfg.get("scale"), w2))
check("真实 Ctrl+滚轮让桌宠变大了", float(cfg.get("scale", 1.0)) > 1.1, str(cfg.get("scale")))
if w2:
    x2, y2, ww2, wh2 = w2[0]
    foot1 = (x2 + ww2 // 2, y2 + wh2)
    say("  脚底 %s -> %s" % (foot0, foot1))
    check("脚底钉在原地（±3px）", abs(foot1[0] - foot0[0]) <= 3 and abs(foot1[1] - foot0[1]) <= 3,
          "%s -> %s" % (foot0, foot1))
    check("窗口确实变大了", wh2 > wh + 20, "%d -> %d" % (wh, wh2))

p.terminate()
time.sleep(0.5)
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-zoom-e2e.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
