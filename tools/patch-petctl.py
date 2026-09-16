from pathlib import Path
TOOLS = Path(r"D:/dsh/deskpet/tools")
changed = []
for p in sorted(TOOLS.glob("*.py")):
    t = p.read_text(encoding="utf-8")
    if "petctl.py" not in t:
        continue
    if "importlib" not in t and "spec_from_file_location" not in t:
        continue
    nt = t.replace(chr(34) + "petctl.py" + chr(34), chr(34) + "petctl.py" + chr(34))
    nt = nt.replace(chr(39) + "petctl.py" + chr(39), chr(39) + "petctl.py" + chr(39))
    if nt != t:
        p.write_text(nt, encoding="utf-8")
        changed.append(p.name)
print("已更新:", changed)