# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("class ImportDialog")
j = s.index("    def _after_load(self)")
print(s[i:i+1200])
print("......[中间略]......")
k = s.index("    def reload(self)")
print(s[k:j])
