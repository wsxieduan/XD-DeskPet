# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\deskpet.py", encoding="utf-8").read()
i = s.index("    def save_cfg(self)")
j = s.index("    def write_pid(self)")
print(s[i:j])
k = s.index("    def load_cfg(self)")
print("=== load_cfg ===")
print(s[k:i])
