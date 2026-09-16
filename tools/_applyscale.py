# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\deskpet.py", encoding="utf-8").read()
i = s.index("    def apply_scale(self")
j = s.index("    # -------------------------------------------------------------- 气泡排版")
print(s[i:j])
