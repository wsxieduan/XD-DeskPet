# -*- coding: utf-8 -*-
"""test-bond.py —— 桌宠"伙伴绑定 + 一起转圈"（阿酉需求卡功能二的最小版）验收。

主人的原话：两只桌宠围着某个点一起转圈就行，可以简单。
所以验收就盯三件事：绑得上、真的在**同一个圆周上相对运动**、时间到了各自停下。

用独立的 APPDATA 跑，不碰主人的数据。
"""
import ctypes, json, math, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
ctypes.windll.shcore.SetProcessDpiAwareness(2)
TMP = BASE / "selftest" / "appdata-bond"
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


def foot_center(pid):
    """精灵脚底中心（逻辑坐标）—— 窗口底边中点。精灵水平居中、贴在窗口底部。"""
    out = []

    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid and u.IsWindowVisible(h):
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left > 20:
                out.append(((r.left + r.right) / 2.0 / DPR, r.bottom / DPR))
        return True

    u.EnumWindows(EP(cb), 0)
    return out[0] if out else None


def sprite_center(pid, scale=1.4, sprite_h=160):
    """精灵中心（逻辑坐标）：窗口底边往上 sprite_h/2 —— 圆周转的是精灵中心，不是窗口。"""
    fc = foot_center(pid)
    if fc is None:
        return None
    return (fc[0], fc[1] - (sprite_h * scale * DPR) / 2.0 / DPR)


def win_pid(pet_id):
    for _ in range(40):
        time.sleep(0.5)
        p = petlist.get_pet(pet_id) or {}
        pid = p.get("pid")
        if pid and foot_center(int(pid)):
            return int(pid)
    return None


say("== 1. 绑定关系（双向写） ==")
p1 = petlist.add_pet("nailong", 300, 300, 1.4)
p2 = petlist.add_pet("nailong", 800, 300, 1.4)
petlist.set_bond(p1["id"], p2["id"])
a = petlist.get_pet(p1["id"])
b = petlist.get_pet(p2["id"])
say("   %s.bond=%s   %s.bond=%s" % (a["id"], a.get("bond"), b["id"], b.get("bond")))
check("A 认 B 是伴侣", a.get("bond") == b["id"], str(a.get("bond")))
check("B 也认 A（双向）", b.get("bond") == a["id"], str(b.get("bond")))
petlist.set_bond(p1["id"], None)
check("解除后两边都清掉",
      not (petlist.get_pet(p1["id"]) or {}).get("bond")
      and not (petlist.get_pet(p2["id"]) or {}).get("bond"), "")
petlist.set_bond(p1["id"], p2["id"])

say()
say("== 2. 起两只桌宠 ==")
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
ctl.start_pet(p1["id"])
ctl.start_pet(p2["id"])
pid1 = win_pid(p1["id"])
pid2 = win_pid(p2["id"])
say("   pid1=%s pid2=%s" % (pid1, pid2))
check("两只都起来了", bool(pid1) and bool(pid2), "%s / %s" % (pid1, pid2))
if not (pid1 and pid2):
    say("结果: 失败: 桌宠没起来")
    sys.exit(1)

say()
say("== 3. 写一份「一起转圈」的计划（6 秒，半径 110） ==")
R = 110
CX, CY = 640.0, 380.0
DUR = 6.0
# spin=False：这一条只验"公转轨迹是不是圆"，翻转由 test-bond-spin 单独验
# （翻转会把绘制区放大 1.45 倍，精灵中心的位置得跟着换算，两件事分开测才看得清）
plan = {"pair": [p1["id"], p2["id"]], "center": [CX, CY], "radius": R, "angle0": 0.0,
        "t0": time.time(), "speed": 0.8, "duration": DUR, "spin": False,
        "offsets": {p1["id"]: 0.0, p2["id"]: math.pi}}
paths.atomic_write_text(paths.data_root() / "bond.json", json.dumps(plan))
say("   圆心 (%.0f, %.0f) 半径 %d  时长 %.0fs" % (CX, CY, R, DUR))

samples = []
t0 = time.time()
while time.time() - t0 < DUR - 1.5:
    fa, fb = foot_center(pid1), foot_center(pid2)
    # 前 0.8 秒不算：两只每 120ms 才看一次计划，采样太快会把"还没动身"的初始位置也收进来
    if fa and fb and time.time() - t0 > 0.8:
        samples.append((fa, fb))
    time.sleep(0.15)
