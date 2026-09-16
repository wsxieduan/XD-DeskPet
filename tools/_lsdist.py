# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
for d in (r"D:\dsh\deskpet\dist\DeskPet-Lite", r"D:\dsh\deskpet\dist\DeskPet"):
    inner = os.path.join(d, "_internal")
    print("==", d)
    print("  根目录:", sorted(os.listdir(d)))
    names = sorted(os.listdir(inner))
    print("  _internal 里的 .txt:", [n for n in names if n.endswith(".txt")])
    print("  _internal 顶层条目数:", len(names), names[:8])
    print("  models:", os.listdir(os.path.join(inner, "models")) if os.path.exists(os.path.join(inner, "models")) else "无")
