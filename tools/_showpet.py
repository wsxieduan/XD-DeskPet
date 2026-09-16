# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
j = s.index("    def show_pet(")
print(s[j:j+900])
k = s.index("    def on_add_pet(")
print("=== on_add_pet ===")
print(s[k:k+700])
