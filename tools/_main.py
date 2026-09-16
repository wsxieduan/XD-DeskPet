# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("def main(")
print(s[i:i+1500])
j = s.index("class Console")
seg = s[j:j+3000]
k = seg.index("def __init__")
print("=== Console.__init__ 片段 ===")
print(seg[k:k+1800])
