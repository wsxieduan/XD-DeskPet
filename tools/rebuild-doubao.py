import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker
BASE = Path(r"D:/dsh/deskpet")
D = Path(r"D:/dsh/图片/透明底豆包处理谢小端.jpeg")
res = petmaker.cutout_ai(D, max_side=1600, gap_level="normal")
v = petmaker.split_views(res.image, 3)[0]
tracks = petmaker.make_frames(v, "full")
final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
manifest = petmaker.install(BASE / "assets", "xiaoduan-doubao", final)
names = json.loads((BASE / "assets" / "user" / "names.json").read_text(encoding="utf-8"))
names["user/xiaoduan-doubao"] = "谢小端（豆包图）"
(BASE / "assets" / "user" / "names.json").write_text(json.dumps(names, indent=2, ensure_ascii=False), encoding="utf-8")
print("豆包形象已用夹缝清理重建: 立绘 %s 画布 %s 帧数 %s" % (
    v.size, final["idle"][0].size, {k: len(x) for k, x in manifest.items()}))
