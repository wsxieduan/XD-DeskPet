"""rebuild-all.py —— 用 AI 抠图重建所有素材（失败自动退回算法）"""
import json, sys, time
from pathlib import Path
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import petmaker

BASE = Path(r"D:/dsh/deskpet")
IMG = Path(r"D:/dsh/图片")
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

use_ai = "--algo" not in sys.argv
ok_ai, why = petmaker.ai_status()
say("AI 状态: %s (%s)" % (ok_ai, why))
say("本次方式: %s" % ("AI 智能抠图" if (use_ai and ok_ai) else "快速算法"))

def do_cut(path):
    if use_ai and ok_ai:
        return petmaker.cutout_ai(path)
    return petmaker.cutout(path, "normal")

def install(pet_id, name, img, mode="full"):
    tracks = petmaker.make_frames(img, mode)
    final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
    petmaker.install(BASE / "assets", pet_id, final)
    names = {}
    nf = BASE / "assets" / "user" / "names.json"
    try:
        names = json.loads(nf.read_text(encoding="utf-8"))
    except Exception:
        pass
    names["user/" + pet_id] = name
    nf.parent.mkdir(parents=True, exist_ok=True)
    nf.write_text(json.dumps(names, indent=2, ensure_ascii=False), encoding="utf-8")
    return final

say()
say("=== 1. 谢小端三视图 -> oc/view1..3 ===")
S = IMG / "双色发双马尾少女设定-角色-谢小端-三视图1.jpg"
t0 = time.time()
res = do_cut(S)
views = petmaker.split_views(res.image, 3)
say("   抠图 %.1fs，切出 %d 个视图，诊断=%s" % (time.time() - t0, len(views), res.info))
for i, v in enumerate(views, 1):
    v.save(BASE / "assets" / "oc-src" / ("view%d.png" % i))
    final = install("__tmp", "x", v) if False else None
    tracks = petmaker.make_frames(v, "full")
    final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
    d = BASE / "assets" / "oc" / ("view%d" % i)
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*.png"):
        old.unlink()
    manifest = {}
    for track, frames in final.items():
        nm = []
        for j, f in enumerate(frames, 1):
            fn = "%s-%d.png" % (track, j)
            f.save(d / fn)
            nm.append(fn)
        manifest[track] = nm
    (d / "_frames.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    s, b = petmaker.halo_score(v, want_band=True)
    say("   view%d 立绘 %-12s 白边=%.3f(带%d) 画布 %s" % (
        i, str(v.size), s, b, str(final["idle"][0].size)))

say()
say("=== 2. 豆包那张 -> user/xiaoduan-doubao ===")
D = IMG / "透明底豆包处理谢小端.jpeg"
t0 = time.time()
res2 = do_cut(D)
vs = petmaker.split_views(res2.image, 3)
say("   抠图 %.1fs，切出 %d 个视图" % (time.time() - t0, len(vs)))
if vs:
    v = vs[0]
    s, b = petmaker.halo_score(v, want_band=True)
    say("   用第 1 个：%s 白边=%.3f(带%d)" % (str(v.size), s, b))
    final = install("xiaoduan-doubao", "谢小端（豆包图）", v, "full")
    say("   画布 %s 帧数 %s" % (str(final["idle"][0].size), {k: len(x) for k, x in final.items()}))

say()
say("=== 3. 现在的形象列表 ===")
for mf in sorted((BASE / "assets").glob("**/_frames.json")):
    say("   " + mf.parent.relative_to(BASE / "assets").as_posix())

Path(BASE / "selftest" / "report-rebuild-all.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
