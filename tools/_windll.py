# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
for m in re.finditer(r".*WinDLL.*", s):
    ln = s[:m.start()].count(chr(10)) + 1
    print("%5d| %s" % (ln, m.group(0).strip()))
i = s.index("NO_WIN")
print(s[i-300:i+300])
