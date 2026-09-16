"""test-uifit.py —— 控制台窗口必须整个在屏幕里，且缩小后能滚到所有控件"""
import json, sys
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

from PySide6.QtWidgets import QApplication, QPushButton, QCheckBox
from PySide6.QtCore import Qt
app = QApplication([])
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)

for f in (ctl.GEOM_FILE,):
    try: f.unlink()
    except Exception: pass

w = ctl.Console()
w.show()
app.processEvents()
scr = app.primaryScreen().availableGeometry()
say("屏幕可用 %dx%d   窗口 %dx%d @ (%d,%d)" % (
    scr.width(), scr.height(), w.width(), w.height(), w.x(), w.y()))
check("窗口完全在屏幕内",
      w.x() >= scr.left() and w.y() >= scr.top()
      and w.x() + w.width() <= scr.right() + 1 and w.y() + w.height() <= scr.bottom() + 1)
check("底部按钮不会被切掉", w.y() + w.height() <= scr.bottom() + 1)

say()
say("== 手动缩到 420 高：应该出现滚动条，且能滚到底 ==")
w.resize(380, 420)
app.processEvents()
sb = w.scroll.verticalScrollBar()
check("出现了垂直滚动条", sb.maximum() > 0, "max=%d" % sb.maximum())
sb.setValue(sb.maximum())
app.processEvents()
inner = w.scroll.widget()
# 滚到底之后，"退出控制台"按钮应该在可视区内
btns = [b for b in inner.findChildren(QPushButton) if "退出控制台" in b.text()]
ok = False
detail = "没找到按钮"
if btns:
    b = btns[0]
    pos = b.mapTo(inner, b.rect().topLeft())
    vis_top = sb.value()
    vis_bottom = sb.value() + w.scroll.viewport().height()
    ok = pos.y() >= vis_top - 2 and pos.y() + b.height() <= vis_bottom + 2
    detail = "按钮 y=%d，可视区 %d~%d" % (pos.y(), vis_top, vis_bottom)
check("滚到底能看到「退出控制台」", ok, detail)

say()
say("== 尺寸是否被记住 ==")
w.resize(400, 500)
w.move(120, 80)
app.processEvents()
w._save_geometry()
geo = json.loads(ctl.GEOM_FILE.read_text(encoding="utf-8"))
check("写进了 ui.json", geo.get("w") == 400 and geo.get("h") == 500, str(geo))
w.close()
w2 = ctl.Console()
check("下次按记住的尺寸打开", w2.width() == 400 and w2.height() == 500,
      "%dx%d" % (w2.width(), w2.height()))
check("位置也被夹在屏幕内",
      w2.x() >= scr.left() and w2.y() >= scr.top(), "(%d,%d)" % (w2.x(), w2.y()))
w2.close()
try: ctl.GEOM_FILE.unlink()
except Exception: pass
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-uifit2.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")