say("   采到 %d 个位置样本（丢掉最前面还没动身的）" % len(samples))


def dist(p, q, cy=CY):
    return math.hypot(p[0] - q[0], (p[1] - 0) - (q[1] - 0))


dists = [dist(fa, fb) for fa, fb in samples]
moved_a = max(s[0][0] for s in samples) - min(s[0][0] for s in samples)
moved_b = max(s[1][0] for s in samples) - min(s[1][0] for s in samples)
say("   两只间距：最小 %.0f 最大 %.0f（期望恒等于 2r=%d）" % (min(dists), max(dists), 2 * R))
say("   各自水平移动量：A %.0fpx  B %.0fpx" % (moved_a, moved_b))
check("两只都在动（不是只有一只在跑）", moved_a > 60 and moved_b > 60,
      "A %.0f / B %.0f" % (moved_a, moved_b))
check("两只始终相隔一个直径（在同一个圆周上相对）",
      abs(sum(dists) / len(dists) - 2 * R) < 45 and (max(dists) - min(dists)) < 60,
      "均值 %.0f，波动 %.0f" % (sum(dists) / len(dists), max(dists) - min(dists)))
# 圆心距：脚底中心比精灵中心低一点点，用均值反推一个偏移再核对半径
# 用"精灵中心"核对半径（脚底中心比精灵中心低半个身高，拿它算距离会随相位变化，
# 那是测量假象，不是桌宠跑偏了 —— 这一版就踩了）
radii = []
for fa, fb in samples:
    for fc in (fa, fb):
        sc = (fc[0], fc[1] - (160 * 1.4) / 2.0)
        radii.append(math.hypot(sc[0] - CX, sc[1] - CY))
say("   精灵中心到圆心：最小 %.0f 最大 %.0f（期望 ≈ 半径 110）" % (min(radii), max(radii)))
check("两只都严格贴着半径 110 的圆周跑",
      abs(sum(radii) / len(radii) - 110) < 15 and (max(radii) - min(radii)) < 25,
      "均值 %.0f 波动 %.0f" % (sum(radii) / len(radii), max(radii) - min(radii)))

say()
say("== 4. 时间到了要各自停下 ==")
time.sleep(2.0)
s1a, s1b = foot_center(pid1), foot_center(pid2)
time.sleep(1.2)
s2a, s2b = foot_center(pid2 and pid1), foot_center(pid2)
da = math.hypot(s2a[0] - s1a[0], s2a[1] - s1a[1])
db = math.hypot(s2b[0] - s1b[0], s2b[1] - s1b[1])
say("   停下后 1.2 秒内的位移：A %.0fpx  B %.0fpx" % (da, db))
check("计划结束后两只都不再转（回到正常状态）", da < 8 and db < 8, "A %.0f / B %.0f" % (da, db))

say()
say("== 5. 桌宠自己能发起（右键菜单那条路） ==")
import importlib.util as _iu
spec2 = _iu.spec_from_file_location("deskpet", BASE / "deskpet.py")
dp = _iu.module_from_spec(spec2)
spec2.loader.exec_module(dp)
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
pet = dp.DeskPet(p1["id"])
ok = pet.start_bond_plan()
plan2 = json.loads((paths.data_root() / "bond.json").read_text(encoding="utf-8"))
say("   计划: pair=%s 圆心=%s 相位=%s" % (plan2.get("pair"),
                                        [round(v) for v in plan2.get("center", [])],
                                        plan2.get("offsets")))
check("桌宠能写计划文件", ok and plan2.get("pair") == [p1["id"], p2["id"]], str(ok))
check("两只的相位相差半圈（一左一右，不会撞在一起）",
      abs(abs(plan2.get("offsets", {}).get(p1["id"], 0)
              - plan2.get("offsets", {}).get(p2["id"], 0)) - math.pi) < 0.01,
      str(plan2.get("offsets")))
print("   [debug] 关掉进程内那只", flush=True)
pet.close()
print("   [debug] 关掉了，准备 stop_all_pets", flush=True)
ctl.stop_all_pets()
print("   [debug] stop_all_pets 返回", flush=True)
time.sleep(1.0)
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-bond.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
