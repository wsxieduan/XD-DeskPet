"""test-doubao-v3.py —— 豆包图在 v3 安全阀下到底清没清（阿酉第五轮要求闭环的一条）"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker
from rembg import new_session, remove

lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
D = Path(r"D:/dsh/图片/透明底豆包处理谢小端.jpeg")
sess = new_session("isnet-anime")

s = petmaker.suitability(D)
say("suitability 分级 = %s（%s）" % (s["grade"], s["label"]))
say("   近背景色面积占比 = %.1f%%" % (100 * s["info"].get("near_bg_ratio", 0)))
say()
src = Image.open(D).convert("RGBA")
k = 1600 / max(src.size)
work = src.resize((max(1,int(src.width*k)), max(1,int(src.height*k))), Image.LANCZOS)
raw = remove(work, session=sess, post_process_mask=True)
a0 = int((np.asarray(raw)[..., 3] > 128).sum())
say("清理前不透明 = %d" % a0)

for lvl in ("low", "normal", "strong"):
    ratio = petmaker.GAP_LEVELS[lvl]
    # 直接调底层，看每一档自己会不会被安全阀否掉
    out = petmaker.clean_inner_background(raw, work, max_area_ratio=ratio)
    a1 = int((np.asarray(out)[..., 3] > 128).sum())
    say("  档位 %-6s (面积上限 %.3f): 清掉 %d px (%.2f%%)  ->  %s" % (
        lvl, ratio, a0-a1, 100.0*(a0-a1)/max(1,a0),
        "未触发清理" if a0 == a1 else ("清了 %.2f%%" % (100.0*(a0-a1)/max(1,a0)))))

# 直接检查：三档降级后是否放弃
import numpy as np
o = np.asarray(work.convert("RGB")).astype(np.float32)
a = np.asarray(raw.convert("RGBA")).astype(np.float32)
alpha = a[..., 3]
solid = alpha > 128
border = np.concatenate([o[:3].reshape(-1,3), o[-3:].reshape(-1,3),
                         o[:, :3].reshape(-1,3), o[:, -3:].reshape(-1,3)])
bg = np.median(border, axis=0)
d = np.sqrt(((o - bg) ** 2).sum(axis=2))
bgish = d < 14.0
from scipy import ndimage
seed = np.zeros(bgish.shape, dtype=bool)
seed[0,:] |= bgish[0,:]; seed[-1,:] |= bgish[-1,:]
seed[:,0] |= bgish[:,0]; seed[:,-1] |= bgish[:,-1]
lb, _ = ndimage.label(bgish, structure=np.ones((3,3), dtype=int))
outer = set(np.unique(lb[seed])) - {0}
outside = np.isin(lb, list(outer)) if outer else np.zeros(bgish.shape, dtype=bool)
cand = bgish & ~outside
det = petmaker._detail_map(o)
total_detail = max(1, int((det & solid).sum()))
say()
say("安全阀判定明细（tol=14）：")
for ratio in (0.04, 0.016, 0.006):
    kill = petmaker._select_gaps(cand, d, tol=14.0, flat=22.0,
                                 limit=ratio*float(solid.sum()), cluster_px=12)
    lost = int((det & kill).sum())
    say("  面积上限 %.4f: 会清 %-7d px, 细节损失 %-6d (%.2f%%)  -> %s" % (
        ratio, int(kill.sum()), lost, 100.0*lost/total_detail,
        "放行" if lost/total_detail <= 0.06 else "被安全阀否掉"))

Path(r"D:/dsh/deskpet/selftest/report-doubao-v3.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")