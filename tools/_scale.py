# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
for pat in (r"cb_scale = ", r"cb_char = ", r"def on_char", r"SCALE_STEPS", r"def ensure_first", r"petlist.ensure_first"):
    for m in re.finditer(re.escape(pat), s):
        i = s.rfind("\n", 0, m.start()) + 1
        j = s.find("\n", m.start())
        line = s[:m.start()].count("\n") + 1
        print("%5d| %s" % (line, s[i:j].strip()[:130]))
    print("---")
i = s.index("self.cb_scale = ")
print(s[i-200:i+900])
