# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("def _after_load")
print("=== _after_load ===\n" + s[i:i+700])
print("=== imports (前 45 行) ===\n" + "\n".join(s.split("\n")[:45]))
