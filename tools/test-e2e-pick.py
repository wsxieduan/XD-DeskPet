import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import numpy as np
import petmaker, paths
lines = []
cands = [
    paths.APP / "assets" / "oc" / "view1" / "idle-3.png",
    paths.APP / "assets" / "whale-girl" / "idle-1.png",
    paths.APP / "assets" / "whale-girl" / "spritesheet.webp",
]
for p in cands:
    if not p.exists():
        lines.append("跳过（不存在）: " + str(p))
        continue
    t0 = time.time()
    try:
        r = petmaker.cutout_ai(p, max_side=512)
        a = np.asarray(r.image)
        cov = float((a[..., 3] > 128).mean())
        lines.append("%-52s 尺寸=%-11s 前景占比=%.3f  用时 %.1fs" % (p.name, str(r.image.size), cov, time.time()-t0))
    except Exception as e:
        lines.append("%-52s 失败: %s" % (p.name, str(e)[:90]))
Path(r"D:/dsh/deskpet/selftest/report-e2e-pick.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")