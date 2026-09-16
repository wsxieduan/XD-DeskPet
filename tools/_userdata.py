# -*- coding: utf-8 -*-
import io, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
D = os.path.join(os.environ["APPDATA"], "DeskPet")
for n in ("config.json", "pets.json"):
    p = os.path.join(D, n)
    print("===", n, os.path.exists(p))
    if os.path.exists(p):
        print(io.open(p, encoding="utf-8").read()[:800])
print("=== assets 目录 ===")
for root, dirs, files in os.walk(os.path.join(D, "assets")):
    if "_frames.json" in files:
        print("  ", os.path.relpath(root, D))
