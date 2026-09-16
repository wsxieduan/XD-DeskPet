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
lines.append("共 %d 帧" % len(seq))

# 四角颜色（跨若干帧抽样）
corner_counter = Counter()
for f in seq[::10]:
    a = np.asarray(f)
    h, w = a.shape[:2]
    for (y, x) in ((2, 2), (2, w - 3), (h - 3, 2), (h - 3, w - 3), (2, w // 2), (h // 2, 2)):
        corner_counter[tuple(int(v) for v in a[y, x][:3])] += 1
lines.append("边缘采样最多的颜色:")
for c, n in corner_counter.most_common(5):
    lines.append("   %s  出现 %d 次" % (str(c), n))

# 首帧：边缘是否单一色
a = np.asarray(seq[0])[..., :3].astype(np.float32)
h, w = a.shape[:2]
border = np.concatenate([a[:2].reshape(-1, 3), a[-2:].reshape(-1, 3),
                         a[:, :2].reshape(-1, 3), a[:, -2:].reshape(-1, 3)])
bg = np.median(border, axis=0)
d = np.sqrt(((border - bg) ** 2).sum(axis=1))
lines.append("")
lines.append("首帧边框背景色 = %s   边框 95%% 以内的比例 = %.1f%%" % (
    str([int(v) for v in bg]), 100 * float((d < 30).mean())))

# 主体是不是黄色（判断会不会和背景撞色）
full = np.asarray(seq[0])[..., :3].astype(np.float32)
dfull = np.sqrt(((full - bg) ** 2).sum(axis=2))
fg = dfull > 40
lines.append("首帧前景占比 = %.1f%%" % (100 * float(fg.mean())))
if fg.sum() > 100:
    lines.append("前景平均色 = %s" % str([int(v) for v in full[fg].mean(axis=0)]))
Path(r"D:/dsh/deskpet/selftest/report-nailong2.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")