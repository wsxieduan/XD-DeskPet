# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
for name in ("CUT_MODES", "GRADE_STYLE", "MOTION_MODES", "STRENGTHS", "GAP_LEVELS"):
    m = re.search(r"^%s\s*=.*?(?=\n[A-Z_]+\s*=)" % name, s, re.M | re.S)
    if m:
        txt = m.group(0)
        print("=== %s ===\n%s" % (name, txt[:700]))
