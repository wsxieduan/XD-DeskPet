import sys
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
from PySide6.QtWidgets import QApplication
app = QApplication([])
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
w = ctl.Console()
scr = app.primaryScreen().availableGeometry()
hint = w.sizeHint()
lines = []
lines.append("屏幕可用区: %d x %d" % (scr.width(), scr.height()))
lines.append("控制台 sizeHint: %d x %d" % (hint.width(), hint.height()))
lines.append("控制台实际尺寸: %d x %d" % (w.width(), w.height()))
lines.append("超出屏幕高度: %d px" % max(0, hint.height() - scr.height()))
lines.append("")
lines.append("各区块高度:")
lay = w.layout()
for i in range(lay.count()):
    it = lay.itemAt(i)
    ww = it.widget()
    if ww is not None:
        lines.append("   %-22s %d" % (type(ww).__name__, ww.sizeHint().height()))
    elif it.layout() is not None:
        lines.append("   %-22s %d" % ("layout", it.layout().sizeHint().height()))
w.close()
Path(BASE / "selftest" / "report-uifit.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")