# -*- coding: utf-8 -*-
"""把 D:\dsh\图片\奶龙.gif 做成内置形象 assets/nailong。

为什么不抠图：这张 GIF 是**不透明**的卡通片段（149 帧、每帧 30ms、底色随场景变），
AI 分割模型在它上面判定"整张图都是背景"（16 帧抽样全失败），
描边屏障法也会漏水（角色占比只剩 0.6%~14%）—— 抠不出来。
所以按原图直接用，只把四角磨圆，让它看起来像一张贴纸而不是一块方块。
"""
import io, os, sys
sys.path.insert(0, r"D:\dsh\deskpet")
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageChops, ImageDraw

SRC = r"D:\dsh\图片\奶龙.gif"
DST = r"D:\dsh\deskpet\assets\nailong"
PET_ID = "nailong"
CORNER_RATIO = 0.14        # 圆角半径占边长的比例
SS = 4                     # 圆角遮罩的超采样倍数（抗锯齿）

def rounded_mask(size, ratio=CORNER_RATIO, ss=SS):
    w, h = size
    m = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(m)
    r = int(round(min(w, h) * ratio)) * ss
    d.rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], radius=r, fill=255)
    return m.resize((w, h), Image.LANCZOS)

def main():
    import json
    im = Image.open(SRC)
    n = getattr(im, "n_frames", 1)
    frames, durs = [], []
    for i in range(n):
        im.seek(i)
        frames.append(im.convert("RGBA").copy())
        durs.append(int(im.info.get("duration", 0) or 0))
    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    print("源: %d 帧 %dx%d 每帧 %s ms" % (len(frames), w, h, sorted(set(durs))))
    durs = [d if 16 <= d <= 5000 else 100 for d in durs]
    mask = rounded_mask((w, h))
    os.makedirs(DST, exist_ok=True)
    for old in os.listdir(DST):
        if old.endswith(".png") or old == "_frames.json":
            os.remove(os.path.join(DST, old))
    names = []
    for i, f in enumerate(frames, 1):
        if f.size != (w, h):
            c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            c.paste(f, ((w - f.width) // 2, (h - f.height) // 2), f)
            f = c
        if f.getchannel("A").getextrema() == (255, 255):
            f.putalpha(mask)                       # 原图不透明 -> 直接套圆角
        else:
            a = ImageChops.multiply(f.getchannel("A"), mask)
            f.putalpha(a)
        name = "idle-%d.png" % i
        f.save(os.path.join(DST, name), optimize=True)
        names.append(name)
    manifest = {"idle": {"files": names, "ms": durs}}
    io.open(os.path.join(DST, "_frames.json"), "w", encoding="utf-8").write(
        json.dumps(manifest, indent=1))
    total = sum(os.path.getsize(os.path.join(DST, x)) for x in os.listdir(DST))
    print("输出: %s  帧数 %d  单帧 %dx%d  总体积 %.1f MB" % (DST, len(names), w, h, total / 1048576.0))

main()
