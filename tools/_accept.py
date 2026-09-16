# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("    def accept_import(self)")
j = s.index("def to_color(c)")
print(s[i:j])
