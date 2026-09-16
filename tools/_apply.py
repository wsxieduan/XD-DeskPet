# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("    def apply(")
print(s[i:i+1400])
j = s.index("    def on_scale(")
print(s[j:j+400])
