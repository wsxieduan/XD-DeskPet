# -*- coding: utf-8 -*-
"""test-bond-spin.py —— "魔性版"一起转圈：转速可调 + 整只跟着翻转。

  · 转速：计划里 speed=2.6 时，两只公转的角速度要明显快于 0.8（按位置反算角度）
  · 翻转：转 180° 时整个精灵是**倒过来的**（用冻结帧抓图，比对"把 180° 的图翻转回来"）
用独立的 APPDATA 跑，不碰主人的数据。
"""
import ctypes, json, math, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
TMP = BASE / "selftest" / "appdata-spin"
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
(TMP / "DeskPet" / "config.json").write_text(json.dumps(
    {"character": "nailong", "scale": 1.4, "sound": False, "mode": "desktop",
     "behavior": {"roam": False, "flee": False, "inertia": False, "recycle": False}}),
    encoding="utf-8")
os.environ["APPDATA"] = str(TMP)
import paths
paths.migrate_from_app_dir()
import petlist
lines, fails = [], []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    print(lines[-1], flush=True)


def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok:
        fails.append(n)


u = ctypes.WinDLL("user32")
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
DPR = 1.5


def sprite_center(pid, scale=1.4):
    out = []

    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid and u.IsWindowVisible(h):
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 20:
                out.append(((r.left + r.right) / 2.0 / DPR,
                            (r.bottom - 160 * scale * DPR / 2.0) / DPR))
        return True

    u.EnumWindows(EP(cb), 0)
    return out[0] if out else None


def win_pid(pet_id):
    for _ in range(40):
        time.sleep(0.5)
        pid = (petlist.get_pet(pet_id) or {}).get("pid")
        if pid and sprite_center(int(pid)):
            return int(pid)
    return None


say("== 1. 转速可调 ==")
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
p1 = petlist.add_pet("nailong", 320, 320, 1.4)
p2 = petlist.add_pet("nailong", 820, 320, 1.4)
petlist.set_bond(p1["id"], p2["id"])
ctl.start_pet(p1["id"])
ctl.start_pet(p2["id"])
pid1, pid2 = win_pid(p1["id"]), win_pid(p2["id"])
check("两只都起来了", bool(pid1) and bool(pid2), "%s / %s" % (pid1, pid2))
if not (pid1 and pid2):
    sys.exit(1)

CX, CY, R = 620.0, 360.0, 110


def run(speed, seconds=4.0):
    """跑一段，返回实测角速度（用两只里靠前那只的位置反算角度）。"""
    plan = {"pair": [p1["id"], p2["id"]], "center": [CX, CY], "radius": R, "angle0": 0.0,
            "t0": time.time(), "speed": speed, "duration": seconds,
            "spin": False, "offsets": {p1["id"]: 0.0, p2["id"]: math.pi}}
    paths.atomic_write_text(paths.data_root() / "bond.json", json.dumps(plan))
    time.sleep(0.6)                      # 等两只读到计划
    samples = []
    t0 = time.time()
    while time.time() - t0 < seconds - 1.6:
        c = sprite_center(pid1)
        if c:
            samples.append((time.time() - t0,
                            math.atan2(c[1] - CY, c[0] - CX)))
        time.sleep(0.1)
    # 解缠绕后线性拟合出角速度
    un = [samples[0][1]]
    for i in range(1, len(samples)):
        d = samples[i][1] - samples[i - 1][1]
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        un.append(un[-1] + d)
    dt = samples[-1][0] - samples[0][0]
    return (un[-1] - un[0]) / dt, len(samples)


w_slow, n1 = run(0.8)
w_fast, n2 = run(2.6)
say("   慢档实测 %.2f 弧度/秒（%d 个样本）   魔性档实测 %.2f 弧度/秒（%d 个样本）"
    % (w_slow, n1, w_fast, n2))
check("慢档转速接近设定值 0.8", abs(w_slow - 0.8) < 0.25, "%.2f" % w_slow)
check("魔性档转速接近设定值 2.6", abs(w_fast - 2.6) < 0.5, "%.2f" % w_fast)
check("魔性档确实明显更快（>2 倍）", w_fast > w_slow * 2, "%.2f vs %.2f" % (w_fast, w_slow))

