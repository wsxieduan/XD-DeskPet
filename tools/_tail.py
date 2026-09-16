# -*- coding: utf-8 -*-
import io, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"D:\dsh\deskpet\tools"
for t in ("test-features.py", "test-toggle.py", "test-multipet.py", "test-import.py"):
    s = io.open(os.path.join(BASE, t), encoding="utf-8").read().split("\n")
    tail = s[-14:]
    print("=== %s 尾部 ===" % t)
    for l in tail:
        print("   ", l[:130])
    print("   sys.exit 出现:", sum(1 for l in s if "sys.exit" in l), " assert 出现:", sum(1 for l in s if l.strip().startswith("assert")))
