# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
for key in ("def load_names", "def save_names", "NAMES_FILE"):
    i = s.find(key)
    print("=== %s ===" % key)
    print(s[i:i+420] if i >= 0 else "没找到")
