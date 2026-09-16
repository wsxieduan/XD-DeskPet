# -*- coding: utf-8 -*-
import io, os, sys
sys.stdout.reconfigure(encoding="utf-8")
D = r"D:\dsh\deskpet\selftest"
for f in sorted(os.listdir(D)):
    if f.startswith("report-") and f.endswith(".txt"):
        s = io.open(os.path.join(D, f), encoding="utf-8", errors="replace").read().split("\n")
        res = [l for l in s if l.startswith("结果")]
        bad = [l for l in s if "[FAIL]" in l or "FAIL" in l]
        print("%-28s %s   （FAIL 行 %d）" % (f, res[-1] if res else "无结果行", len(bad)))
