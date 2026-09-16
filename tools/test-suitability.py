import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker
lines = []
D = Path(r"D:/dsh/图片")
for p in sorted(D.iterdir()):
    if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        continue
    s = petmaker.suitability(p)
    lines.append("")
    lines.append("【%s】 分级 %s —— %s" % (p.name[:52], s["grade"], s["label"]))
    for r in s["reasons"]:
        lines.append("    判断: " + r)
    for a in s["advice"]:
        lines.append("    建议: " + a)
Path(r"D:/dsh/deskpet/selftest/report-suitability.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")