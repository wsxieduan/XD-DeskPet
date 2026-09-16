"""test-behavior.py —— 验证漫游 / 躲避鼠标 / 拖拽惯性"""
import ctypes, json, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import paths
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(name, ok, detail=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok: fails.append(name)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass
u = ctypes.WinDLL("user32")
u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
u.mouse_event.argtypes = [wintypes.DWORD] * 5

def kill():
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(BASE / "tools" / "kill-pets.ps1")],
                   capture_output=True, creationflags=0x08000000)
    time.sleep(1.2)

def start(mode="topmost"):
    c = json.loads(paths.config_path().read_text(encoding="utf-8"))
    c.update({"mode": mode, "character": "oc/view1", "scale": 1.0, "x": 700, "y": 380})
    c["behavior"] = {"roam": True, "flee": True, "inertia": True, "recycle": True}
    paths.config_path().write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
    lf = open(BASE / "selftest" / "beh.log", "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, str(BASE / "deskpet.py")], cwd=str(BASE),
                         stdout=lf, stderr=subprocess.STDOUT)
    time.sleep(4)
    return p

def pet_pos():
    # 桌宠漫游时会频繁改位置，读的时候要容忍"刚好撞上写入"的瞬间
    for _ in range(6):
        try:
            c = json.loads(paths.config_path().read_text(encoding="utf-8"))
            return (c.get("x"), c.get("y"))
        except Exception:
            time.sleep(0.08)
    return (None, None)

kill()
p = start()
say("启动位置: %s" % str(pet_pos()))
say()

say("== 1. 躲避鼠标 ==")
x, y = pet_pos()
DPI = 1.5
u.SetCursorPos(int((x + 105) * DPI), int((y + 200) * DPI))
time.sleep(0.4)
u.SetCursorPos(int((x + 110) * DPI), int((y + 205) * DPI))   # 动一下确保触发
before = pet_pos()
time.sleep(3.5)
after = pet_pos()
d = ((after[0] - before[0]) ** 2 + (after[1] - before[1]) ** 2) ** 0.5
check("鼠标靠近后她跑开了", d > 40, "%s -> %s (移动 %.0fpx)" % (str(before), str(after), d))

say()
say("== 2. 漫游（等最多 30 秒）==")
u.SetCursorPos(40, 40)          # 光标挪远，避免一直触发躲避
base = pet_pos()
moved = 0
for i in range(30):
    time.sleep(1)
    now = pet_pos()
    dd = ((now[0] - base[0]) ** 2 + (now[1] - base[1]) ** 2) ** 0.5
    if dd > 60:
        moved = dd
        break
check("会自己溜达", moved > 60, "位移 %.0fpx（%s -> %s）" % (moved, str(base), str(pet_pos())))

say()
say("== 3. 拖拽惯性 ==")
x, y = pet_pos()
# 朝空间大的一侧拖 —— 否则会撞到屏幕边缘，测出来的是"撞墙"不是"惯性"
import ctypes as _c
scr = u.GetSystemMetrics(0) // int(DPI)
sign = -1 if x > scr // 2 else 1
cx, cy = int((x + 105) * DPI), int((y + 200) * DPI)
u.SetCursorPos(cx, cy)
time.sleep(0.4)
u.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.15)
for i in range(1, 9):
    u.SetCursorPos(cx + sign * int(i * 22 * DPI), cy)
    time.sleep(0.02)
u.mouse_event(0x0004, 0, 0, 0, 0)
at_release = pet_pos()
time.sleep(1.2)
after_glide = pet_pos()
glide = (after_glide[0] - at_release[0]) * sign
check("松手后还往前滑了一段", glide > 30, "滑了 %dpx（%s -> %s，朝%s）" % (
    glide, str(at_release), str(after_glide), "左" if sign < 0 else "右"))

say()
say("== 4. 行为日志 ==")
try:
    log = (BASE / "selftest" / "beh.log").read_text(encoding="utf-8", errors="replace")
    for l in log.strip().splitlines()[:12]:
        say("   " + l)
except Exception as e:
    say("   (读不到日志)")
p.terminate()
kill()
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-behavior.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")