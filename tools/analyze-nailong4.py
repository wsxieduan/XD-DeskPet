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
n = len(seq)

lines.append("=== 四角像素跨全部 %d 帧的变化 ===" % n)
cc = Counter()
samples = []
for i, f in enumerate(seq):
    a = np.asarray(f)[..., :3]
    h, w = a.shape[:2]
    tl = tuple(int(v) for v in a[1, 1])
    br = tuple(int(v) for v in a[h-2, w-2])
    cc[tl] += 1
    if i % 15 == 0:
        samples.append((i, tl, br))
lines.append("  左上角出现过的不同颜色数: %d" % len(cc))
for c, k in cc.most_common(6):
    lines.append("     %s  %d 帧" % (str(c), k))
for i, tl, br in samples:
    lines.append("   帧%-4d 左上=%s 右下=%s" % (i, str(tl), str(br)))

lines.append("")
lines.append("=== 相邻帧差异（判断是一段连续动画还是多个场景拼的）===")
diffs = []
for i in range(1, n):
    d = np.abs(np.asarray(seq[i], dtype=np.int16) - np.asarray(seq[i-1], dtype=np.int16))
    diffs.append(float(d.mean()))
diffs = np.array(diffs)
lines.append("  平均逐帧差异 %.1f  最大 %.1f  最小 %.1f" % (diffs.mean(), diffs.max(), diffs.min()))
big = np.where(diffs > diffs.mean() + 3 * diffs.std())[0]
lines.append("  突变帧（可能是场景切换）: %s" % str([int(x) for x in big[:20]]))

lines.append("")
lines.append("=== 每帧主体包围盒（看角色有没有大范围移动/换场景）===")
for i in range(0, n, 20):
    a = np.asarray(seq[i])[..., :3].astype(np.float32)
    h, w = a.shape[:2]
    border = np.concatenate([a[:2].reshape(-1,3), a[-2:].reshape(-1,3), a[:, :2].reshape(-1,3), a[:, -2:].reshape(-1,3)])
    bg = np.median(border, axis=0)
    d = np.sqrt(((a - bg) ** 2).sum(axis=2))
    fg = d > 45
    if fg.sum() > 20:
        ys, xs = np.where(fg)
        lines.append("   帧%-4d 前景占比 %4.1f%%  bbox x[%d..%d] y[%d..%d]" % (
            i, 100*fg.mean(), xs.min(), xs.max(), ys.min(), ys.max()))
    else:
        lines.append("   帧%-4d 前景几乎没有" % i)
Path(r"D:/dsh/deskpet/selftest/report-nailong4.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")