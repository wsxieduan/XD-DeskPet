# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\deskpet.py", encoding="utf-8").read()
i = s.index("        self._bubble_lines = None")
print(repr(s[i:i+260]))
j = s.index("    def show_bubble(self")
print(repr(s[j:j+330]))
