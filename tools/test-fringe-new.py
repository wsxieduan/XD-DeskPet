"""test-fringe-new.py —— 验证白边判据从"泛白"改成"到背景色距离"后的行为差异"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok: fails.append(n)

def make(edge_rgb, edge_alpha=90):
    """造一张：实心方块 + 一圈指定颜色的半透明软边 + 透明外围。

    edge_rgb 代表"环形区里那些半透明像素的颜色" ——
    它可能是背景色（真白边，该清），也可能是角色自己的浅色（不该清）。
    这正是新旧判据的分水岭。"""
    im = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
    px = im.load()
    for y in range(10, 70):
        for x in range(10, 70):
            px[x, y] = (200, 120, 60, 255)          # 主体
    for y in range(8, 72):
        for x in range(8, 72):
            if 8 <= x < 10 or 70 <= x < 72 or 8 <= y < 10 or 70 <= y < 72:
                px[x, y] = (edge_rgb[0], edge_rgb[1], edge_rgb[2], edge_alpha)
    return im

def cnt_alpha(img, box):
    a = np.asarray(img)[..., 3]
    return int((a[box[1]:box[3], box[0]:box[2]] > 12).sum())

ring = (6, 6, 74, 74)

say("== 场景 A：白底图，环形区就是背景色（真白边）—— 应该清掉 ==")
a_img = make((255, 255, 255), 90)
b0 = cnt_alpha(a_img, ring)
a_new = cnt_alpha(petmaker.kill_white_fringe(a_img, bg=np.array([255., 255., 255.])), ring)
say("   原始 %d -> 新判据 %d" % (b0, a_new))
check("白边被清掉", a_new < b0, "%d -> %d" % (b0, a_new))

say()
say("== 场景 B：白底图，但环形区是角色自己的浅色（不该清）==")
b_img = make((248, 246, 244), 150)
c0 = cnt_alpha(b_img, ring)
c_new = cnt_alpha(petmaker.kill_white_fringe(b_img, bg=np.array([255., 255., 255.])), ring)
say("   原始 %d -> 新判据 %d" % (c0, c_new))

say()
say("== 场景 C（关键）：黑底图 + 环形区是角色的浅色 —— 旧判据的坑 ==")
d_img = make((235, 233, 230), 150)
d0 = cnt_alpha(d_img, ring)
d_new = cnt_alpha(petmaker.kill_white_fringe(d_img, bg=np.array([0., 0., 0.])), ring)
d_old = cnt_alpha(petmaker.kill_white_fringe(d_img, bg=None), ring)
say("   环形区 alpha>12 像素：原始 %d" % d0)
say("   新判据（按背景色=黑，距离远 → 保留）: %d" % d_new)
say("   旧判据（泛白+低饱和 → 一律清）      : %d" % d_old)
check("新判据保住了黑底上的浅色边缘", d_new == d0, "%d vs 原始 %d" % (d_new, d0))
check("旧判据会把这圈浅色啃掉（证明这次改动有价值）", d_old < d0, "%d vs 原始 %d" % (d_old, d0))

say()
say("== 真实三视图上的完整 AI 抠图（回归）==")
S = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图1.jpg")
if S.exists():
    r = petmaker.cutout_ai(S, max_side=1200, gap_level="normal")
    a = np.asarray(r.image)[..., 3]
    hs, hb = petmaker.halo_score(r.image, want_band=True)
    say("   尺寸=%s 不透明占比=%.3f 白边=%.3f(带%d)" % (str(r.image.size), float((a > 24).mean()), hs, hb))
    check("白边指标仍然很低", hs < 0.05, "%.3f" % hs)   # 改动前是 0.59
    check("抠图结果正常（占比合理）", 0.2 < float((a > 24).mean()) < 0.6)

say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
Path(r"D:/dsh/deskpet/selftest/report-fringe-new.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")