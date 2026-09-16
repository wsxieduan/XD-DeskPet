import sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(r"D:/dsh/deskpet")))
import petmaker
lines = []
P = Path(r"D:/dsh/图片/奶龙.gif")
im = Image.open(P)
lines.append("文件: %s  %d KB" % (P.name, P.stat().st_size // 1024))
lines.append("尺寸: %s   模式: %s   帧数: %d" % (str(im.size), im.mode, getattr(im, "n_frames", 1)))
durs = []
alphas = []
sizes = []
for i in range(getattr(im, "n_frames", 1)):
    im.seek(i)
    durs.append(im.info.get("duration", 0))
    f = im.convert("RGBA")
    sizes.append(f.size)
    a = np.asarray(f)[..., 3]
    alphas.append((float((a < 250).mean()), int(a.min())))
lines.append("每帧时长: " + str(durs[:20]) + (" ..." if len(durs) > 20 else ""))
lines.append("帧尺寸是否一致: " + str(len(set(sizes)) == 1) + "  " + str(list(set(sizes))[:4]))
trans = sum(1 for t, _ in alphas if t > 0.02)
lines.append("有透明像素的帧数: %d / %d" % (trans, len(alphas)))
lines.append("  平均透明占比: %.1f%%" % (100 * np.mean([t for t, _ in alphas])))
lines.append("  最小 alpha 值: " + str(sorted({m for _, m in alphas})[:5]))
lines.append("")
lines.append("=== 用我们自己的读取器再验一次 ===")
seq, ms = petmaker.load_sequence(P)
lines.append("load_sequence 得到 %d 帧，时长 %s" % (len(seq), str(ms[:8]) if ms else None))
lines.append("单帧尺寸: %s" % str(seq[0].size))
a0 = np.asarray(seq[0])[..., 3]
lines.append("首帧透明占比: %.1f%%" % (100 * float((a0 < 250).mean())))
Path(r"D:/dsh/deskpet/selftest/report-nailong.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")