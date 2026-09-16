# -*- coding: utf-8 -*-
import io, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"D:\dsh\deskpet"
files = ["deskpet.py", "petctl.py", "petmaker.py", "paths.py", "petlist.py", "main.py",
         "petctl.pyw", "tools/build.py", "README.md", "发布说明.md", "THIRD-PARTY-NOTICES.md"]
for name in files:
    p = os.path.join(BASE, name)
    s = io.open(p, encoding="utf-8", errors="replace").read().split("\n")
    for i, l in enumerate(s, 1):
        if re.search(r"whale|oc/view|oc-backup|oc-src|xioaduan|谢小端|鲸鱼", l):
            print("%-16s %4d| %s" % (name, i, l.strip()[:120]))
