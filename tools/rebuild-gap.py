"""rebuild-gap.py —— 用夹缝清理重建，并生成"清理前 vs 清理后"对比图"""
import json, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import petmaker

BASE = Path(r"D:/dsh/deskpet")
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

# 先备份当前素材，万一清理过头可以立刻还原
bak = BASE / "assets" / "oc-backup"
if not bak.exists():
    shutil.copytree(BASE / "assets" / "oc", bak)
    say("已备份原素材到 assets/oc-backup")

def checker(size, cell=10):
    q = Image.new("RGB", size, (238,238,238)); d = ImageDraw.Draw(q)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x//cell)+(y//cell)) % 2:
                d.rectangle([x, y, x+cell-1, y+cell-1], fill=(200,200,200))
    return q

SHEET = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图1.jpg")
DOUBAO = Path(r"D:/dsh/图片/透明底豆包处理谢小端.jpeg")

panels = []
for tag, path in (("shet", SHEET), ("doubao", DOUBAO)):
    raw = petmaker.cutout_ai(path, max_side=1600, gap_level="off")
    cleaned = petmaker.cutout_ai(path, max_side=1600, gap_level="normal")
    v_raw = petmaker.split_views(raw.image, 3)[0]
    v_cln = petmaker.split_views(cleaned.image, 3)[0]
    a0 = int((np.asarray(v_raw)[..., 3] > 128).sum())
    a1 = int((np.asarray(v_cln)[..., 3] > 128).sum())
    say("%-8s 清理前不透明=%-8d 清理后=%-8d 减少 %.1f%%（%s）" % (
        tag, a0, a1, 100.0*(a0-a1)/max(1,a0), "夹缝被清掉的部分"))
    v_raw.save(BASE / "selftest" / ("gapfix-%s-before.png" % tag))
    v_cln.save(BASE / "selftest" / ("gapfix-%s-after.png" % tag))
    panels.append((tag, v_raw, v_cln))

    if tag == "shet":
        # 用清理后的结果重建三个视图
        views = petmaker.split_views(cleaned.image, 3)
        for i, v in enumerate(views, 1):
            v.save(BASE / "assets" / "oc-src" / ("view%d.png" % i))
            tracks = petmaker.make_frames(v, "full")
            final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
            d = BASE / "assets" / "oc" / ("view%d" % i)
            d.mkdir(parents=True, exist_ok=True)
            for old in d.glob("*.png"):
                old.unlink()
            manifest = {}
            for tr, frames in final.items():
                nm = []
                for j, f in enumerate(frames, 1):
                    fn = "%s-%d.png" % (tr, j)
                    f.save(d / fn)
                    nm.append(fn)
                manifest[tr] = nm
            (d / "_frames.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

# 拼对比图
H = 560
def thumb(im):
    t = im.copy(); t.thumbnail((int(im.width*H/im.height), H), Image.LANCZOS); return t
rows = []
for tag, a, b in panels:
    rows.append((thumb(a), thumb(b)))
W = sum(r[0].width + r[1].width for r in rows) + 40*5
canvas = Image.new("RGB", (W, H + 110), (18, 24, 40))
d = ImageDraw.Draw(canvas)
d.text((40, 20), "LEFT of each pair = AI only (gaps stay white)   RIGHT = AI + gap cleanup", fill=(170,190,240))
d.text((40, 44), "check hair strands / neck gaps / and whether any light-colored part of the character got eaten", fill=(120,140,190))
x = 40
for a, b in rows:
    for im in (a, b):
        bg = checker(im.size); bg.paste(im, (0,0), im)
        canvas.paste(bg, (x, 80)); x += im.width + 40
    x += 40
canvas.save(BASE / "selftest" / "gap-before-after.png")
say()
say("对比图: selftest/gap-before-after.png")
Path(BASE / "selftest" / "report-gapfix2.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
