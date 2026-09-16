# -*- coding: utf-8 -*-
"""调试：为什么"180° 翻转回来"对不上原图。"""
import os, shutil, subprocess, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
TMP = BASE / "selftest" / "appdata-spin-dbg"
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
(TMP / "DeskPet" / "config.json").write_text(
    '{"character": "nailong", "scale": 1.4, "sound": false}', encoding="utf-8")
os.environ["APPDATA"] = str(TMP)
import paths
paths.migrate_from_app_dir()
import importlib.util
spec = importlib.util.spec_from_file_location("deskpet", BASE / "deskpet.py")
dp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dp)
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from PIL import Image, ImageChops
app = QApplication([])
pet = dp.DeskPet(None)
pet.show()
app.processEvents()
time.sleep(0.6)
pet.timer.stop()
print("track=%s index=%d sprite=%dx%d bubble_h=%d sprite_x=%d"
      % (pet.track, pet.index, pet.sprite_w, pet.sprite_h, pet.bubble_h, pet.sprite_x), flush=True)


def grab():
    app.processEvents()
    img = pet.grab().toImage().convertToFormat(QImage.Format_RGBA8888)
    full = Image.frombytes("RGBA", (img.width(), img.height()), bytes(img.constBits())).convert("RGB")
    k = img.width() / float(pet.width())
    box = (int(pet.sprite_x * k), int(pet.bubble_h * k),
           int((pet.sprite_x + pet.sprite_w) * k), int((pet.bubble_h + pet.sprite_h) * k))
    return full.crop(box)


def diff(a, b):
    d = ImageChops.difference(a, b).convert("L")
    return sum(1 for v in d.get_flattened_data() if v > 16)


pet._bond_rot = 0.0
a1 = grab()
pet.index = (pet.index + 1) % len(pet.frames[pet.track])
pet.update()
a2 = grab()                    # 换一帧：看"帧不同"会带来多大差异
pet.index = (pet.index - 1) % len(pet.frames[pet.track])
pet._bond_rot = 0.0
pet.update()
a3 = grab()                    # 回到同一帧同一角度：应该和 a1 完全一样
pet._bond_rot = 180.0
pet.update()
b180 = grab()
print("同一帧两次抓图差异:", diff(a1, a3), " (应为 0)")
print("换一帧的差异:", diff(a1, a2), " (帧动画本身的差异)")
print("180° 直接比:", diff(a1, b180))
print("180° 翻转回来比:", diff(a1, b180.transpose(Image.ROTATE_180)))
print("原图自翻转比:", diff(a1, a1.transpose(Image.ROTATE_180)))
print("图像尺寸:", a1.size)
# 非透明像素的重心（判断内容有没有真的转过去）
def com(im):
    px = im.load()
    sx = sy = n = 0
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            if abs(r) + abs(g) + abs(b) > 30:
                sx += x; sy += y; n += 1
    return (sx / max(1, n), sy / max(1, n), n)
print("重心 a1:", com(a1), "  b180:", com(b180), "  自翻转:", com(a1.transpose(Image.ROTATE_180)))
