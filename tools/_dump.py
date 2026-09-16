# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
pm = io.open(r"D:\dsh\deskpet\petmaker.py", encoding="utf-8").read()
i = pm.index("def frames_to_files"); j = pm.index("def install")
sys.stdout.write("=== frames_to_files ~ build_from_slots ===\n" + pm[i:j])
k = pm.index("def install")
sys.stdout.write("=== install ===\n" + pm[k:k+1800])
pa = io.open(r"D:\dsh\deskpet\paths.py", encoding="utf-8").read()
a = pa.index("def asset_roots"); sys.stdout.write("=== asset_roots ===\n" + pa[a:a+700])
b = pa.index("def find_asset"); sys.stdout.write("=== find_asset ===\n" + pa[b:b+500])
bu = io.open(r"D:\dsh\deskpet\tools\build.py", encoding="utf-8").read()
c = bu.index("KEEP_ASSETS"); sys.stdout.write("=== build KEEP_ASSETS ===\n" + bu[c-600:c+900])
