# -*- coding: utf-8 -*-
"""test-toggle2.py —— 复现/回归：召唤之后点行为开关，不该多冒出一只桌宠，开关也不该自己弹回去。

复现的现象（主人报的）：召唤完桌宠后，点"躲开鼠标"→ 桌面上多出一只，而且勾选状态自己回来了。
怀疑两处：
  ① deskpet.write_pid() 无论是不是多实例都写 pet.pid → 控制台 apply() 里
     "if pet_running(): 重启单宠物模式那只" 被误判成立 → 多起一只。
  ② 开关被 refresh() 的 _syncing 吞掉 → 一秒后按 config 重新勾上。
"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
TMP = BASE / "selftest" / "appdata-toggle2"
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
os.environ["APPDATA"] = str(TMP)
ctypes.windll.shcore.SetProcessDpiAwareness(2)

from PySide6.QtWidgets import QApplication
app = QApplication([])
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
import paths, petlist

u = ctypes.WinDLL("user32")
u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def pet_windows():
    """桌面上真正有几个"桌宠"窗口（标题就是"桌宠"），按 pid 去重计数。"""
    out = {}

    def cb(h, l):
        if u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(128)
            u.GetWindowTextW(h, b, 128)
            if b.value == "桌宠":
                wp = wintypes.DWORD()
                u.GetWindowThreadProcessId(h, ctypes.byref(wp))
                out[wp.value] = out.get(wp.value, 0) + 1
        return True

    u.EnumWindows(EP(cb), 0)
    return out


def cfg_flee():
    try:
        return json.loads(paths.config_path().read_text(encoding="utf-8")).get("behavior", {}).get("flee")
    except Exception:
        return None


w = ctl.Console()
w.show()
app.processEvents()
say("开始的桌宠窗口: " + str(pet_windows()))

say()
say("== 1. 点「＋ 召唤一个桌宠」 ==")
w.on_add_pet()
time.sleep(3.5)
app.processEvents()
pets = petlist.load_pets()
wins = pet_windows()
say("pets.json: " + json.dumps(pets, ensure_ascii=False))
say("桌宠窗口: " + str(wins))
check("召唤后桌面上正好一只", len(wins) == 1, str(wins))
check("flee 默认是开（没写过时按默认值算开）", cfg_flee() in (True, None), str(cfg_flee()))

say()
say("== 2. 点「躲开鼠标」关掉它（模拟真实点击） ==")
check("点击前勾选状态是开", w.cb_flee.isChecked(), str(w.cb_flee.isChecked()))
w.cb_flee.click()
app.processEvents()
time.sleep(1.0)
say("  点击后立刻：勾选=%s  config.flee=%s  窗口=%s" % (w.cb_flee.isChecked(), cfg_flee(), pet_windows()))
time.sleep(3.0)
app.processEvents()
wins2 = pet_windows()
say("  3 秒后：勾选=%s  config.flee=%s  窗口=%s" % (w.cb_flee.isChecked(), cfg_flee(), wins2))
check("config 里真的写成了关", cfg_flee() is False, str(cfg_flee()))
check("勾选状态没有自己弹回去", w.cb_flee.isChecked() is False, str(w.cb_flee.isChecked()))
check("点开关没有多冒出一只桌宠", len(wins2) == 1, str(wins2))

say()
say("== 3. 再打开它 ==")
w.cb_flee.click()
time.sleep(3.0)
app.processEvents()
wins3 = pet_windows()
say("  勾选=%s  config.flee=%s  窗口=%s" % (w.cb_flee.isChecked(), cfg_flee(), wins3))
check("重新打开也写进 config", cfg_flee() is True, str(cfg_flee()))
check("再次切换也没多冒出桌宠", len(wins3) == 1, str(wins3))

ctl.stop_all_pets()
time.sleep(1.0)
check("全部关闭后桌面干净", len(pet_windows()) == 0, str(pet_windows()))
w.close()
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-toggle2.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
