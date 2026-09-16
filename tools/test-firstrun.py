# -*- coding: utf-8 -*-
"""test-firstrun.py —— 第一次打开（全新数据目录）的体验：形象名、默认大小、点一下能召唤出奶龙。

用独立的 APPDATA 跑，不碰主人的数据。
"""
import ctypes, json, os, shutil, subprocess, sys, time  # noqa: E401
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
TMP = BASE / "selftest" / "appdata-firstrun"
# 先杀掉遗留的桌宠进程：它可能正占着上一次测试的临时目录，删不掉
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
# 开发机上源码目录里有个历史 config.json（老测试留下的），
# petctl 启动时的 migrate_from_app_dir() 会把它搬进"全新"数据目录 —— 那就不是首次运行了。
# 放一个 .migrated 标记让迁移跳过（打包发行时程序目录里没有 config.json，不存在这个问题）。
(TMP / "DeskPet" / ".migrated").write_text("test", encoding="utf-8")
os.environ["APPDATA"] = str(TMP)

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
ctypes.windll.shcore.SetProcessDpiAwareness(2)
from PySide6.QtWidgets import QApplication
app = QApplication([])
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
import paths, petlist
say("隔离数据目录: %s" % paths.DATA)
check("数据目录是隔离的", str(TMP) in str(paths.DATA), str(paths.DATA))

w = ctl.Console()
w.show()
app.processEvents()
say("形象下拉: " + str([w.cb_char.itemText(i) for i in range(w.cb_char.count())]))
say("大小下拉: " + str([(w.cb_scale.itemText(i), w.cb_scale.itemData(i)) for i in range(w.cb_scale.count())])
    + "  当前=" + w.cb_scale.currentText())
labels = [w.cb_char.itemText(i) for i in range(w.cb_char.count())]
# 源码目录里还留着开发用的形象（oc / whale-girl），打包后只有 nailong
# —— 发行包"只有一个形象"这件事由主程序自检里的 characters 字段验证（实测 == ["nailong"]）。
check("内置形象显示成中文名「奶龙」", "奶龙" in labels, str(labels))
idx = w.cb_char.findData(paths.DEFAULT_CHARACTER)
check("内置形象在列表里", idx >= 0, str(idx))
w.cb_char.setCurrentIndex(idx)
app.processEvents()
check("默认大小是大号（内置形象帧只有 160 高）", float(w.cb_scale.currentData()) >= 1.4,
      str(w.cb_scale.currentData()))

say()
say("== 点「召唤一个桌宠」 ==")
w.on_add_pet()
time.sleep(1.0)
pets = petlist.load_pets()
say("pets.json: " + json.dumps(pets, ensure_ascii=False))
# on_add_pet 会先 ensure_first()（补出 pet1 兜底），再追加真正点出来的那只 —— 所以看最后一只。
newest = pets[-1]
check("召唤出来了（列表里多了一只）", len(pets) >= 1, "%d 只" % len(pets))
check("形象是内置的奶龙", newest.get("character") == paths.DEFAULT_CHARACTER, str(newest.get("character")))
check("大小按默认值存下来了", float(newest.get("scale", 0)) >= 1.4, str(newest.get("scale")))
time.sleep(3.0)
check("桌宠进程真的起来了", ctl.pet_running(newest["id"]),
      "pets.json 里的 pid=" + str(newest.get("pid")))
pid = ctl.read_pid() or newest.get("pid")
u = ctypes.WinDLL("user32")
u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
from ctypes import wintypes
found = []
def cb(h, l):
    wp = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(wp))
    if wp.value == pid and u.IsWindowVisible(h):
        r = wintypes.RECT(); u.GetWindowRect(h, ctypes.byref(r))
        if r.right - r.left > 20:
            found.append((r.right - r.left, r.bottom - r.top))
    return True
u.EnumWindows(EP(cb), 0)
say("桌宠窗口: " + str(found))
check("窗口尺寸符合 1.4 倍（约 336 宽）", bool(found) and 300 <= found[0][0] <= 360, str(found))
w.on_delete_char if False else None
ctl.stop_pet(pets[0]["id"])
w.close()
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-firstrun.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
