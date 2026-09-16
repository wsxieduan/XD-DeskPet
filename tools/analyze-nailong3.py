import sys
from pathlib import Path
from collections import Counter
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker
lines = []
P = Path(r"D:/dsh/图片/奶龙.gif")
seq, ms = petmaker.load_sequence(P)

lines.append("=== 每帧的主色（看背景是不是稳定的）===")
for i in (0, 30, 60, 90, 120):
    if i >= len(seq): break
    a = np.asarray(seq[i])[..., :3].reshape(-1, 3)
    q = (a // 16 * 16)
    c = Counter(map(tuple, q))
    top = c.most_common(3)
    lines.append("  帧%-4d 主色: %s" % (i, ", ".join("%s %.0f%%" % (str(k), 100*v/len(q)) for k, v in top)))

lines.append("")
lines.append("=== AI 抠图试第一帧 ===")
f0 = Path(r"D:/dsh/deskpet/selftest/nailong-f0.png")
seq[0].save(f0)
try:
    r = petmaker.cutout_ai(f0, max_side=320)
    a = np.asarray(r.image)[..., 3]
    h, w = a.shape
    corners = [a[2, 2], a[2, w-3], a[h-3, 2], a[h-3, w-3]]
    lines.append("  尺寸 %s  不透明占比 %.3f" % (str(r.image.size), float((a > 128).mean())))
    lines.append("  四角 alpha: %s  （都接近 0 = 背景被去掉了）" % str([int(x) for x in corners]))
    r.image.save(r"D:/dsh/deskpet/selftest/nailong-cut.png")
except Exception as e:
    lines.append("  AI 失败: " + str(e)[:120])

lines.append("")
lines.append("=== 快速算法抠图试第一帧 ===")
try:
    r2 = petmaker.cutout(f0, "normal", max_side=320)
    a2 = np.asarray(r2.image)[..., 3]
    lines.append("  尺寸 %s  不透明占比 %.3f  诊断 %s" % (
        str(r2.image.size), float((a2 > 128).mean()), str(r2.info)))
except Exception as e:
    lines.append("  算法失败: " + str(e)[:120])
Path(r"D:/dsh/deskpet/selftest/report-nailong3.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")