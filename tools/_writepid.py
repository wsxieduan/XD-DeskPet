# -*- coding: utf-8 -*-
import io, re, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\deskpet.py", encoding="utf-8").read()
i = s.find("def write_pid")
print("=== write_pid ===")
print(s[i:i+600])
for m in re.finditer(r"PIDFILE", s):
    ln = s[:m.start()].count(chr(10)) + 1
    print("PIDFILE @", ln, ":", s[s.rfind(chr(10), 0, m.start())+1:s.find(chr(10), m.start())].strip()[:110])
