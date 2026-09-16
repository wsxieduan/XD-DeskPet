# -*- coding: utf-8 -*-
import io, re, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\deskpet.py", encoding="utf-8").read().split("\n")
for i, l in enumerate(s, 1):
    if re.search(r"timer", l):
        print("%5d| %s" % (i, l.rstrip()[:140]))
