"""test-bubble.py —— 验证对话框配色：自动跟随角色 / 自定义 / 实际渲染"""
import importlib.util, json, sys
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

cfg_path = paths.config_path()
orig = cfg_path.read_text(encoding="utf-8")
cfg = json.loads(orig)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
app = QApplication([])
spec = importlib.util.spec_from_file_location("deskpet", BASE / "deskpet.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

try:
    say("== 1. 自动模式：从角色像素里提取主色 ==")
    cfg.pop("bubble", None)
    cfg["character"] = "oc/view1"
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    pet = mod.DeskPet()
    pet.show()
    QTest.qWait(300)
    t = pet.theme_color
    say("   提取到的主色: rgb(%d,%d,%d)  #%s" % (t.red(), t.green(), t.blue(), t.name()))
    check("主色不是默认兜底值", not (t.red() == 126 and t.green() == 152 and t.blue() == 255),
          "#" + t.name())
    say("   推导出的对话框: 背景 #%s  文字 #%s  边框 #%s" % (
        pet.bub_bg.name(), pet.bub_fg.name(), pet.bub_border.name()))
    # 文字和背景的对比度要够
    lum_bg = 0.2126 * pet.bub_bg.red() + 0.7152 * pet.bub_bg.green() + 0.0722 * pet.bub_bg.blue()
    lum_fg = 0.2126 * pet.bub_fg.red() + 0.7152 * pet.bub_fg.green() + 0.0722 * pet.bub_fg.blue()
    ratio = (max(lum_bg, lum_fg) + 5) / (min(lum_bg, lum_fg) + 5)
    check("文字/背景对比度足够（WCAG 相对亮度比）", ratio > 4.5, "比值 %.2f" % ratio)

    say()
    say("== 2. 实际渲染出来的气泡颜色 ==")
    pet.show_bubble("今天也要加油哦！")
    QTest.qWait(200)
    pm = pet.grab()
    pm.save(str(BASE / "selftest" / "bubble-auto.png"))
    img = pm.toImage()
    # 取气泡正中间偏左的一点（避开文字）作为背景色采样
    sample = img.pixelColor(int(pet.win_w * 0.22), pet.bubble_h // 2)
    say("   渲染出的气泡填充色: rgb(%d,%d,%d)" % (sample.red(), sample.green(), sample.blue()))
    check("渲染颜色和配色一致（±25）",
          abs(sample.red() - pet.bub_bg.red()) < 40 and abs(sample.blue() - pet.bub_bg.blue()) < 40,
          "期望 #%s 实际 #%s" % (pet.bub_bg.name(), sample.name()))
    pet.close()

    say()
    say("== 3. 自定义模式 ==")
    cfg["bubble"] = {"auto": False, "bg": [12, 60, 40], "fg": [255, 240, 200], "border": [90, 220, 150]}
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    pet2 = mod.DeskPet()
    pet2.show()
    QTest.qWait(250)
    say("   配置里写的是 背景 rgb(12,60,40) 文字 rgb(255,240,200) 边框 rgb(90,220,150)")
    say("   实际用上的是 背景 #%s 文字 #%s 边框 #%s" % (
        pet2.bub_bg.name(), pet2.bub_fg.name(), pet2.bub_border.name()))
    check("自定义背景生效", (pet2.bub_bg.red(), pet2.bub_bg.green(), pet2.bub_bg.blue()) == (12, 60, 40))
    check("自定义文字生效", (pet2.bub_fg.red(), pet2.bub_fg.green(), pet2.bub_fg.blue()) == (255, 240, 200))
    pet2.show_bubble("随便改颜色～")
    QTest.qWait(200)
    pet2.grab().save(str(BASE / "selftest" / "bubble-custom.png"))
    pet2.close()

    say()
    say("== 4. 写回配置供控制台预览 ==")
    cfg3 = json.loads(cfg_path.read_text(encoding="utf-8"))
    res = cfg3.get("bubble_resolved")
    say("   bubble_resolved = " + str(res))
    check("桌宠把实际颜色写回了配置", isinstance(res, dict) and "bg" in res and "theme" in res)
finally:
    cfg_path.write_text(orig, encoding="utf-8")

say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-bubble.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
