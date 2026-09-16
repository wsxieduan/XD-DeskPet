# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\tools\verify-exe-v14.py", encoding="utf-8").read()
i = s.find("def real_drag")
print(repr(s[i-80:i+700]))
j = s.find("exstyle 是 showEvent")
print("exstyle 补丁在:", j >= 0)
