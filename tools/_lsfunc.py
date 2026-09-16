# -*- coding: utf-8 -*-
import io, re, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petmaker.py", encoding="utf-8").read()
for m in re.finditer(r"^def ([a-zA-Z_0-9]+)\(([^)]*)\)", s, re.M):
    line = s[:m.start()].count("\n") + 1
    print("%5d  %s(%s)" % (line, m.group(1), m.group(2)[:110].replace("\n", " ")))
