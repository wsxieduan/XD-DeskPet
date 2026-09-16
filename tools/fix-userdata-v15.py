# -*- coding: utf-8 -*-
"""数据修复 + 启动最新版。"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"D:/dsh/deskpet")
DATA = Path(os.environ["APPDATA"]) / "DeskPet"
TARGET = DATA / "assets" / "user" / "xiaoduan-doubao"
SRC = BASE / "assets" / "user" / "xiaoduan-doubao"

if not TARGET.exists():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC, TARGET)
    print("形象素材已还原:", TARGET)
names_path = DATA / "assets" / "user" / "names.json"
names = {}
if names_path.exists():
    try:
        names = json.loads(names_path.read_text(encoding="utf-8"))
    except Exception:
        names = {}
names.setdefault("user/xiaoduan-doubao", "谢小端（豆包图）")
names_path.parent.mkdir(parents=True, exist_ok=True)
names_path.write_text(json.dumps(names, indent=2, ensure_ascii=False), encoding="utf-8")

pets = [{"id": "pet1", "character": "user/xiaoduan-doubao", "x": 299, "y": 328,
         "scale": 1.4, "pid": None}]
(DATA / "pets.json").write_text(json.dumps(pets, indent=2, ensure_ascii=False), encoding="utf-8")
cfg = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
cfg["character"] = "nailong"
cfg["mode"] = "desktop"
(DATA / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
print("pets.json:", json.dumps(pets, ensure_ascii=False))
print("names.json:", json.dumps(names, ensure_ascii=False))
print("数据目录里的形象:", [p.parent.relative_to(DATA).as_posix() for p in (DATA / "assets").rglob("_frames.json")])
