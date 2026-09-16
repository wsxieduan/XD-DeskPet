# -*- coding: utf-8 -*-
"""把帧降采样成 ASCII 图，用字符"看"一眼画面构成。输出 UTF-8 文件。"""
import io
from collections import Counter
from PIL import Image

SRC = r"D:\dsh\图片\奶龙.gif"
OUT = r"D:\dsh\deskpet\selftest\ascii-nailong.txt"

def render(rgb, cols=64, rows=32):
    sm = rgb.resize((cols, rows), Image.BOX)
    px = sm.load()
    out = []
    for y in range(rows):
        line = []
        for x in range(cols):
            r, g, b = px[x, y]
            lum = (r * 299 + g * 587 + b * 114) // 1000
            mx, mn = max(r, g, b), min(r, g, b)
            sat = mx - mn
            if sat < 30:
                line.append(" .:-=+*#%@"[min(9, lum * 10 // 256)])
            else:
                if r >= g and r >= b:
                    line.append("R" if g > b else "O")
                elif g >= r and g >= b:
                    line.append("G" if b > r else "Y")
                else:
                    line.append("B" if r > g else "C")
        out.append("".join(line))
    return "\n".join(out)

buf = io.StringIO()
im = Image.open(SRC)
for idx in (0, 20, 60, 100, 125, 148):
    im.seek(idx)
    rgb = im.convert("RGB")
    buf.write("=" * 70 + "\n")
    buf.write("帧 %d\n" % idx)
    buf.write(render(rgb) + "\n")
    q = Counter(rgb.getdata())
    buf.write("主色: " + str([(c, "%.0f%%" % (n / (160 * 160) * 100)) for c, n in q.most_common(6)]) + "\n")
    # 边框 4 角各 6x6 平均
    px = rgb.load()
    for name, (x0, y0) in (("左上", (0, 0)), ("右上", (154, 0)), ("左下", (0, 154)), ("右下", (154, 154))):
        acc = [0, 0, 0]
        for x in range(x0, x0 + 6):
            for y in range(y0, y0 + 6):
                p = px[x, y]
                acc[0] += p[0]; acc[1] += p[1]; acc[2] += p[2]
        buf.write("   %s 6x6 均值 %s\n" % (name, tuple(v // 36 for v in acc)))
io.open(OUT, "w", encoding="utf-8").write(buf.getvalue())
print("ok", OUT)
