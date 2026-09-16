# -*- coding: utf-8 -*-
"""对照实验：AI 抠图在同一进程里对已知好图是否正常；算法抠图对奶龙各帧出什么结果。"""
import io, os, sys, time
sys.path.insert(0, r"D:\dsh\deskpet")
sys.stdout.reconfigure(encoding="utf-8")
import paths
paths.setup_model_env()
import petmaker
from PIL import Image

GOOD = r"D:\dsh\deskpet\assets\whale-girl\idle-1.png"
print("对照：AI 抠 %s" % GOOD)
t0 = time.time()
try:
    res = petmaker.cutout_ai(GOOD)
    print("  OK coverage=%.3f 用时%.1fs" % (res.info["coverage"], time.time() - t0))
except Exception as e:
    print("  失败:", e)

FR = r"D:\dsh\deskpet\selftest\nailong-frames"
print()
print("奶龙各帧：先看 suitability 分级，再跑算法抠图")
for name in sorted(os.listdir(FR)):
    if not name.endswith(".png"):
        continue
    fp = os.path.join(FR, name)
    s = petmaker.suitability(fp)
    line = "%-10s 分级%s" % (name, s["grade"])
    # 算法抠图默认参数
    for mode, kw in (("fast", {"strength": "fast"}), ("normal", {})):
        try:
            r = petmaker.cutout(fp, **kw)
            line += "  %s: cov=%.2f" % (mode, r.info["coverage"])
        except Exception as e:
            line += "  %s: 失败(%s)" % (mode, str(e)[:24])
    print(line)
