# -*- coding: utf-8 -*-
"""定位 test-sounds 第 3 节为什么静默退出。"""
import os, shutil, subprocess, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
TMP = BASE / "selftest" / "appdata-sounds-dbg"
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
os.environ["APPDATA"] = str(TMP)
sys.stdout.reconfigure(encoding="utf-8")
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
from PySide6.QtWidgets import QApplication
app = QApplication([])
print("1 导入 OK", flush=True)
w = ctl.Console()
print("2 Console 建好了", flush=True)
app.processEvents()
print("3 processEvents OK, sfx_status=%s" % {k: v.text() for k, v in w.sfx_status.items()}, flush=True)
w.on_preview_sound("click")
print("4 试听 OK", flush=True)
w.on_clear_sound("click")
print("5 清空 OK", flush=True)
w.on_add_sound("click")
print("6 添加（没选文件）OK", flush=True)
class Fake:
    FILES = []
    @staticmethod
    def getOpenFileNames(*a, **k):
        return list(Fake.FILES), ""


class FakeMsg:
    @staticmethod
    def information(*a, **k):
        print("     [假提示]", str(a[2])[:60].replace(chr(10), " "), flush=True)

    @staticmethod
    def warning(*a, **k):
        print("     [假警告]", str(a[2])[:60], flush=True)


ctl.QFileDialog = Fake
ctl.QMessageBox = FakeMsg
print("ctl.CONFIG =", getattr(ctl, "CONFIG", "没有这个属性"), flush=True)
import json, wave
from pathlib import Path
userdir = TMP / "u"
userdir.mkdir(exist_ok=True)
good = userdir / "x.wav"
with wave.open(str(good), "wb") as f:
    f.setnchannels(1); f.setsampwidth(2); f.setframerate(22050)
    f.writeframes(b"\x00\x00" * 2205)
bad = userdir / "x.mp3"
bad.write_bytes(b"ID3")
Fake.FILES = [str(good), str(bad)]
print("6.5 直接调 on_add_sound（真文件）", flush=True)
try:
    w.on_add_sound("click")
except Exception as e:
    import traceback
    traceback.print_exc()
    print("   on_add_sound 抛异常:", e, flush=True)
print("7 on_add_sound 返回", flush=True)
w.on_add_sound("click")
print("8 空选择 OK", flush=True)
w.close()
print("8 关闭 OK", flush=True)
