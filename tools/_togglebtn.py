# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read().split("\n")
for i, l in enumerate(s, 1):
    if "toggle" in l or "on_add_pet" in l or "act_show" in l or "act_hide" in l:
        print("%5d| %s" % (i, l.rstrip()[:130]))
