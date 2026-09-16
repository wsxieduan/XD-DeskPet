import importlib.util, json, sys
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import paths
from PySide6.QtWidgets import QApplication
app = QApplication([])
spec = importlib.util.spec_from_file_location("deskpet", BASE / "deskpet.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
cfg_path = paths.config_path()
orig = cfg_path.read_text(encoding="utf-8")
cfg = json.loads(orig)
lines = []
try:
    for ch in ("oc/view1", "oc/view2", "oc/view3", "user/xiaoduan-doubao", "whale-girl"):
        if not (BASE / "assets" / ch / "_frames.json").exists():
            continue
        cfg["character"] = ch
        cfg.pop("bubble", None)
        cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        p = mod.DeskPet()
        t = p.theme_color
        lines.append("%-24s 主色 #%s  rgb(%3d,%3d,%3d)   ->  气泡 底#%s 字#%s 边#%s" % (
            ch, t.name(), t.red(), t.green(), t.blue(),
            p.bub_bg.name(), p.bub_fg.name(), p.bub_border.name()))
        p.close()
finally:
    cfg_path.write_text(orig, encoding="utf-8")
Path(BASE / "selftest" / "report-theme.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
