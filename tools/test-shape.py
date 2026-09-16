import sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker

lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

S = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图1.jpg")

def shape_report(cut, tag):
    a = np.asarray(cut)[..., 3]
    solid = a > 128
    lbl, n = ndimage.label(solid, structure=np.ones((3,3), dtype=int))
    if n == 0:
        say("   %-10s 空的" % tag); return
    sizes = ndimage.sum(solid, lbl, index=np.arange(1, n+1))
    order = np.argsort(sizes)[::-1]
    top = sizes[order[0]]
    say("   %-10s 不透明=%d  连通块=%d  最大块=%d(占 %.1f%%)  前3块占比=%.1f%%" % (
        tag, int(solid.sum()), n, int(top), 100.0*top/solid.sum(),
        100.0*sizes[order[:3]].sum()/solid.sum()))
    # 洞的数量：清理的本质是把"实心区域里的洞"变多
    holes = ndimage.binary_fill_holes(solid) & ~solid
    lh, nh = ndimage.label(holes, structure=np.ones((3,3), dtype=int))
    say("              内部空洞=%d 个，合计 %d px" % (nh, int(holes.sum())))
    return n, int(solid.sum()), nh

for level in ("off", "low", "normal", "strong"):
    res = petmaker.cutout_ai(S, max_side=1600, gap_level=level)
    v = petmaker.split_views(res.image, 3)[0]
    shape_report(v, "level=" + level)

say()
say("解读：如果 normal/strong 之后连通块数量暴涨、最大块占比大跌，说明她的身体被切碎了（清理过头）；")
say("      如果最大块占比基本不变、只是内部空洞变多，说明清掉的确实是夹缝。")
Path(r"D:/dsh/deskpet/selftest/report-shape.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
