# -*- coding: utf-8 -*-
import io, re, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
lines = s.split("\n")
pats = ["whale", "oc/view", "内置", "cut_mode", "抠图", "ASSETS", "grade", "suitab"]
for i, l in enumerate(lines, 1):
    if any(p in l for p in pats):
        print("%5d| %s" % (i, l[:150]))
