# -*- coding: utf-8 -*-
"""快速探针：连续 _zoom_to 之后 _fast 为什么变回 False。"""
import ctypes, json, os, shutil, subprocess, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
TMP = BASE / "selftest" / "appdata-probe"
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
(TMP / "DeskPet" / "config.json").write_text(json.dumps(
    {"character": "nailong", "x": 600, "y": 300, "scale": 1.0, "sound": False}), encoding="utf-8")
os.environ["APPDATA"] = str(TMP)
ctypes.windll.shcore.SetProcessDpiAwareness(2)
from PySide6.QtWidgets import QApplication
app = QApplication([])
import deskpet

pet = deskpet.DeskPet(None)
pet.show()
app.processEvents()
print("初始 _fast =", pet._fast, " scale =", pet.scale)
orig = pet._zoom_settle
calls = []

def traced():
    calls.append("settle")
    orig()

pet._zoom_settle = traced
pet._zoom_timer.timeout.disconnect()
pet._zoom_timer.timeout.connect(traced)
for i in range(5):
    r = pet._zoom_to(1.0 + i * 0.02)
    print("  i=%d 返回值=%s scale=%.3f _fast=%s timer_active=%s settle次数=%d"
          % (i, r, pet.scale, pet._fast, pet._zoom_timer.isActive(), len(calls)))
    app.processEvents()
    print("     processEvents 之后: _fast=%s settle次数=%d" % (pet._fast, len(calls)))
pet.close()
