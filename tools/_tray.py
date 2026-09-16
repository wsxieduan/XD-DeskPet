# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("    def _build_tray(self)")
print(s[i:i+2000])
j = s.index("    def on_quit(self)")
print("=== on_quit ===")
print(s[j:j+500])
k = s.index("    def on_toggle(self)")
print("=== on_toggle ===")
print(s[k:k+500])
