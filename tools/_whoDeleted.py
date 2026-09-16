# -*- coding: utf-8 -*-
import os, sys, time, glob
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(os.environ["APPDATA"]) / "DeskPet"
print("=== 数据目录现状 ===")
for p in sorted(DATA.rglob("*")):
    if p.is_file():
        print("   %-46s %s" % (p.relative_to(DATA).as_posix(), time.strftime("%H:%M:%S", time.localtime(p.stat().st_mtime))))
print()
print("=== 测试脚本里谁在删东西 ===")
BASE = Path(r"D:/dsh/deskpet/tools")
for f in sorted(BASE.glob("test-*.py")) + sorted(BASE.glob("verify-*.py")) + [BASE / "run-regression.py"]:
    s = f.read_text(encoding="utf-8", errors="replace")
    hits = [l.strip()[:100] for l in s.splitlines() if ("rmtree" in l or "unlink" in l or "APPDATA" in l)]
    if hits:
        print("---", f.name)
        for h in hits[:6]:
            print("     ", h)
