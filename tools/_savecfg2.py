# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
i = s.index("def save_cfg")
print(s[i-400:i+500])
j = s.index("PIDFILE.unlink()")
print("=== 退出时 unlink pet.pid 的上下文（deskpet.py）===")
d = io.open(r"D:\dsh\deskpet\deskpet.py", encoding="utf-8").read()
k = d.index("PIDFILE.unlink()")
print(d[k-700:k+200])
