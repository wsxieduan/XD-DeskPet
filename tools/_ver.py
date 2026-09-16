# -*- coding: utf-8 -*-
import io, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"D:\dsh\deskpet"
for name in ("petctl.py", "deskpet.py", "paths.py", "README.md", "发布说明.md", "main.py"):
    p = os.path.join(BASE, name)
    s = io.open(p, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r".{0,60}(v?1\.[0-9]+|VERSION|版本[:：]).{0,60}", s):
        t = m.group(0).replace("\n", " ")
        print("%-14s %s" % (name, t[:140]))
print("=== 有没有打包 zip 的脚本 ===")
for root, dirs, files in os.walk(BASE):
    if "dist" in root or "build_stage" in root or "__pycache__" in root:
        continue
    for f in files:
        if f.endswith((".py", ".ps1", ".sh", ".md")):
            s = io.open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            if "zipfile" in s or "Compress-Archive" in s:
                print("  ", os.path.join(root, f))
