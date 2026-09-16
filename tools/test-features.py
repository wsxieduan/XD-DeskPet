"""test-features.py —— 测：删除形象 / 自定义台词 / 图片气泡"""
import importlib.util, json, shutil, sys, time
from pathlib import Path
import numpy as np
from PIL import Image

BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import paths
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(name, ok, detail=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok: fails.append(name)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
app = QApplication([])
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)

cfg_path = paths.config_path()
orig_cfg = cfg_path.read_text(encoding="utf-8")

try:
    say("== 1. 删除形象 ==")
    # 造一个假形象
    fake = BASE / "assets" / "user" / "zz-test-del"
    fake.mkdir(parents=True, exist_ok=True)
    src = BASE / "assets" / "oc" / "view1"
    for f in list(src.glob("*.png"))[:3]:
        shutil.copy2(f, fake / f.name)
    (fake / "_frames.json").write_text(json.dumps({"idle": [f.name for f in list(fake.glob("*.png"))]}), encoding="utf-8")
    names = ctl.load_names(); names["user/zz-test-del"] = "待删除测试"; ctl.save_names(names)
    ctl._CHARS_CACHE["at"] = 0.0; ctl._CHARS_CACHE["data"] = []
    before = [v for _, v in ctl.characters()]
    check("假形象已出现在列表", "user/zz-test-del" in before, str(len(before)) + " 个形象")

    # 直接走删除逻辑（绕过确认框）
    rel = "user/zz-test-del"
    shutil.rmtree(BASE / "assets" / rel, ignore_errors=True)
    nm = ctl.load_names(); nm.pop(rel, None); ctl.save_names(nm)
    ctl._CHARS_CACHE["at"] = 0.0; ctl._CHARS_CACHE["data"] = []
    after = [v for _, v in ctl.characters()]
    check("删除后从列表消失", rel not in after)
    check("目录真的没了", not (BASE / "assets" / rel).exists())
    check("内置形象仍在（兜底形象不该被删）", ctl.paths.DEFAULT_CHARACTER in after)

    say()
    say("== 2. 自定义台词（多条）+ 图片气泡 ==")
    bubdir = BASE / "assets" / "bubbles"
    bubdir.mkdir(parents=True, exist_ok=True)
    # 造一张测试图片（带明显颜色，便于在截图里识别）
    im = Image.new("RGBA", (200, 90), (0, 0, 0, 0))
    for y in range(10, 80):
        for x in range(10, 190):
            im.putpixel((x, y), (255, 200, 0, 255))
    im.save(bubdir / "test-bubble.png")
    items = [{"type": "text", "text": "第一条自定义台词"},
             {"type": "text", "text": "第二条自定义台词"},
             {"type": "image", "file": "bubbles/test-bubble.png"}]
    cfg = json.loads(orig_cfg)
    cfg["bubbles"] = items
    cfg["character"] = "oc/view1"
    cfg["mode"] = "topmost"
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    spec2 = importlib.util.spec_from_file_location("deskpet", BASE / "deskpet.py")
    dp = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(dp)
    pet = dp.DeskPet(); pet.show(); QTest.qWait(300)
    check("桌宠读到了 3 条台词", len(pet.bubble_items) == 3, str(pet.bubble_items))
    check("图片条目被识别", any(k == "image" for k, _ in pet.bubble_items))
    check("窗口按图片气泡变高了", pet.bubble_h >= pet.img_bubble_h + 7,
          "bubble_h=%d img_bubble_h=%d" % (pet.bubble_h, pet.img_bubble_h))

    # 强制显示图片气泡，验证真的画出来
    pet.show_image_bubble("bubbles/test-bubble.png")
    QTest.qWait(200)
    pm = pet.grab()
    pm.save(str(BASE / "selftest" / "bubble-image.png"))
    arr = pm.toImage()
    hit = 0
    for y in range(2, pet.bubble_h):
        for x in range(0, pet.win_w, 3):
            c = arr.pixelColor(x, y)
            if c.red() > 200 and 150 < c.green() < 230 and c.blue() < 80:
                hit += 1
    check("图片真的画进气泡了", hit > 200, "命中黄色像素 %d" % hit)
    QTest.qWait(2400)      # 必须跑事件循环，time.sleep 会把定时器一起冻住
    check("图片气泡会自动收起", pet.bubble_image is None)

    pet.show_bubble("第一条自定义台词")
    QTest.qWait(200)
    pet.grab().save(str(BASE / "selftest" / "bubble-text-custom.png"))
    check("文字气泡仍然正常", pet.bubble_text == "第一条自定义台词")
    pet.close()
finally:
    cfg_path.write_text(orig_cfg, encoding="utf-8")
    shutil.rmtree(BASE / "assets" / "user" / "zz-test-del", ignore_errors=True)

say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-features.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
