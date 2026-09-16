# -*- coding: utf-8 -*-
"""把主人自己那只形象的名字补回数据目录（数据目录被清过，names.json 只剩测试条目）。"""
import io, json, os, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(os.environ["APPDATA"]) / "DeskPet" / "assets" / "user" / "names.json"
d = {}
if DATA.exists():
    try:
        d = json.loads(DATA.read_text(encoding="utf-8"))
    except Exception:
        d = {}
before = dict(d)
d.setdefault("user/xiaoduan-doubao", "谢小端（豆包图）")
if d != before:
    DATA.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
print("names.json 现在:", json.dumps(d, ensure_ascii=False))
