# -*- coding: utf-8 -*-
"""把主人的配置还原成"他自己的那只"。

为什么需要：跑回归测试时（测试用的是真实 %APPDATA%），测试进程在脚本还原之后又写了一次
pets.json，把 pet1 的形象改成了 nailong 并多出一条 pet2。已经给 run-regression.py 加了
"先杀进程再还原 + 还原后校验"，这份是把被改坏的数据改回去。
"""
import io, json, os, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
DATA = Path(os.environ["APPDATA"]) / "DeskPet"

pets = [{
    "id": "pet1",
    "character": "user/xiaoduan-doubao",     # 主人自己上传的那只（素材已还原到数据目录）
    "x": 299, "y": 328,
    "scale": 1.4,
    "pid": None,                              # 旧 pid 早就不在了，留着只会显示"未启动"
}]
(DATA / "pets.json").write_text(json.dumps(pets, indent=2, ensure_ascii=False), encoding="utf-8")
print("pets.json 已还原:", json.dumps(pets, ensure_ascii=False))

try:
    cfg = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
except Exception:
    cfg = {}
cfg["character"] = "nailong"       # oc/view1 已经不随包分发了；内置形象是奶龙
cfg["mode"] = "desktop"            # 只贴壁纸层（主人最初的要求；topmost 是之前测试留下的）
cfg.setdefault("sound", True)
cfg.setdefault("behavior", {"roam": True, "flee": True, "inertia": True, "recycle": True})
(DATA / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
print("config.json: 形象=%s 层级=%s 大小=%s" % (cfg["character"], cfg["mode"], cfg.get("scale")))
print("素材检查:", [p.parent.relative_to(DATA).as_posix() for p in (DATA / "assets").rglob("_frames.json")])
