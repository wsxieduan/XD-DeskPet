# -*- coding: utf-8 -*-
import os, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
D = Path(os.path.expanduser("~")) / "Desktop"
print("=== 桌面上的桌宠相关 ===")
for p in sorted(D.iterdir()):
    if "deskpet" in p.name.lower() or "桌宠" in p.name:
        print("   %-28s %s" % (p.name, ("%.0f MB" % (p.stat().st_size / 1048576)) if p.is_file() else "<文件夹>"))
print()
print("=== D 盘上的版本 ===")
base = Path(r"D:/dsh/deskpet")
for p in sorted(base.glob("*.zip")) + sorted((base / "dist-kit").glob("*.zip")):
    print("   %-40s %.0f MB" % (p.relative_to(base).as_posix(), p.stat().st_size / 1048576))
for p in (base / "dist").iterdir():
    print("   dist/%-35s %s" % (p.name, "最新构建"))
