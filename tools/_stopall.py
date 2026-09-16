# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("def stop_all_pets")
print(s[i-200:i+700])
