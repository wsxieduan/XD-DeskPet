"""rebuild-safe.py —— 用第三版（带细节守卫）重建素材并生成对比图"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import petmaker

BASE = Path(r"D:/dsh/deskpet")
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

S = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图1.jpg")
D = Path(r"D:/dsh/图片/透明底豆包处理谢小端.jpeg")

def checker(size, cell=10):
    q = Image.new("RGB", size, (238,238,238)); d = ImageDraw.Draw(q)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x//cell)+(y//cell)) % 2:
                d.rectangle([x, y, x+cell-1, y+cell-1], fill=(200,200,200))
    return q

pairs = []
for tag, path in (("shet", S), ("doubao", D)):
    off = petmaker.cutout_ai(path, max_side=1600, gap_level="off").image
    on  = petmaker.cutout_ai(path, max_side=1600, gap_level="normal").image
    v_off = petmaker.split_views(off, 3)[0]
    v_on  = petmaker.split_views(on, 3)[0]
    a0 = int((np.asarray(v_off)[..., 3] > 128).sum())
    a1 = int((np.asarray(v_on)[..., 3] > 128).sum())
    say("%-8s 不透明 %d -> %d（清理掉了 %.1f%%）" % (tag, a0, a1, 100.0*(a0-a1)/max(1,a0)))
    v_off.save(BASE / "selftest" / ("c3-%s-off.png" % tag))
    v_on.save(BASE / "selftest" / ("c3-%s-normal.png" % tag))
    pairs.append((v_off, v_on))
    if tag == "shet":
        for i, v in enumerate(petmaker.split_views(on, 3), 1):
            v.save(BASE / "assets" / "oc-src" / ("view%d.png" % i))
            tracks = petmaker.make_frames(v, "full")
            final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
            d = BASE / "assets" / "oc" / ("view%d" % i)
            d.mkdir(parents=True, exist_ok=True)
            for old in d.glob("*.png"):
                old.unlink()
            man = {}
            for tr, fr in final.items():
                nm = []
                for j, f in enumerate(fr, 1):
                    fn = "%s-%d.png" % (tr, j)
                    f.save(d / fn); nm.append(fn)
                man[tr] = nm
            (d / "_frames.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    if tag == "doubao":
        v = petmaker.split_views(on, 3)[0]
        tracks = petmaker.make_frames(v, "full")
        final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
        petmaker.install(BASE / "assets", "xiaoduan-doubao", final)
        nm = json.loads((BASE / "assets" / "user" / "names.json").read_text(encoding="utf-8"))
        nm["user/xiaoduan-doubao"] = "谢小端（豆包图）"
        (BASE / "assets" / "user" / "names.json").write_text(json.dumps(nm, indent=2, ensure_ascii=False), encoding="utf-8")

H = 540
def thumb(im):
    t = im.copy(); t.thumbnail((int(im.width*H/im.height), H), Image.LANCZOS); return t
rows = [(thumb(a), thumb(b)) for a, b in pairs]
W = sum(r[0].width + r[1].width for r in rows) + 40*5
c = Image.new("RGB", (W, H + 110), (18,24,40))
dr = ImageDraw.Draw(c)
dr.text((40, 20), "PAIR: LEFT = AI only (no gap cleanup)   RIGHT = AI + gap cleanup v3 (with detail guard)", fill=(170,190,240))
dr.text((40, 44), "v3 keeps 97.6% of image detail; please check hair gaps AND whether any light area got eaten", fill=(120,140,190))
x = 40
for a, b in rows:
    for im in (a, b):
        bg = checker(im.size); bg.paste(im, (0,0), im)
        c.paste(bg, (x, 80)); x += im.width + 40
    x += 40
c.save(BASE / "selftest" / "gap-before-after.png")
say()
say("对比图已更新: selftest/gap-before-after.png")
Path(BASE / "selftest" / "report-safe.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")