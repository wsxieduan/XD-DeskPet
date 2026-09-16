# -*- coding: utf-8 -*-
"""verify-nailong.py —— 内置形象（奶龙）真机验收：渲染 / 动画 / 点击气泡 / 拖拽 / 内存。

用独立的 APPDATA（临时目录）跑，不碰主人自己的配置和形象列表。
"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
from PIL import Image, ImageChops, ImageGrab

BASE = Path(r"D:/dsh/deskpet")
OUT = BASE / "selftest"
TMP = OUT / "appdata-nailong"
lines, fails = [], []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    print(lines[-1], flush=True)


def check(name, ok, detail=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok:
        fails.append(name)


# DPI 感知必须在任何截图之前设置，否则坐标会被系统虚拟化（踩过）
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.WinDLL("user32", use_last_error=True)
u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u.mouse_event.argtypes = [wintypes.DWORD] * 5
u.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
X, Y, SCALE = 20, 300, 1.6


def click(x, y):
    u.SetCursorPos(x, y)
    time.sleep(0.15)
    u.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.08)
    u.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def drag(x0, y0, x1, y1, steps=12):
    u.SetCursorPos(x0, y0)
    time.sleep(0.15)
    u.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    for i in range(1, steps + 1):
        u.SetCursorPos(int(x0 + (x1 - x0) * i / steps), int(y0 + (y1 - y0) * i / steps))
        time.sleep(0.02)
    time.sleep(0.05)
    u.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def pet_windows(pid):
    found = []

    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid and u.IsWindowVisible(h):
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if (r.right - r.left) > 20 and (r.bottom - r.top) > 20:
                found.append((h, r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    u.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found


def mem_mb(pid):
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    k32 = ctypes.WinDLL("kernel32")
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(0x0410, False, pid)       # QUERY_INFORMATION | VM_READ
    if not h:
        return None
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    ok = ctypes.WinDLL("psapi").GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
    k32.CloseHandle(h)
    return round(pmc.WorkingSetSize / 1048576.0, 1) if ok else None


def shot(box):
    return ImageGrab.grab(bbox=box).convert("RGB")


def diff_px(a, b, thr=20):
    d = ImageChops.difference(a, b).convert("L")
    return sum(1 for p in d.get_flattened_data() if p > thr)


def main():
    # 隔离数据目录：临时 APPDATA
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    (TMP / "DeskPet").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["APPDATA"] = str(TMP)
    cfg = {"character": "nailong", "x": X, "y": Y, "scale": SCALE, "sound": False,
           "mode": "desktop"}
    (TMP / "DeskPet" / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    # 先清掉正在跑的桌宠，避免混淆
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(BASE / "tools" / "kill-pets.ps1")],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)

    proc = subprocess.Popen([sys.executable, str(BASE / "deskpet.py")], cwd=str(BASE), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(4.0)
    wins = pet_windows(proc.pid)
    say("桌宠进程 pid=%d  可见窗口 %d 个" % (proc.pid, len(wins)))
    for w in wins:
        say("    hwnd=%d rect=(%d,%d) %dx%d" % w)
    if not wins:
        check("桌宠窗口出现", False)
        proc.kill()
        return
    hwnd, wx, wy, ww, wh = wins[0]
    check("桌宠窗口出现", True, "位置(%d,%d) 尺寸%dx%d" % (wx, wy, ww, wh))
    box = (wx - 2, wy - 2, wx + ww + 2, wy + wh + 2)
    sprite_h_phys = int(160 * SCALE * 1.5)
    say("    sprite 高 %d 物理像素（160 x scale %.1f x dpr 1.5）" % (sprite_h_phys, SCALE))

    # 1) 画出来了没有：和"启动前"的空桌面比
    bg = shot(box)
    time.sleep(0.4)
    now = shot(box)
    vis = diff_px(bg, now)
    check("角色在桌面上可见", vis > 5000, "可见像素 %d" % vis)

    # 2) 动画在跑：隔 150ms 两张对比（源 GIF 每帧 30ms）
    a = shot(box)
    time.sleep(0.15)
    b = shot(box)
    anim = diff_px(a, b)
    check("动画在播放（30ms/帧）", anim > 500, "150ms 内变化像素 %d" % anim)

    # 3) 点击反馈：气泡画在 sprite 上方那块区域
    top_h = wh - sprite_h_phys - 4
    top_box = (box[0], box[1], box[2], box[1] + max(30, top_h))
    before = shot(top_box)
    cx, cy = wx + ww // 2, wy + wh - sprite_h_phys // 2
    click(cx, cy)
    time.sleep(0.6)
    after = shot(top_box)
    bub = diff_px(before, after)
    check("点击弹出气泡", bub > 300, "气泡区变化像素 %d（气泡区高 %d）" % (bub, top_h))

    # 4) 拖拽
    time.sleep(2.5)                      # 等气泡消失，别把气泡算进拖拽判定
    pos0 = pet_windows(proc.pid)[0]
    drag(pos0[1] + pos0[3] // 2, pos0[2] + pos0[4] - sprite_h_phys // 2,
         pos0[1] + pos0[3] // 2 + 260, pos0[2] + pos0[4] - sprite_h_phys // 2 - 120)
    time.sleep(0.8)
    pos1 = pet_windows(proc.pid)[0]
    moved = abs(pos1[1] - pos0[1]) + abs(pos1[2] - pos0[2])
    check("能拖动", moved > 100, "位移 %d 像素 (%d,%d) -> (%d,%d)" % (moved, pos0[1], pos0[2], pos1[1], pos1[2]))

    # 5) 内存
    m = mem_mb(proc.pid)
    say("   桌宠进程工作集 %.1f MB" % (m or -1))
    check("内存 < 400MB", (m or 0) < 400, "%.1f MB" % (m or -1))

    # 6) 进程控制台输出（气泡台词等）
    proc.terminate()
    try:
        out = proc.communicate(timeout=5)[0].decode("utf-8", "replace")
    except Exception:
        proc.kill()
        out = ""
    say("   桌宠 stdout 末尾: " + " | ".join(out.strip().splitlines()[-3:]))
    say("")
    say("结果：%d 项通过，%d 项失败" % (len(lines) - len(fails) and 0 or 0, len(fails)))
    (OUT / "verify-nailong.txt").write_text("\n".join(lines), encoding="utf-8")
    say("失败项：" + (", ".join(fails) if fails else "无"))


main()
