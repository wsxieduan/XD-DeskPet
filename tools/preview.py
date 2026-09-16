"""preview.py —— 生成白边检查图，格纹背景下一眼就能看出抠干净没有"""
from pathlib import Path
from PIL import Image, ImageDraw

BASE = Path(r"D:/dsh/deskpet")

def checker(size, cell=10):
    w, h = size
    q = Image.new("RGB", (w, h), (240, 240, 240))
    d = ImageDraw.Draw(q)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if ((x // cell) + (y // cell)) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(200, 200, 200))
    return q

def paste(canvas, im, x, y, box_h):
    t = im.copy()
    t.thumbnail((int(im.width * box_h / im.height), box_h), Image.LANCZOS)
    bg = checker(t.size)
    bg.paste(t, (0, 0), t)
    canvas.paste(bg, (x, y))
    return t.width

# 1) 三个视图的立绘
views = [Image.open(BASE / "assets" / "oc-src" / ("view%d.png" % i)).convert("RGBA") for i in (1, 2, 3)]
W = sum(int(v.width * 600 / v.height) for v in views) + 40 * 4
c1 = Image.new("RGB", (W, 680), (20, 26, 44))
d = ImageDraw.Draw(c1)
d.text((40, 18), "cutout check - 3 views (checkerboard background)", fill=(150, 170, 220))
x = 40
for v in views:
    x += paste(c1, v, x, 50, 560) + 40
c1.save(BASE / "selftest" / "cutout-check.png")

# 2) 动画帧
frames = []
for track in ("idle", "jumping", "running"):
    for n in (1, 3, 5):
        p = BASE / "assets" / "oc" / "view1" / ("%s-%d.png" % (track, n))
        if p.exists():
            frames.append((track + "-" + str(n), Image.open(p).convert("RGBA")))
W2 = sum(int(f.width * 300 / f.height) for _, f in frames) + 20 * (len(frames) + 1)
c2 = Image.new("RGB", (W2, 380), (20, 26, 44))
d2 = ImageDraw.Draw(c2)
d2.text((20, 12), "animation frames (checkerboard background)", fill=(150, 170, 220))
x = 20
for _, f in frames:
    x += paste(c2, f, x, 40, 300) + 20
c2.save(BASE / "selftest" / "frames-check.png")
print("已生成 selftest/cutout-check.png 和 selftest/frames-check.png")
