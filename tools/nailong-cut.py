# -*- coding: utf-8 -*-
"""奶龙.gif 抠图尝试：描边屏障 + 从画面边缘漫水填充。

原理：卡通角色有闭合的深色描边，把描边当成"墙"，从画面四边往里灌水，
灌不到的地方就是角色。不依赖背景是单色，所以比色键法能应付换场景的 GIF。

输出：
  selftest/nailong-cut/frames/NNN.png   抠好的 RGBA 帧
  selftest/nailong-preview-cut.png      抠图结果 contact sheet（棋盘底）
  selftest/nailong-preview-raw.png      原图 contact sheet（对照）
"""
import os, sys, io
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

SRC = r"D:\dsh\图片\奶龙.gif"
BASE = r"D:\dsh\deskpet\selftest"
OUTD = os.path.join(BASE, "nailong-cut", "frames")

EDGE_THR = 46.0      # 梯度阈值：低于它的像素可以被"水"穿过
EDGE_GROW = 1        # 描边加粗像素数，避免抗锯齿处漏水
MIN_AREA = 40        # 小于这个面积的孤岛当噪声丢掉
FEATHER = 0.6        # 边缘羽化半径


def sobel_mag(gray):
    gx = ndimage.sobel(gray, axis=1, mode="nearest")
    gy = ndimage.sobel(gray, axis=0, mode="nearest")
    return np.hypot(gx, gy) / 4.0


def cut_one(rgb):
    arr = np.asarray(rgb, dtype=np.float32)
    gray = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    mag = sobel_mag(gray)
    edge = mag > EDGE_THR
    if EDGE_GROW:
        edge = ndimage.binary_dilation(edge, iterations=EDGE_GROW)
    free = ~edge
    H, W = free.shape
    seeds = np.zeros_like(free)
    seeds[0, :] = free[0, :]
    seeds[-1, :] = free[-1, :]
    seeds[:, 0] = free[:, 0]
    seeds[:, -1] = free[:, -1]
    bg = ndimage.binary_propagation(seeds, mask=free)
    char = ~bg
    # 去小岛
    lab, cnt = ndimage.label(char)
    if lab.max() > 0:
        sizes = ndimage.sum(char, lab, range(1, lab.max() + 1))
        keep = np.zeros(lab.max() + 1, dtype=bool)
        for i, s in enumerate(sizes, start=1):
            if s >= MIN_AREA:
                keep[i] = True
        # 面积最大的一块一定保留
        keep[int(np.argmax(sizes)) + 1] = True
        char = keep[lab]
    # 填内部小洞：背景区域里面积很小、又不挨着画面边的洞，多半是描边里的空隙
    bglab, bcnt = ndimage.label(bg)
    border_labels = set(bglab[0, :].tolist()) | set(bglab[-1, :].tolist())
    border_labels |= set(bglab[:, 0].tolist()) | set(bglab[:, -1].tolist())
    if bglab.max() > 0:
        for i in range(1, bglab.max() + 1):
            if i in border_labels:
                continue
            m = bglab == i
            if m.sum() < MIN_AREA:
                char |= m
    alpha = (char * 255).astype(np.uint8)
    if FEATHER:
        a = ndimage.gaussian_filter(alpha.astype(np.float32), FEATHER)
        alpha = np.clip(a, 0, 255).astype(np.uint8)
    out = np.dstack([np.asarray(rgb, dtype=np.uint8), alpha])
    return Image.fromarray(out, "RGBA"), char


def checker(size, cell=10):
    im = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if (x // cell + y // cell) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(205, 205, 205))
    return im


def main():
    os.makedirs(OUTD, exist_ok=True)
    im = Image.open(SRC)
    n = getattr(im, "n_frames", 1)
    picks = [0, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120, 132, 140, 148]
    picks = [p for p in picks if p < n]
    cell = 200
    cols = 5
    rows = (len(picks) + cols - 1) // cols
    sheet_cut = checker((cols * cell, rows * cell))
    sheet_raw = Image.new("RGB", (cols * cell, rows * cell), (255, 255, 255))
    lines = []
    for i in range(n):
        im.seek(i)
        rgb = im.convert("RGB")
        out, char = cut_one(rgb)
        out.save(os.path.join(OUTD, "%03d.png" % i))
        cov = float(char.mean())
        # 边缘残余：画面最外一圈里被判成角色的比例
        ring = np.zeros(char.shape, dtype=bool)
        ring[0, :] = ring[-1, :] = True
        ring[:, 0] = ring[:, -1] = True
        leak = float(char[ring].mean())
        if i in picks:
            k = picks.index(i)
            pos = ((k % cols) * cell, (k // cols) * cell)
            big = out.resize((cell, cell), Image.LANCZOS)
            sheet_cut.paste(big, pos, big)
            sheet_raw.paste(rgb.resize((cell, cell), Image.NEAREST), pos)
        if i % 15 == 0 or i == n - 1:
            lines.append("帧%-4d 角色占比%5.1f%%  边框残留%5.1f%%" % (i, cov * 100, leak * 100))
    sheet_cut.save(os.path.join(BASE, "nailong-preview-cut.png"))
    sheet_raw.save(os.path.join(BASE, "nailong-preview-raw.png"))
    io.open(os.path.join(BASE, "nailong-cut-report.txt"), "w", encoding="utf-8").write("\n".join(lines))
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    print("预览:", os.path.join(BASE, "nailong-preview-cut.png"))


main()
