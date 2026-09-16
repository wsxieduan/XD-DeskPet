# -*- coding: utf-8 -*-
import io, re, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\deskpet.py", encoding="utf-8").read()
for m in re.finditer(r"^(class |    def |def )([A-Za-z_0-9]+)", s, re.M):
    line = s[:m.start()].count("\n") + 1
    print("%5d  %s%s" % (line, m.group(1), m.group(2)))
print("总行数", s.count("\n") + 1)
