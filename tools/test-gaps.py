"""test-gaps.py —— 在裁剪前的同一坐标系里量化"该透明却没透明"的像素"""
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

def leak(orig_rgb, cut_rgba, tol=28):
    o = np.asarray(orig_rgb.convert("RGB")).astype(np.float32)
    a = np.asarray(cut_rgba.convert("RGBA"))[..., 3]
    border = np.concatenate([o[:3].reshape(-1,3), o[-3:].reshape(-1,3),
                             o[:, :3].reshape(-1,3), o[:, -3:].reshape(-1,3)])
    bg = np.median(border, axis=0)
    d = np.sqrt(((o - bg) ** 2).sum(axis=2))
    solid = a > 128
    bad = (d < tol) & solid
    n = int(bad.sum())
    biggest, where = 0, None
    if n:
        lbl, k = ndimage.label(bad, structure=np.ones((3,3), dtype=int))
        if k:
            sizes = ndimage.sum(bad, lbl, index=np.arange(1, k+1))
            i = int(np.argmax(sizes)) + 1
            ys, xs = np.where(lbl == i)
            biggest, where = int(sizes[i-1]), (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    return n, 100.0 * n / max(1, int(solid.sum())), biggest, where

sess = new_session("isnet-anime")
S = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图1.jpg")
D = Path(r"D:/dsh/图片/透明底豆包处理谢小端.jpeg")

for tag, path in (("三视图", S), ("豆包图", D)):
    say("=" * 90)
    say("【%s】%s" % (tag, path.name))
    say("=" * 90)
    src = Image.open(path).convert("RGBA")
    k = 1600 / max(src.size) if max(src.size) > 1600 else 1.0
    work = src.resize((max(1,int(src.width*k)), max(1,int(src.height*k))), Image.LANCZOS) if k != 1.0 else src
    raw = remove(work, session=sess, post_process_mask=True)

    n0, p0, b0, w0 = leak(work, raw)
    say("  纯 AI 原始输出      : 漏白=%-7d (占角色 %.1f%%)  最大一块=%-7d %s" % (n0, p0, b0, w0))

    cleaned = petmaker.clean_inner_background(raw, work)
    n1, p1, b1, w1 = leak(work, cleaned)
    say("  + 内部夹缝清理      : 漏白=%-7d (占角色 %.1f%%)  最大一块=%-7d %s" % (n1, p1, b1, w1))
    say("  -> 减少 %.1f%%" % (100.0*(n0-n1)/max(1,n0)))

    # 完整流程（含 defringe / 反预乘 / 白边清理）对比
    full = petmaker.cutout_ai(path, max_side=1600, clean_gaps=False)
    say("  （完整流程但不清夹缝后的裁剪尺寸 %s）" % str(full.image.size))
    say()
    work.save(Path(r"D:/dsh/deskpet/selftest") / ("gap-orig-%s.png" % tag))
    cleaned.save(Path(r"D:/dsh/deskpet/selftest") / ("gap-clean-%s.png" % tag))
    raw.save(Path(r"D:/dsh/deskpet/selftest") / ("gap-raw-%s.png" % tag))

Path(r"D:/dsh/deskpet/selftest/report-gaps.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
