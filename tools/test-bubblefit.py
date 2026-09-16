"""test-bubblefit.py —— 长文字/长文件名时气泡要自适应（#1 回归测试）"""
import json, sys, time
from pathlib import Path
import numpy as np
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import paths
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok: fails.append(n)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontMetrics, QFont
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
app = QApplication([])
import importlib.util
spec = importlib.util.spec_from_file_location("deskpet", BASE / "deskpet.py")
dp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dp)

c = json.loads(paths.config_path().read_text(encoding="utf-8"))
c["character"] = "oc/view1"
c.setdefault("behavior", {}).update({"roam": False, "flee": False})
paths.atomic_write_text(paths.config_path(), json.dumps(c, indent=2, ensure_ascii=False))

pet = dp.DeskPet()
pet.show()
QTest.qWait(300)
scr = dp.QApplication.primaryScreen().availableGeometry()
say("屏幕可用区 %dx%d   基准窗口 %dx%d" % (scr.width(), scr.height(), pet.win_w, pet.win_h))
say()

fm = QFontMetrics(QFont("Microsoft YaHei UI", dp.BUBBLE_FONT_PX))

cases = [
    ("短台词", "被摸头了～"),
    ("长文件名", "吃掉啦：2026年第三季度财务分析报告_最终修订版_v7_千万不要删_副本(2).xlsx"),
    ("超长无空格", "A" * 120),
    ("超长中文", "这是一段特别特别长的台词" * 6),
]
for name, text in cases:
    pet.show_bubble(text)
    QTest.qWait(120)
    n_lines = len(pet._bubble_lines or [])
    max_line_w = max((fm.horizontalAdvance(l) for l in (pet._bubble_lines or [])), default=0)
    bubble_w = max_line_w + dp.BUBBLE_PAD_X * 2
    fit = bubble_w <= pet.win_w + 1
    on_screen = pet.win_w <= scr.width() and pet.x() >= scr.left() - 1 and pet.x() + pet.win_w <= scr.right() + 1
    shown = ""
    if pet._bubble_lines:
        shown = "".join(pet._bubble_lines).replace("…", "")
    complete = text.replace("\n", "").startswith(shown[:max(0, len(shown) - 1)])
    say("%-10s 窗口 %dx%d  行数 %d  最长行 %dpx  气泡宽 %dpx" % (
        name, pet.win_w, pet.win_h, n_lines, max_line_w, bubble_w))
    check("  " + name + " 文字没被裁掉", fit, "气泡 %d <= 窗口 %d" % (bubble_w, pet.win_w))
    check("  " + name + " 窗口没超出屏幕", on_screen, "x=%d w=%d" % (pet.x(), pet.win_w))
    if len(text) < 30:
        check("  " + name + " 内容完整", complete, repr(shown))

say()
say("== 换行后精灵位置是否保持 ==")
pet.show_bubble("短")
QTest.qWait(120)
sprite_left = pet.x() + pet.sprite_x
sprite_top = pet.y() + pet.bubble_h
pet.show_bubble("这是一段会换行的很长的文字" * 5)
QTest.qWait(120)
nl = pet.x() + pet.sprite_x
nt = pet.y() + pet.bubble_h
check("换行后精灵没跑掉", abs(nl - sprite_left) <= 3 and abs(nt - sprite_top) <= 3,
      "(%d,%d) -> (%d,%d)" % (sprite_left, sprite_top, nl, nt))
check("窗口确实变高了", pet.win_h > 0)

say()
say("== 实际渲染出非空像素 ==")
pet.show_bubble("吃掉啦：一个特别长的文件名用来测试自适应_2026_最终版.xlsx")
QTest.qWait(200)
pm = pet.grab()
pm.save(str(BASE / "selftest" / "bubble-longtext.png"))
arr = pm.toImage()
ink = 0
for y in range(0, pet.bubble_h, 2):
    for x in range(0, pet.win_w, 2):
        c2 = arr.pixelColor(x, y)
        if c2.red() > 200 and c2.green() > 200:
            ink += 1
check("气泡里画出了文字像素", ink > 60, "%d 个亮像素" % ink)
pet.close()
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-bubblefit.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")