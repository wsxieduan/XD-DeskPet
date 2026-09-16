# -*- coding: utf-8 -*-
"""桌面整理：删掉旧的桌宠测试副本，放上最新的试玩包 zip。"""
import os, shutil, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DESK = Path(os.path.expanduser("~")) / "Desktop"
BASE = Path(r"D:/dsh/deskpet")

OLD = ["DeskPetTest", "FullTest", "LiteTest"]
for name in OLD:
    p = DESK / name
    if p.exists():
        size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1048576
        shutil.rmtree(p, ignore_errors=True)
        print("已删除旧测试副本: %-12s (%.0f MB)" % (name, size))
    else:
        print("本就没有:", name)

src = BASE / "dist-kit" / "DeskPet-精简版-v1.4.zip"
dst = DESK / "DeskPet-精简版-v1.4.zip"
if src.exists():
    if dst.exists():
        dst.unlink()
    shutil.copy2(src, dst)
    print("桌面已放上最新试玩包: %s (%.0f MB)" % (dst.name, dst.stat().st_size / 1048576))

print()
print("现在桌面上的桌宠相关项:")
for p in sorted(DESK.iterdir()):
    if "deskpet" in p.name.lower() or "桌宠" in p.name:
        print("   %-30s %s" % (p.name, "%.0f MB" % (p.stat().st_size / 1048576) if p.is_file() else "<文件夹>"))
