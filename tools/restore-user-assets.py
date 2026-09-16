# -*- coding: utf-8 -*-
"""把开发机上保存的形象素材还原回数据目录（之前测试把 %APPDATA%\\DeskPet\\assets 清空过）。"""
import os, shutil, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"D:/dsh/deskpet")
DATA = Path(os.environ["APPDATA"]) / "DeskPet"
pairs = [(BASE / "assets" / "user" / "xiaoduan-doubao", DATA / "assets" / "user" / "xiaoduan-doubao")]
for src, dst in pairs:
    if not src.exists():
        print("跳过（源不存在）:", src); continue
    if dst.exists():
        print("已存在，不动:", dst); continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    print("已还原: %s -> %s (%d 个文件)" % (src.name, dst, len(list(dst.glob('*')))))
for root, dirs, files in os.walk(DATA / "assets"):
    if "_frames.json" in files:
        print("  数据目录里的形象:", Path(root).relative_to(DATA).as_posix())
