# -*- coding: utf-8 -*-
import sys, io
sys.path.insert(0, r"D:\dsh\deskpet")
sys.stdout.reconfigure(encoding="utf-8")
import paths
paths.setup_model_env()
import petmaker, numpy as np
FIX = r"D:\dsh\deskpet\selftest\fixture2.png"
petmaker.make_test_fixture().save(FIX)
for name, fn in (("AI", lambda: petmaker.cutout_ai(FIX, max_side=512)),
                 ("算法", lambda: petmaker.cutout(FIX, "normal", max_side=512))):
    try:
        r = fn()
        cov = float((np.asarray(r.image)[..., 3] > 128).mean())
        print("%s 抠图 coverage=%.3f 尺寸=%s" % (name, cov, r.image.size))
    except Exception as e:
        print("%s 失败: %r" % (name, e))
