# -*- coding: utf-8 -*-
"""make-placeholder.py —— 生成"零版权风险"的占位形象 assets/placeholder。

为什么要有它：内置的奶龙是版权素材（阿酉第十轮 review 的发布红线），
发布物里不能带。发布包用这个程序画出来的几何小当默认形象 —— 纯代码画的，不涉及任何第三方形象。

产出三条轨道：idle（呼吸+眨眼）/ jumping（点她时的挤压回弹）/ running（溜达时左右倾）。
形象自带透明底，不需要抠图。
"""
import io, json, math, os, sys
from PIL import Image, ImageDraw

OUT = r"D:\dsh\deskpet\assets\placeholder"
S = 320                      # 画布边长（和"用户自己传的形象统一到 320 高"对齐）
BODY = (108, 140, 246)       # 主体色（靛蓝）
BODY_D = (78, 106, 208)      # 暗部
BELLY = (238, 243, 255)
INK = (44, 52, 78)
BLUSH = (250, 178, 186)


def draw_frame(bob=0.0, squash=1.0, lean=0.0, blink=False, feet=0.0):
    """squash>1 = 拉长，<1 = 压扁；lean = 倾斜角度；feet = 脚的交替偏移。"""
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = S // 2
    base_y = S - 46                              # 脚底基准线
    body_h = 176 * squash
    body_w = 196 / max(0.6, squash)              # 压扁就变宽，体积守恒一点
    top = base_y - body_h - bob
    # 脚
    for i, dx in enumerate((-46, 46)):
        off = feet * (1 if i == 0 else -1)
        d.ellipse([cx + dx - 26 + off, base_y - 16, cx + dx + 26 + off, base_y + 10],
                  fill=BODY_D)
    # 身体
    d.rounded_rectangle([cx - body_w / 2, top, cx + body_w / 2, base_y - 4],
                        radius=body_w * 0.44, fill=BODY)
    d.rounded_rectangle([cx - body_w / 2 + 16, top + 62, cx + body_w / 2 - 16, base_y - 16],
                        radius=body_w * 0.32, fill=BELLY)
    # 头顶的小芽
    d.line([cx, top + 2, cx, top - 26], fill=BODY_D, width=9)
    d.ellipse([cx - 12, top - 46, cx + 18, top - 18], fill=(126, 206, 168))
    # 眼睛
    ey = top + 66
    for dx in (-40, 40):
        if blink:
            d.line([cx + dx - 15, ey + 6, cx + dx + 15, ey + 6], fill=INK, width=7)
        else:
            d.ellipse([cx + dx - 15, ey - 15, cx + dx + 15, ey + 15], fill=INK)
            d.ellipse([cx + dx - 3, ey - 9, cx + dx + 7, ey + 1], fill=(255, 255, 255))
    # 腮红 + 嘴
    for dx in (-70, 70):
        d.ellipse([cx + dx - 17, ey + 18, cx + dx + 17, ey + 40], fill=BLUSH)
    d.arc([cx - 22, ey + 22, cx + 22, ey + 52], 15, 165, fill=INK, width=6)
    if lean:
        im = im.rotate(lean, resample=Image.BICUBIC, center=(cx, base_y))
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".png") or f == "_frames.json":
            os.remove(os.path.join(OUT, f))
    manifest = {}

    # 待机：呼吸 + 偶尔眨眼
    frames, ms = [], []
    for i in range(24):
        t = i / 24.0
        bob = 6 * math.sin(t * 2 * math.pi)
        squash = 1.0 + 0.035 * math.sin(t * 2 * math.pi + 1.2)
        blink = i % 12 == 11
        frames.append(draw_frame(bob=bob, squash=squash, blink=blink))
        ms.append(110)
    manifest["idle"] = {"files": [], "ms": ms}

    # 点击反馈：压扁 -> 拉长 -> 回弹
    jump, jms = [], []
    seq = [(0.0, 0.86, 0), (2.0, 0.92, 0), (12.0, 1.14, 0), (18.0, 1.08, 0), (8.0, 0.98, 0),
           (0.0, 1.03, 0), (0.0, 0.97, 0), (0.0, 1.0, 0)]
    for bob, squash, _ in seq:
        jump.append(draw_frame(bob=bob, squash=squash))
        jms.append(70)
    manifest["jumping"] = {"files": [], "ms": jms}

    # 走动：左右倾斜 + 交替抬脚
    run, rms = [], []
    for i in range(12):
        t = i / 12.0
        lean = 7 * math.sin(t * 2 * math.pi)
        feet = 9 * math.sin(t * 2 * math.pi)
        run.append(draw_frame(bob=3 * abs(math.sin(t * 2 * math.pi)), lean=lean, feet=feet))
        rms.append(90)
    manifest["running"] = {"files": [], "ms": rms}

    for track, imgs in (("idle", frames), ("jumping", jump), ("running", run)):
        names = []
        for i, im in enumerate(imgs, 1):
            name = "%s-%d.png" % (track, i)
            im.save(os.path.join(OUT, name), optimize=True)
            names.append(name)
        manifest[track]["files"] = names
    io.open(os.path.join(OUT, "_frames.json"), "w", encoding="utf-8").write(
        json.dumps(manifest, indent=1))
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) / 1024.0
    print("占位形象: %s  idle %d 帧 / jumping %d 帧 / running %d 帧  共 %.0f KB"
          % (OUT, len(frames), len(jump), len(run), total))


main()
