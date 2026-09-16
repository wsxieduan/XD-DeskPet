# -*- coding: utf-8 -*-
"""把奶龙 GIF 抽帧拼成一张 contact sheet，供人眼/视觉复核。"""
import os
from PIL import Image

SRC = r"D:\dsh\图片\奶龙.gif"
OUT = r"D:\dsh\deskpet\selftest\nailong-sheet.png"

im = Image.open(SRC)
n = getattr(im, "n_frames", 1)
picks = [0, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120, 132, 140, 148]
picks = [p for p in picks if p < n]
cols, cell = 5, 200
rows = (len(picks) + cols - 1) // cols
sheet = Image.new("RGB", (cols * cell, rows * cell), (255, 255, 255))
for i, idx in enumerate(picks):
    im.seek(idx)
    f = im.convert("RGB").resize((cell, cell), Image.NEAREST)
    sheet.paste(f, ((i % cols) * cell, (i // cols) * cell))
sheet.save(OUT)
print("saved", OUT, sheet.size, "frames", n, "picked", picks)
