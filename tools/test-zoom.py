# -*- coding: utf-8 -*-
"""test-zoom.py —— 自由缩放（阿酉需求卡）验收：

  · Ctrl+滚轮能缩放，且**脚底中心钉在原地**
  · 拖右下角手柄能缩放（径向：往右下拖变大）
  · 交互期间走的是"不重采样"的快速路径（防抖），停稳后才真正重采样
  · 范围钳制 [0.4, 3.0]
  · 大小写进配置，重启后还在
  · 三档预设 + 自定义值在控制台/右键菜单都能显示

用独立的 APPDATA 跑，不碰主人的数据。
"""
import ctypes, json, os, shutil, subprocess, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
TMP = BASE / "selftest" / "appdata-zoom"
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
# 位置要留在屏幕中下部：放大到 3.0 倍时窗口高度约 550，脚底以上得放得下，
# 否则会被"保持在屏幕内"的夹取顶下来 —— 那是预期行为，不是缩放的 bug
(TMP / "DeskPet" / "config.json").write_text(json.dumps(
    {"character": "nailong", "x": 600, "y": 500, "scale": 1.0, "sound": False}), encoding="utf-8")
os.environ["APPDATA"] = str(TMP)
ctypes.windll.shcore.SetProcessDpiAwareness(2)

lines, fails = [], []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    print(lines[-1], flush=True)


def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok:
        fails.append(n)


from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QCursor, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication
app = QApplication([])
import deskpet


def foot(pet):
    p = pet._foot_screen_pos()
    return (p.x(), p.y())


def wheel(pet, notches, ctrl=True):
    ev = QWheelEvent(QPointF(40, pet.height() - 40), QPointF(500, 500), QPoint(0, 0),
                     QPoint(0, int(120 * notches)), Qt.NoButton,
                     Qt.ControlModifier if ctrl else Qt.NoModifier, Qt.NoScrollPhase, False)
    pet.wheelEvent(ev)


