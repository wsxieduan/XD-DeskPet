# -*- coding: utf-8 -*-
"""把 奶龙.gif 的每一帧喂给 AI 抠图，看哪些帧能出角色、哪些帧模型认不出来。"""
import io, os, sys, time
sys.path.insert(0, r"D:\dsh\deskpet")
sys.stdout.reconfigure(encoding="utf-8")
import paths
paths.setup_model_env()
import petmaker
from PIL import Image

SRC = r"D:\dsh\图片\奶龙.gif"
OUT = r"D:\dsh\deskpet\selftest\nailong-frames"
os.makedirs(OUT, exist_ok=True)

im = Image.open(SRC)
n = getattr(im, "n_frames", 1)
picks = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 148]
buf = []
buf.append("AI 抠图逐帧结果（model=%s）" % petmaker.AI_MODEL)
for idx in picks:
    im.seek(idx)
    rgb = im.convert("RGB")
    fp = os.path.join(OUT, "f%03d.png" % idx)
    rgb.save(fp)
    t0 = time.time()
    try:
        res = petmaker.cutout_ai(fp)
        cov = res.info.get("coverage")
        buf.append("帧%-4d OK   coverage=%.3f  用时%.1fs  尺寸%s" % (idx, cov, time.time() - t0, res.info.get("content")))
    except Exception as e:
        buf.append("帧%-4d 失败 %s  用时%.1fs" % (idx, e, time.time() - t0))
    print(buf[-1])
io.open(os.path.join(OUT, "ai-report.txt"), "w", encoding="utf-8").write("\n".join(buf))
