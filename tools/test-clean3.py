"""test-clean3.py —— 第三版夹缝清理：漏白降幅 vs 细节损失"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker
from rembg import new_session, remove

lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

sess = new_session("isnet-anime")
S = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图1.jpg")
D = Path(r"D:/dsh/图片/透明底豆包处理谢小端.jpeg")

def metrics(orig, cut):
    o = np.asarray(orig.convert("RGB")).astype(np.float32)
    a = np.asarray(cut.convert("RGBA"))[..., 3]
    border = np.concatenate([o[:3].reshape(-1,3), o[-3:].reshape(-1,3),
                             o[:, :3].reshape(-1,3), o[:, -3:].reshape(-1,3)])
    bg = np.median(border, axis=0)
    d = np.sqrt(((o - bg) ** 2).sum(axis=2))
    solid = a > 128
    leak = int(((d < 28) & solid).sum())
    det = petmaker._detail_map(o)
    det_in = det & solid
    return leak, int(solid.sum()), int(det_in.sum())

for tag, path in (("三视图", S), ("豆包图", D)):
    say("=" * 96)
    say("【%s】" % tag)
    say("=" * 96)
    src = Image.open(path).convert("RGBA")
    k = 1600 / max(src.size) if max(src.size) > 1600 else 1.0
    work = src.resize((max(1,int(src.width*k)), max(1,int(src.height*k))), Image.LANCZOS) if k!=1.0 else src
    raw = remove(work, session=sess, post_process_mask=True)
    l0, s0, dt0 = metrics(work, raw)
    say("  纯 AI（基准）      : 漏白=%-7d 不透明=%-7d 角色内细节像素=%-6d" % (l0, s0, dt0))
    for lvl in ("low", "normal", "strong"):
        c = petmaker.clean_inner_background(raw, work,
                 max_area_ratio=petmaker.GAP_LEVELS[lvl])
        l1, s1, dt1 = metrics(work, c)
        say("  + 清理(%-6s)      : 漏白=%-7d (降 %5.1f%%)  不透明=%-7d (减 %4.1f%%)  细节像素=%-6d (减 %4.1f%%)" % (
            lvl, l1, 100.0*(l0-l1)/max(1,l0), s1, 100.0*(s0-s1)/max(1,s0),
            dt1, 100.0*(dt0-dt1)/max(1,dt0)))
    say()
    work.save(Path(r"D:/dsh/deskpet/selftest") / ("c3-orig-%s.png" % tag))
    petmaker.clean_inner_background(raw, work, max_area_ratio=0.04).save(
        Path(r"D:/dsh/deskpet/selftest") / ("c3-normal-%s.png" % tag))

Path(r"D:/dsh/deskpet/selftest/report-clean3.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")