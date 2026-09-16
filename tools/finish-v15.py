# -*- coding: utf-8 -*-
"""v1.5 收尾：桌面换成新试玩包、启动最新版、把主人的数据保持原样。"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"D:/dsh/deskpet")
DESK = Path(os.path.expanduser("~")) / "Desktop"
DATA = Path(os.environ["APPDATA"]) / "DeskPet"

# 1) 桌面：删掉旧 v1.4 zip，放上 v1.5
for p in DESK.glob("DeskPet-*v1.*.zip"):
    p.unlink()
    print("删掉旧包:", p.name)
# 取 dist-kit 里最新的那个精简版包（版本号会变，别写死）
cands = sorted((BASE / "dist-kit").glob("DeskPet-精简版-*.zip"),
               key=lambda q: q.stat().st_mtime)
src = cands[-1]
dst = DESK / src.name
shutil.copy2(src, dst)
print("桌面新包:", dst.name, "%.0f MB" % (dst.stat().st_size / 1048576))

# 2) 主人数据体检（只读，不改）
pets = json.loads((DATA / "pets.json").read_text(encoding="utf-8"))
cfg = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
print("pets.json:", json.dumps(pets, ensure_ascii=False))
print("config: character=%s mode=%s scale=%s" % (cfg.get("character"), cfg.get("mode"), cfg.get("scale")))
print("数据目录里的形象:", [p.parent.relative_to(DATA).as_posix() for p in (DATA / "assets").rglob("_frames.json")])
print()
print("桌面上的桌宠相关:")
for p in sorted(DESK.iterdir()):
    if "deskpet" in p.name.lower() or "桌宠" in p.name:
        print("   %-30s %s" % (p.name, ("%.0f MB" % (p.stat().st_size / 1048576)) if p.is_file() else "<文件夹>"))