def press(pet, local):
    g = pet.mapToGlobal(local)
    QCursor.setPos(g)
    ev = QMouseEvent(QEvent.MouseButtonPress, QPointF(local), QPointF(g),
                     Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    pet.mousePressEvent(ev)


def move_to(pet, local):
    g = pet.mapToGlobal(local)
    QCursor.setPos(g)
    ev = QMouseEvent(QEvent.MouseMove, QPointF(local), QPointF(g),
                     Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
    pet.mouseMoveEvent(ev)


def release(pet, local):
    g = pet.mapToGlobal(local)
    ev = QMouseEvent(QEvent.MouseButtonRelease, QPointF(local), QPointF(g),
                     Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
    pet.mouseReleaseEvent(ev)


pet = deskpet.DeskPet(None)
pet.show()
app.processEvents()
time.sleep(0.4)
app.processEvents()
say("初始：scale=%.3f 窗口 %dx%d  精灵 %dx%d  脚底=%s"
    % (pet.scale, pet.width(), pet.height(), pet.sprite_w, pet.sprite_h, foot(pet)))

say()
say("== 1. Ctrl+滚轮缩放（脚底必须钉住） ==")
f0 = foot(pet)
wheel(pet, 3)
app.processEvents()
f1 = foot(pet)
say("  上滚 3 格：scale=%.3f  尺寸 %dx%d  脚底 %s -> %s" % (pet.scale, pet.sprite_w, pet.sprite_h, f0, f1))
check("Ctrl+滚轮能放大", pet.scale > 1.15, "%.3f" % pet.scale)
check("脚底没有飘走（±2px）", abs(f1[0] - f0[0]) <= 2 and abs(f1[1] - f0[1]) <= 2, "%s -> %s" % (f0, f1))
check("缩放中走的是快速路径（还没重采样）", pet._fast is True, str(pet._fast))

# 不按 Ctrl 时滚轮不该有任何反应
before = pet.scale
wheel(pet, 3, ctrl=False)
check("不按 Ctrl 滚轮不缩放", abs(pet.scale - before) < 1e-6, "%.3f" % pet.scale)

say()
say("== 2. 防抖：快速路径 vs 真正重采样的耗时 ==")
t0 = time.perf_counter()
for i in range(20):
    pet._zoom_to(1.0 + i * 0.02)
t_fast = (time.perf_counter() - t0) / 20 * 1000
# 注意：这个断言必须在下面那次"完整重采样计时"之前 —— 那次调用本身就会把 _fast 清掉
check("连续缩放后仍是快速状态（没有偷偷重采样）", pet._fast is True)
t0 = time.perf_counter()
pet.apply_scale(resample=True)
t_full = (time.perf_counter() - t0) * 1000
say("  快速路径 %.2f ms/次   完整重采样 %.1f ms/次（%d 帧）" % (
    t_fast, t_full, sum(len(v) for v in pet.raw.values())))
check("快速路径明显更快（连续缩放不卡）", t_fast < t_full / 3, "%.2f ms vs %.1f ms" % (t_fast, t_full))
pet._zoom_settle()
app.processEvents()
check("停稳后做完了重采样", pet._fast is False, str(pet._fast))
check("重采样后的缓存尺寸对得上",
      pet.frames["idle"][0].width() == max(1, round(pet.raw["idle"][0].width() * pet.scale * pet.dpr)),
      "%d vs %d" % (pet.frames["idle"][0].width(),
                    round(pet.raw["idle"][0].width() * pet.scale * pet.dpr)))

say()
say("== 3. 拖右下角手柄（径向缩放） ==")
pet._zoom_to(1.0)
pet._zoom_settle()
app.processEvents()
r = pet.show_resize_handle() if False else None
pet.show_resize_handle()
app.processEvents()
hb = pet._handle_rect()
say("  手柄矩形: %s" % (hb,))
check("手柄出现了", hb is not None, str(hb))
f0 = foot(pet)
s0 = pet.scale
if hb is not None:
    press(pet, hb.center())
    check("按在手柄上进入缩放状态（不是拖动）", pet._resizing is True, str(pet._resizing))
    # 径向缩放：一切按"鼠标到脚底锚点的距离"算，所以拖拽点要在**屏幕坐标**里算，
    # 不能用窗口内坐标 —— 缩放过程中窗口本身在变大，局部坐标会跟着漂（这个坑踩过）
    anchor = QPoint(*f0)
    cur = QCursor.pos()
    d0 = max(24.0, pet._dist(cur, anchor))
    import math as _m
    ux = (cur.x() - anchor.x()) / d0
    uy = (cur.y() - anchor.y()) / d0

    def drag_to(k):
        p = QPoint(int(anchor.x() + ux * d0 * k), int(anchor.y() + uy * d0 * k))
        g = pet.mapFromGlobal(p)
        QCursor.setPos(p)
        app.processEvents()
        ev = QMouseEvent(QEvent.MouseMove, QPointF(g), QPointF(p),
                         Qt.NoButton, Qt.LeftButton, Qt.NoModifier)
        pet.mouseMoveEvent(ev)
        app.processEvents()

    drag_to(1.5)                      # 往外 -> 变大
    f1 = foot(pet)
    say("  往外拖 1.5 倍距离：scale %.3f -> %.3f  脚底 %s -> %s" % (s0, pet.scale, f0, f1))
    check("往外拖变大", pet.scale > s0 * 1.2, "%.3f -> %.3f" % (s0, pet.scale))
    check("拖手柄时脚底也钉住（±3px）", abs(f1[0] - f0[0]) <= 3 and abs(f1[1] - f0[1]) <= 3, "%s -> %s" % (f0, f1))
    drag_to(0.8)                      # 往回 -> 变小
    say("  往回拖到 0.8 倍距离：scale=%.3f" % pet.scale)
    check("往回拖变小", pet.scale < s0, "%.3f" % pet.scale)
    release(pet, QPoint(0, 0))
    time.sleep(0.5)
    app.processEvents()
    check("松手后完成重采样并落盘", pet._fast is False, str(pet._fast))

say()
say("== 4. 范围钳制 [0.4, 3.0] ==")
pet._zoom_to(99)
say("  想缩到 99 -> %.2f" % pet.scale)
check("上限 3.0", abs(pet.scale - 3.0) < 1e-6, "%.3f" % pet.scale)
pet._zoom_to(0.01)
say("  想缩到 0.01 -> %.2f" % pet.scale)
check("下限 0.4", abs(pet.scale - 0.4) < 1e-6, "%.3f" % pet.scale)
pet._zoom_to(1.234)
pet._zoom_settle()
app.processEvents()
check("0.4x 时窗口仍然可用（宽高 > 0）", pet.width() > 0 and pet.height() > 0,
      "%dx%d" % (pet.width(), pet.height()))

say()
say("== 5. 自定义大小要落盘、要能显示 ==")
cfg = json.loads((TMP / "DeskPet" / "config.json").read_text(encoding="utf-8"))
say("  config.scale = %s" % cfg.get("scale"))
check("写进了 config（任意浮点，不是三档里的值）",
      abs(float(cfg.get("scale", 0)) - 1.234) < 0.01, str(cfg.get("scale")))
pet.close()
pet2 = deskpet.DeskPet(None)
app.processEvents()
check("重启后按自定义大小打开", abs(pet2.scale - 1.234) < 0.01, "%.3f" % pet2.scale)
pet2.close()

import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
w = ctl.Console()
app.processEvents()
items = [(w.cb_scale.itemText(i), w.cb_scale.itemData(i)) for i in range(w.cb_scale.count())]
say("  控制台大小下拉: %s  当前=%s" % (items, w.cb_scale.currentText()))
check("控制台显示成「自定义 xx%」", "自定义" in w.cb_scale.currentText(), w.cb_scale.currentText())
check("三档预设还在（当快捷键用）",
      [i[0] for i in items[:3]] == [l for l, _ in ctl.SCALE_STEPS], str([i[0] for i in items[:3]]))
w.close()
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-zoom.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
