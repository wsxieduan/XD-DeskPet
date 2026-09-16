# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("    def refresh(self)")
j = s.index("    def _selected_pet(self)")
print(s[i:j])
