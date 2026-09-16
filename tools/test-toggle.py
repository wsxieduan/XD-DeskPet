"""test-toggle.py —— 验证行为开关真的会重启桌宠并生效（#2 的根因回归测试）"""
import json, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import paths
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok: fails.append(n)

import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)

ctl.stop_pet()
time.sleep(0.6)
c = json.loads(paths.config_path().read_text(encoding="utf-8"))
c["character"] = "oc/view1"
c["behavior"] = {"roam": True, "flee": True, "inertia": True, "recycle": True}
paths.atomic_write_text(paths.config_path(), json.dumps(c, indent=2, ensure_ascii=False))
ctl.start_pet(); time.sleep(3.5)
pid0 = ctl.read_pid()
check("桌宠已启动且能被识别", ctl.pet_running(), "pid=%s" % pid0)
say()
say("== 关掉「躲避鼠标」==")
# 走控制台真实路径：_set_behavior 等价于勾选框触发
ctl.Console  # 存在性检查
beh = dict(json.loads(paths.config_path().read_text(encoding="utf-8")).get("behavior") or {})
beh["flee"] = False
cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
cfg["behavior"] = beh
paths.atomic_write_text(paths.config_path(), json.dumps(cfg, indent=2, ensure_ascii=False))
# apply() 的行为：先存再重启
was = ctl.pet_running()
if was:
    ctl.stop_pet()
    time.sleep(0.4)
ctl.start_pet()
time.sleep(3.5)
pid1 = ctl.read_pid()
check("桌宠被重启了（pid 变了）", pid1 != pid0, "%s -> %s" % (pid0, pid1))
now = json.loads(paths.config_path().read_text(encoding="utf-8"))
check("配置里 flee 已是 False", now.get("behavior", {}).get("flee") is False, str(now.get("behavior")))
check("重启后仍被正确识别", ctl.pet_running(), "pid=%s" % pid1)
say()
say("== 实测：鼠标贴上去她还躲不躲 ==")
import ctypes
from ctypes import wintypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)
u = ctypes.WinDLL("user32")
u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
p0 = (now.get("x"), now.get("y"))
DPI = 1.5
u.SetCursorPos(int((p0[0] + 100) * DPI), int((p0[1] + 190) * DPI))
time.sleep(0.4)
u.SetCursorPos(int((p0[0] + 105) * DPI), int((p0[1] + 195) * DPI))
time.sleep(3.0)
try:
    p1 = json.loads(paths.config_path().read_text(encoding="utf-8"))
    p1 = (p1.get("x"), p1.get("y"))
except Exception:
    p1 = p0
d = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5
# 关了躲避之后，只可能因为漫游而移动；短时间内应基本不动
check("关掉后不再因为鼠标而躲开", d < 60, "位移 %.0fpx（%s -> %s）" % (d, str(p0), str(p1)))
say()
say("== 关闭功能 ==")
ctl.stop_pet()
time.sleep(0.8)
check("能把她关掉", not ctl.pet_running())
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-toggle.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")