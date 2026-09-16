# -*- coding: utf-8 -*-
"""奶龙.gif 逐帧背景分析：边框是不是干净的单色底，能不能用"从边框漫水填充"抠出来。"""
from collections import Counter
from PIL import Image

SRC = r"D:\dsh\图片\奶龙.gif"

im = Image.open(SRC)
n = getattr(im, "n_frames", 1)
rows = []
prev = None
cuts = []
for i in range(n):
    im.seek(i)
    rgb = im.convert("RGB")
    W, H = rgb.size
    px = rgb.load()
    border = []
    for x in range(W):
        for y in (0, 1, H - 2, H - 1):
            border.append(px[x, y])
    for y in range(H):
        for x in (0, 1, W - 2, W - 1):
            border.append(px[x, y])
    q = Counter(((r // 12 * 12, g // 12 * 12, b // 12 * 12) for r, g, b in border))
    top, cnt = q.most_common(1)[0]
    rows.append((i, top, cnt / len(border), len(q)))
    if prev is not None:
        d = sum(abs(a - b) for a, b in zip(top, prev))
        if d > 40:
            cuts.append((i, prev, top, d))
    prev = top

clean = [r for r in rows if r[2] >= 0.90]
mid = [r for r in rows if 0.60 <= r[2] < 0.90]
bad = [r for r in rows if r[2] < 0.60]
print("总帧数 %d" % n)
print("边框单色占比 >=90%% 的帧: %d" % len(clean))
print("边框单色占比 60-90%% 的帧: %d" % len(mid))
print("边框单色占比 <60%% 的帧: %d  -> %s" % (len(bad), [r[0] for r in bad][:60]))
print()
print("=== 底色突变点（换场景）===")
for c in cuts:
    print("   帧%-4d %s -> %s  距离%d" % c)
print()
print("=== 每 5 帧的底色 ===")
for r in rows[::5]:
    print("   帧%-4d 底色%-18s 占比%5.1f%% 边框色种数%3d" % (r[0], str(r[1]), r[2] * 100, r[3]))
