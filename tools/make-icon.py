"""make-icon.py —— 用当前形象生成程序图标（.ico 和 .png）"""
from pathlib import Path
from PIL import Image

BASE = Path(r"D:/dsh/deskpet")
src = BASE / "assets" / "oc" / "view1" / "idle-1.png"
im = Image.open(src).convert("RGBA")
bb = im.getchannel("A").getbbox()
im = im.crop(bb)
side = max(im.size)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
canvas = canvas.resize((256, 256), Image.LANCZOS)
canvas.save(BASE / "assets" / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
canvas.save(BASE / "assets" / "icon.png")
print("icon.ico / icon.png 已生成", canvas.size)
