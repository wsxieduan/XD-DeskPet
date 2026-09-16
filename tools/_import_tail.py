# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\tools\test-import.py", encoding="utf-8").read()
print(s[:1200])
print("......")
print(s[-1500:])
