# -*- coding: utf-8 -*-
"""verify-exe-v14.py —— 打包好的 exe 真机验收（不依赖屏幕可见性）。

为什么不用截屏比像素：这台机器上锁屏窗口（Windows 默认锁屏界面）会盖在一切之上，
抓屏抓到的是它，于是"桌宠没动/不可见"这种误判就出来了（这次真踩了）。
改成 PrintWindow 直接抓桌宠窗口自己的内容 —— 被盖住、锁屏都不影响；
点击/拖拽改用 PostMessage 投递鼠标消息，同样不依赖窗口在最上层。

用法：python tools/verify-exe-v14.py dist/DeskPet-Lite/DeskPet.exe
"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
from PIL import Image, ImageChops

BASE = Path(r"D:/dsh/deskpet")
OUT = BASE / "selftest"
EXE = Path(sys.argv[1]) if len(sys.argv) > 1 else (BASE / "dist" / "DeskPet-Lite" / "DeskPet.exe")
TAG = EXE.parent.name
TMP = OUT / ("appdata-exe-" + TAG)
lines, fails = [], []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    print(lines[-1], flush=True)


def check(name, ok, detail=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok:
        fails.append(name)


ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.WinDLL("user32", use_last_error=True)
g = ctypes.WinDLL("gdi32")
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u.mouse_event.argtypes = [wintypes.DWORD] * 5
u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
u.GetWindowLongW.restype = ctypes.c_long
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE = 0x0201, 0x0202, 0x0200
MK_LBUTTON = 0x0001
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST = 0x80, 0x08000000, 0x8

h_pet = None            # 当前被测的桌宠窗口（real_drag / post_click 要用）


def hwnds(pid):
    out = []
    EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid and u.IsWindowVisible(h):
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 20:
                out.append((h, r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    u.EnumWindows(EP(cb), 0)
    return out


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def grab(h, w, hh):
    hdc = u.GetWindowDC(h)
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, hh)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(h, mdc, 2)                     # PW_RENDERFULLCONTENT
    bi = BIH()
    bi.biSize = ctypes.sizeof(bi); bi.biWidth = w; bi.biHeight = -hh
    bi.biPlanes = 1; bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * hh * 4)
    g.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    g.DeleteObject(bmp); g.DeleteDC(mdc); u.ReleaseDC(h, hdc)
    return Image.frombuffer("RGB", (w, hh), buf, "raw", "BGRX", 0, 1)


def diff(a, b, thr=12):
    d = ImageChops.difference(a, b).convert("L")
    return sum(1 for v in d.get_flattened_data() if v > thr)


def post_click(h, x, y):
    lp = (y << 16) | (x & 0xFFFF)
    u.PostMessageW(h, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.05)
    u.PostMessageW(h, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    time.sleep(0.08)
    u.PostMessageW(h, WM_LBUTTONUP, 0, lp)


def real_drag(x0, y0, x1, y1, steps=14):
    """拖拽：**光标位置 + PostMessage** 两条一起用。

    · 只用 mouse_event：锁屏（Windows 默认锁屏界面）盖在上面时，真实输入被它吃掉，
      桌宠收不到消息 —— 上一轮就是这么"拖不动"的（位移 32px，其实是漫游走的）。
    · 只用 PostMessage：Qt 取的是真实光标位置来算全局坐标，合成消息里光标不在窗口上，
      mouseMoveEvent 算出来位移是 0（更早踩过）。
    所以每次投递消息前先把光标挪到位。"""
    u.SetCursorPos(x0, y0)
    time.sleep(0.2)
    lp = (y0 << 16) | (x0 & 0xFFFF)
    u.PostMessageW(h_pet, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.1)
    u.PostMessageW(h_pet, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    for i in range(1, steps + 1):
        px, py = int(x0 + (x1 - x0) * i / steps), int(y0 + (y1 - y0) * i / steps)
        u.SetCursorPos(px, py)
        u.PostMessageW(h_pet, WM_MOUSEMOVE, MK_LBUTTON, ((py & 0xFFFF) << 16) | (px & 0xFFFF))
        time.sleep(0.03)
    time.sleep(0.05)
    u.PostMessageW(h_pet, WM_LBUTTONUP, 0, ((y1 & 0xFFFF) << 16) | (x1 & 0xFFFF))


def post_drag(h, x0, y0, x1, y1, steps=14):
    lp = (y0 << 16) | (x0 & 0xFFFF)
    u.PostMessageW(h, WM_MOUSEMOVE, 0, lp)
    time.sleep(0.05)
    u.PostMessageW(h, WM_LBUTTONDOWN, MK_LBUTTON, lp)
    for i in range(1, steps + 1):
        px, py = int(x0 + (x1 - x0) * i / steps), int(y0 + (y1 - y0) * i / steps)
        u.PostMessageW(h, WM_MOUSEMOVE, MK_LBUTTON, (py << 16) | (px & 0xFFFF))
        time.sleep(0.02)
    time.sleep(0.05)
    u.PostMessageW(h, WM_LBUTTONUP, 0, (y1 << 16) | (x1 & 0xFFFF))


def main():
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(BASE / "tools" / "kill-all-deskpet.ps1")],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)
    (TMP / "DeskPet").mkdir(parents=True, exist_ok=True)
    # 试玩包里带了 portable.txt，数据写在 exe 旁边的 data\ —— 走那条路时才验得到真东西
    portable = (EXE.parent / "portable.txt").exists()
    pdata = (EXE.parent / "data") if portable else (TMP / "DeskPet")
    pdata.mkdir(parents=True, exist_ok=True)
    say("数据目录模式：%s" % ("便携（exe 旁边 data\）" if portable else "%APPDATA%"))
    (pdata / "config.json").write_text(json.dumps(
        {"character": "nailong", "x": 20, "y": 300, "scale": 1.6, "sound": False,
         "mode": "desktop"}), encoding="utf-8")
    env = dict(os.environ)
    env["APPDATA"] = str(TMP)
    say("被测 exe：%s" % EXE)
    proc = subprocess.Popen([str(EXE), "--autostart"], cwd=str(EXE.parent), env=env)
    pet_pid = None
    for _ in range(40):
        time.sleep(0.5)
        f = pdata / "pet.pid"
        if f.exists():
            try:
                # pet.pid 现在是 "<pid> <创建时刻>"（用来识破 pid 复用），取第一个字段
                pet_pid = int(f.read_text().strip().split()[0])
                break
            except Exception:
                pass
    check("控制台 --autostart 拉起了桌宠进程", pet_pid is not None, "pid=%s" % pet_pid)
    if pet_pid is None:
        proc.kill()
        return
    ws = []
    for _ in range(20):
        ws = hwnds(pet_pid)
        if ws:
            break
        time.sleep(0.5)
    if not ws:
        check("桌宠窗口出现", False)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL)
        return
    h, wx, wy, ww, wh = ws[0]
    global h_pet
    h_pet = h
    check("桌宠窗口出现", True, "位置(%d,%d) 尺寸%dx%d" % (wx, wy, ww, wh))
    say("   pets.json: %s" % (pdata / "pets.json").read_text(
        encoding="utf-8").replace(chr(10), " ").replace("  ", ""))
    # exstyle 是 showEvent 里 apply_layer() 设的，窗口刚出现时可能还没设完 —— 轮询等一下
    ex = 0
    for _ in range(20):
        ex = u.GetWindowLongW(h, GWL_EXSTYLE)
        if (ex & WS_EX_NOACTIVATE) and (ex & WS_EX_TOOLWINDOW):
            break
        time.sleep(0.2)
    check("不抢焦点 / 不上任务栏（NOACTIVATE+TOOLWINDOW）",
          bool(ex & WS_EX_NOACTIVATE) and bool(ex & WS_EX_TOOLWINDOW), "exstyle=0x%x" % (ex & 0xFFFFFFFF))
    check("贴壁纸层（不是置顶窗口）", not (ex & WS_EX_TOPMOST), "")

    f0 = grab(h, ww, wh)
    nonbg = sum(1 for v in f0.getchannel("A" if f0.mode == "RGBA" else "R").get_flattened_data() if v > 8)
    # 角色画出来了没有：窗口里应有一大片和边角底色不同的像素
    px = f0.load()
    corner = px[2, 2]
    painted = 0
    for yy in range(0, wh, 3):
        for xx in range(0, ww, 3):
            c = px[xx, yy]
            if abs(c[0] - corner[0]) + abs(c[1] - corner[1]) + abs(c[2] - corner[2]) > 40:
                painted += 1
    check("角色真的画在窗口里", painted > 500, "与角点底色不同的采样点 %d（采样步长 3）" % painted)

    # 动画检测：采样三次取最大差值。PrintWindow 偶尔会抓到两张一样的帧（窗口刚好在重绘），
    # 单次采样会出现假失败 —— 真实情况是"只要有一次不一样，就说明她在动"。
    anim = 0
    for _ in range(3):
        time.sleep(0.6)
        a = grab(h, ww, wh)
        time.sleep(0.15)
        anim = max(anim, diff(a, grab(h, ww, wh)))
    check("动画在播放（源 GIF 30ms/帧）", anim > 2000, "150ms 内变化像素 %d" % anim)

    # 点击：反馈是"气泡画在精灵上方那条区域"
    # 精灵高度：默认按内置奶龙（160 帧 × 1.6 倍 × dpr1.5）；发布包的占位形象是 320 帧 × 1.0
    sprite_h = int(os.environ.get("PET_SPRITE_H", 160 * 1.6 * 1.5))
    top_h = max(20, wh - sprite_h - 2)
    before = grab(h, ww, wh).crop((0, 0, ww, top_h))
    post_click(h, ww // 2, wh - sprite_h // 2)
    time.sleep(0.5)
    after = grab(h, ww, wh).crop((0, 0, ww, top_h))
    bub = diff(before, after)
    check("点击弹出气泡", bub > 300, "气泡区变化像素 %d" % bub)

    time.sleep(2.6)
    r0 = hwnds(pet_pid)[0]
    real_drag(r0[1] + r0[3] // 2, r0[2] + r0[4] - sprite_h // 2,
              r0[1] + r0[3] // 2 + 260, r0[2] + r0[4] - sprite_h // 2 - 120)
    time.sleep(1.2)                      # 等惯性走完
    r1 = hwnds(pet_pid)[0]
    moved = abs(r1[1] - r0[1]) + abs(r1[2] - r0[2])
    check("能拖动", moved > 100, "位移 %d 像素 (%d,%d)->(%d,%d)" % (moved, r0[1], r0[2], r1[1], r1[2]))

    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdout=subprocess.DEVNULL)
    time.sleep(0.8)
    check("关掉控制台能连桌宠一起收掉", not hwnds(pet_pid), "")
    say("")
    say("失败项：" + (", ".join(fails) if fails else "无"))
    (OUT / ("verify-exe-%s.txt" % TAG)).write_text("\n".join(lines), encoding="utf-8")


main()
