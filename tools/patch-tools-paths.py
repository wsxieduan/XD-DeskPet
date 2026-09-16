import re
from pathlib import Path

TOOLS = Path(r"D:/dsh/deskpet/tools")
NL = chr(10)
changed = []
for p in sorted(TOOLS.glob("*.py")):
    t = p.read_text(encoding="utf-8")
    o = t
    if "config.json" not in t:
        continue
    t = t.replace(chr(39) + "BASE / " + chr(34) + "config.json" + chr(34) + chr(39), "paths.config_path()")
    t = t.replace("BASE / " + chr(34) + "config.json" + chr(34), "paths.config_path()")
    if t == o:
        continue
    if "import paths" not in t:
        for anchor in ("sys.path.insert(0, str(BASE))", "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))"):
            if anchor in t:
                t = t.replace(anchor, anchor + NL + "import paths", 1)
                break
    p.write_text(t, encoding="utf-8")
    changed.append(p.name)
print("已更新:", changed)