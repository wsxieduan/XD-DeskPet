# -*- coding: utf-8 -*-
"""给自检造一张"合成小人"测试图，验证 AI 抠图链路（不需要随包带任何角色素材）。
先验证模型认不认这张图。"""
import sys, os
sys.path.insert(0, r"D:\dsh\deskpet")
sys.stdout.reconfigure(encoding="utf-8")
import paths
paths.setup_model_env()
from PIL import Image, ImageDraw
import petmaker

OUT = r"D:\dsh\deskpet\selftest\fixture.png"

def draw_fixture(size=512):
    im = Image.new("RGB", (size, size), (176, 214, 240))   # 天蓝底
    d = ImageDraw.Draw(im)
    cx = size // 2
    # 身体
    d.rounded_rectangle([cx - 92, 250, cx + 92, 430], radius=40, fill=(240, 240, 245),
                        outline=(60, 50, 60), width=7)
    # 手臂
    d.line([(cx - 92, 290), (cx - 150, 350)], fill=(240, 240, 245), width=34)
    d.line([(cx + 92, 290), (cx + 150, 350)], fill=(240, 240, 245), width=34)
    # 腿
    d.line([(cx - 45, 425), (cx - 45, 480)], fill=(60, 50, 60), width=30)
    d.line([(cx + 45, 425), (cx + 45, 480)], fill=(60, 50, 60), width=30)
    # 头
    d.ellipse([cx - 105, 70, cx + 105, 280], fill=(252, 226, 206), outline=(60, 50, 60), width=7)
    # 头发
    d.chord([cx - 112, 58, cx + 112, 250], 180, 360, fill=(86, 60, 110), outline=(60, 50, 60), width=6)
    d.ellipse([cx - 128, 150, cx - 88, 260], fill=(86, 60, 110))
    d.ellipse([cx + 88, 150, cx + 128, 260], fill=(86, 60, 110))
    # 眼睛
    d.ellipse([cx - 62, 170, cx - 30, 220], fill=(40, 36, 48))
    d.ellipse([cx + 30, 170, cx + 62, 220], fill=(40, 36, 48))
    d.ellipse([cx - 54, 178, cx - 42, 192], fill=(255, 255, 255))
    d.ellipse([cx + 38, 178, cx + 50, 192], fill=(255, 255, 255))
    # 腮红 + 嘴
    d.ellipse([cx - 88, 214, cx - 60, 236], fill=(250, 190, 190))
    d.ellipse([cx + 60, 214, cx + 88, 236], fill=(250, 190, 190))
    d.arc([cx - 22, 218, cx + 22, 250], 20, 160, fill=(60, 50, 60), width=5)
    return im

im = draw_fixture()
im.save(OUT)
print("测试图:", OUT, im.size)

res = petmaker.cutout_ai(OUT, max_side=512)
import numpy as np
cov = float((np.asarray(res.image)[..., 3] > 128).mean())
print("AI 抠图结果 coverage=%.3f 尺寸=%s" % (cov, res.image.size))
print("分级:", petmaker.suitability(OUT)["grade"])