say()
say("== 2. 整只跟着翻转（转 180° = 倒过来） ==")
paths.atomic_write_text(paths.data_root() / "bond.json", json.dumps({"pair": []}))
ctl.stop_all_pets()
time.sleep(1.0)

spec2 = importlib.util.spec_from_file_location("deskpet", BASE / "deskpet.py")
dp = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(dp)
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from PIL import Image, ImageChops
app = QApplication.instance() or QApplication([])
pet = dp.DeskPet(None)
pet.show()
app.processEvents()
time.sleep(0.6)
pet.timer.stop()                      # 冻住动画帧，专心看旋转
app.processEvents()
w_norm, h_norm = pet.sprite_w, pet.sprite_h


def grab_pil():
    """只截"精灵绘制区"那一块再比。

    整窗截图里还包含头顶的气泡区和大片透明边距，那些地方不随旋转变化 ——
    不裁掉的话，旋转 180° 的对比会被它们稀释成"看起来对不上"（第一版就吃了这个亏）。"""
    app.processEvents()
    img = pet.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    full = Image.frombytes("RGBA", (img.width(), img.height()),
                           bytes(img.constBits())).convert("RGB")
    k = img.width() / float(pet.width())
    box = (int(pet.sprite_x * k), int(pet.bubble_h * k),
           int((pet.sprite_x + pet.sprite_w) * k), int((pet.bubble_h + pet.sprite_h) * k))
    return full.crop(box)


def diff(a, b):
    d = ImageChops.difference(a, b).convert("L")
    return sum(1 for v in d.get_flattened_data() if v > 16)


def best_diff(a, b, rng=2):
    """允许 ±2 像素的平移再比：绘制区放大 1.45 倍后，旋转中心的取整会有半像素误差，
    严格对齐去比会把"其实就是同一张图"误判成不一样（踩过）。"""
    best = None
    for dx in range(-rng, rng + 1):
        for dy in range(-rng, rng + 1):
            shifted = ImageChops.offset(b, dx, dy)
            d = diff(a, shifted)
            best = d if best is None else min(best, d)
    return best


pet._bond_rot = 0.0
pet.update()
g0 = grab_pil()
pet._set_spin(True)
app.processEvents()
time.sleep(0.4)          # 等窗口按放大后的尺寸落定，再取样（不然会比到两次不同的几何）
app.processEvents()
w_spin, h_spin = pet.sprite_w, pet.sprite_h
pet._bond_rot = 0.0
pet.update()
g0s = grab_pil()
pet._bond_rot = 180.0
pet.update()
g180 = grab_pil()
say("   绘制区：不翻转 %dx%d → 翻转 %dx%d（放大了 %.2f 倍，给四个角留位置）"
    % (w_norm, h_norm, w_spin, h_spin, w_spin / float(w_norm)))
check("翻转时绘制区放大到外接正方形（不然 45° 时会缺角）",
      1.25 < w_spin / float(w_norm) < 1.6, "%.2f" % (w_spin / float(w_norm)))
d_flip_back = best_diff(g0s, g180.transpose(Image.ROTATE_180))
d_direct = best_diff(g0s, g180)
d_self = best_diff(g0s, g0s.transpose(Image.ROTATE_180))
say("   角度=%.0f°  index=%d  track=%s  绘制区 %dx%d@(%d,%d)"
    % (pet._bond_rot, pet.index, pet.track, pet.sprite_w, pet.sprite_h,
       pet.sprite_x, pet.bubble_h))
say("   像素差：180°图翻转回来 vs 原图 = %d；直接比 = %d；原图自翻转 = %d"
    % (d_flip_back, d_direct, d_self))
check("转 180° 后整只是倒过来的（翻转回来能对上原图）",
      d_flip_back < d_self * 0.45 and d_flip_back < d_direct * 0.45,
      "%d vs 自翻转 %d" % (d_flip_back, d_self))
pet._set_spin(False)
check("关掉翻转后绘制区回到原尺寸", (pet.sprite_w, pet.sprite_h) == (w_norm, h_norm),
      "%dx%d" % (pet.sprite_w, pet.sprite_h))
pet.close()
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-bond-spin.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
