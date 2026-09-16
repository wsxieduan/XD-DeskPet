"""test-matting.py —— 正经方案：alpha matting（软抠图），专治发丝/细缝"""
import sys, time
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

def metrics(orig, cut):
    o = np.asarray(orig.convert("RGB")).astype(np.float32)
    a = np.asarray(cut.convert("RGBA"))[..., 3]
    border = np.concatenate([o[:3].reshape(-1,3), o[-3:].reshape(-1,3),
                             o[:, :3].reshape(-1,3), o[:, -3:].reshape(-1,3)])
    bg = np.median(border, axis=0)
    d = np.sqrt(((o - bg) ** 2).sum(axis=2))
    solid = a > 128
    return int(((d < 28) & solid).sum()), int(solid.sum()), int((petmaker._detail_map(o) & solid).sum())

src = Image.open(S).convert("RGBA")
k = 1200 / max(src.size)
work = src.resize((max(1,int(src.width*k)), max(1,int(src.height*k))), Image.LANCZOS)
say("测试尺寸: %s（原图 %s）" % (str(work.size), str(src.size)))
say()

def run(tag, **kw):
    t0 = time.time()
    out = remove(work, session=sess, post_process_mask=kw.pop("ppm", True), **kw)
    dt = time.time() - t0
    l, s, det = metrics(work, out)
    say("  %-34s 漏白=%-7d 不透明=%-7d 细节=%-7d  (%.1fs)" % (tag, l, s, det, dt))
    return out, l, s, det

say("基准与对比：")
base, l0, s0, d0 = run("默认（硬 mask）")
base.save(Path(r"D:/dsh/deskpet/selftest") / "matting-base.png")

for fg, bg, er in ((240, 10, 10), (240, 15, 15), (250, 5, 5)):
    try:
        out, l1, s1, d1 = run("alpha_matting fg=%d bg=%d erode=%d" % (fg, bg, er),
                              alpha_matting=True,
                              alpha_matting_foreground_threshold=fg,
                              alpha_matting_background_threshold=bg,
                              alpha_matting_erode_size=er)
        say("      相对硬 mask: 漏白降 %.1f%%  不透明减 %.1f%%  细节减 %.1f%%" % (
            100.0*(l0-l1)/max(1,l0), 100.0*(s0-s1)/max(1,s0), 100.0*(d0-d1)/max(1,d0)))
        out.save(Path(r"D:/dsh/deskpet/selftest") / ("matting-fg%d.png" % fg))
    except Exception as e:
        say("      失败: " + str(e)[:200])

Path(r"D:/dsh/deskpet/selftest/report-matting.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")