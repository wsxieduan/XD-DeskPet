import sys, time
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))

P = Path(r"D:/dsh/图片/透明底豆包处理谢小端.jpeg")
S = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图1.jpg")

def report(cut, tag, seconds=None):
    a = np.asarray(cut)[..., 3]
    cov = float((a > 24).mean())
    hs, hb = petmaker.halo_score(cut, want_band=True)
    say("   %-30s 尺寸=%-12s 占比=%.3f  白边=%.3f(带%d)%s" % (
        tag, str(cut.size), cov, hs, hb, ("  %.1fs" % seconds) if seconds else ""))
    return hs

say("=== 豆包图（问题图）===")
r = petmaker.cutout(P, "normal")
report(r.image, "算法")
for fringe in ((0.25, 0.80), (0.35, 0.75), (0.45, 0.70)):
    t0 = time.time()
    ai = petmaker.cutout_ai(P, fringe=fringe)
    hs = report(ai.image, "AI + 白边清理 fringe=%s" % (fringe,), time.time() - t0)
    if fringe == (0.35, 0.75):
        ai.image.save(r"D:/dsh/deskpet/selftest/ai-doubao.png")

say()
say("=== 三视图（不能弄坏）===")
r2 = petmaker.cutout(S, "normal")
v = petmaker.split_views(r2.image, 3)
for i, x in enumerate(v, 1):
    report(x, "算法 view%d" % i)
t0 = time.time()
ai2 = petmaker.cutout_ai(S, fringe=(0.35, 0.75))
v2 = petmaker.split_views(ai2.image, 3)
say("   （AI 用时 %.1fs，切出 %d 个）" % (time.time() - t0, len(v2)))
for i, x in enumerate(v2, 1):
    report(x, "AI view%d" % i)

# 对比图
from PIL import ImageDraw
def checker(size, cell=10):
    q = Image.new("RGB", size, (238,238,238)); d = ImageDraw.Draw(q)
    for yy in range(0, size[1], cell):
        for xx in range(0, size[0], cell):
            if ((xx//cell)+(yy//cell)) % 2:
                d.rectangle([xx, yy, xx+cell-1, yy+cell-1], fill=(202,202,202))
    return q
def panel(imgs, h, title):
    ts = []
    for im in imgs:
        t = im.copy(); t.thumbnail((int(im.width*h/im.height), h), Image.LANCZOS); ts.append(t)
    W = sum(t.width for t in ts) + 30*(len(ts)+1)
    c = Image.new("RGB", (W, h+90), (18,24,40))
    ImageDraw.Draw(c).text((30, 20), title, fill=(160,180,230))
    x = 30
    for t in ts:
        bg = checker(t.size); bg.paste(t, (0,0), t); c.paste(bg, (x, 60)); x += t.width+30
    return c
rows = [panel([r.image, ai.image], 430, "Doubao JPEG:  LEFT = algorithm   RIGHT = AI"),
        panel([v[0], v2[0]], 430, "3-view sheet:  LEFT = algorithm   RIGHT = AI")]
W = max(x.width for x in rows); H = sum(x.height for x in rows) + 20
sheet = Image.new("RGB", (W, H), (18,24,40)); y = 0
for x in rows:
    sheet.paste(x, (0, y)); y += x.height + 20
sheet.save(r"D:/dsh/deskpet/selftest/ai-vs-algorithm.png")
say()
say("对比图: selftest/ai-vs-algorithm.png")
Path(r"D:/dsh/deskpet/selftest/report-fringe.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
