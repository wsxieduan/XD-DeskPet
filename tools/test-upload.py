# -*- coding: utf-8 -*-
"""test-upload.py —— 两张 BUG 卡的验收（阿酉 0915）：

  ① 上传角色时控制台卡死 → 重活进工作线程，界面全程不冻结；连切档位不串图。
  ② 动图上传报 "argument should be a str ... not 'list'" → build_from_slots 认帧列表。

用独立的 APPDATA 跑，不碰主人的数据。
"""
import ctypes, json, os, shutil, subprocess, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
TMP = BASE / "selftest" / "appdata-upload"
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
os.environ["APPDATA"] = str(TMP)
sys.path.insert(0, str(BASE))
import paths
paths.migrate_from_app_dir()
import petmaker
from PIL import Image
lines, fails = [], []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    print(lines[-1], flush=True)


def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok:
        fails.append(n)


# ---------------------------------------------------------------- ① 动图路径
say("== 1. 动图上传：build_from_slots 要认「已经拆好的帧列表」 ==")
GIF = Path(r"D:/dsh/图片/奶龙1.gif")
say("   测试动图: %s" % (GIF if GIF.exists() else "（不存在，改用合成动图）"))
if GIF.exists():
    frames, durs = petmaker.load_sequence(GIF)
else:
    frames, durs = [], None
if len(frames) < 2:
    frames = [petmaker.make_test_fixture(240).convert("RGBA") for _ in range(8)]
    durs = [60] * 8
say("   帧数 %d  每帧时长种类 %s" % (len(frames), sorted(set(durs or []))[:6]))
try:
    tracks, ms = petmaker.build_from_slots({"idle": frames}, "full", slot_ms={"idle": durs})
    check("传帧列表不再炸（以前是 Path(list) 报错）", True, "轨道=%s" % {k: len(v) for k, v in tracks.items()})
    check("待机帧数原样保留", len(tracks["idle"]) == len(frames), "%d vs %d" % (len(tracks["idle"]), len(frames)))
    check("每帧时长也带过来了", ms.get("idle") == list(durs), "%s" % (str(ms.get("idle"))[:40]))
    final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
    check("裁剪缩放后帧数不变（时长数组才对得上）",
          all(len(final[k]) == len(v) for k, v in tracks.items()),
          str({k: len(v) for k, v in final.items()}))
    man = petmaker.install(paths.asset_root_for_write(), "gif-test", final, ms=ms)
    idle = man["idle"]
    check("清单里 idle 是 {files, ms} 形态", isinstance(idle, dict) and "ms" in idle, str(type(idle)))
    check("ms 长度和帧数一致（GIF 0 时长帧的兜底也生效）",
          len(idle["ms"]) == len(idle["files"]) == len(frames),
          "%d / %d / %d" % (len(idle["ms"]), len(idle["files"]), len(frames)))
    # 引擎能不能吃下
    import importlib.util
    spec = importlib.util.spec_from_file_location("deskpet", BASE / "deskpet.py")
    dp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dp)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    raw, per = dp.load_frames("user/gif-test")
    check("桌宠引擎能加载这个形象", "idle" in raw and len(raw["idle"]) == len(frames),
          "idle %d 帧" % len(raw.get("idle", [])))
    check("引擎读到了每帧时长", bool(per.get("idle")) and len(per["idle"]) == len(frames),
          str(len(per.get("idle", []))))
    # 动图 + 额外姿势槽位混用（第七轮测过的场景，别被改坏）
    t2, m2 = petmaker.build_from_slots({"idle": frames, "jumping": frames[:5]},
                                       "full", slot_ms={"idle": durs, "jumping": durs[:5]})
    check("动图 + 额外姿势槽位混用正常",
          len(t2["jumping"]) == 5 and len(t2["idle"]) == len(frames),
          "idle %d / jumping %d" % (len(t2["idle"]), len(t2["jumping"])))
    # 静态图老路径
    stat = petmaker.make_test_fixture(400).convert("RGBA")
    t3, m3 = petmaker.build_from_slots({"idle": stat}, "full")
    check("静态图老路径没被改坏", len(t3["idle"]) == 1 and len(t3.get("jumping", [])) > 1,
          "idle %d / jumping %d" % (len(t3["idle"]), len(t3.get("jumping", []))))
except Exception as e:
    import traceback
    traceback.print_exc()
    check("动图路径不报错", False, repr(e)[:120])

# ---------------------------------------------------------------- ② 线程化
say()
say("== 2. 上传不卡界面：重活必须在工作线程 ==")
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

TESTIMG = TMP / "big.png"
petmaker.make_test_fixture(1200).save(TESTIMG)
DELAY = 2.0
real_cutout = petmaker.cutout
real_ai = petmaker.cutout_ai


def slow_cutout(path, strength="normal", max_side=2048):
    time.sleep(DELAY)                       # 假装在抠一张大图
    return real_cutout(path, strength, max_side=max_side)


def fake_ai(path, model="isnet-anime", max_side=1600, fringe=(0.35, 0.75), gap_level="normal"):
    time.sleep(DELAY)
    return petmaker.CutoutResult(real_cutout(path, "normal", max_side=512).image,
                                 ["AI 假结果"], {"mode": "ai", "model": "fake"})


petmaker.cutout = slow_cutout
petmaker.cutout_ai = fake_ai

dlg = ctl.ImportDialog()
dlg.path = TESTIMG
dlg.show()
app.processEvents()

t0 = time.time()
dlg.reload()
dt = time.time() - t0
check("reload() 立刻返回（以前会一路阻塞到抠完）", dt < 0.5, "%.3f s" % dt)
ticks = {"n": 0}
tm = QTimer()
tm.timeout.connect(lambda: ticks.__setitem__("n", ticks["n"] + 1))
tm.start(50)
end = time.time() + 1.2
while time.time() < end:
    app.processEvents()
    time.sleep(0.01)
check("处理期间主线程照常跑事件循环（界面不冻结）", ticks["n"] >= 15, "%d 次定时器 tick" % ticks["n"])
check("处理期间预览区写着「正在处理」", "正在处理" in dlg.lb_preview.text(), dlg.lb_preview.text()[:24])
check("处理期间「生成桌宠」按钮禁用", not dlg.b_ok.isEnabled())

end = time.time() + 30
while dlg._busy_work and time.time() < end:
    app.processEvents()
    time.sleep(0.02)
check("处理完成、预览出来了", (not dlg._busy_work) and bool(dlg.views),
      "views=%d" % len(dlg.views or []))
check("完成后按钮恢复可用", dlg.b_ok.isEnabled())

say()
say("== 3. 连切档位 3 次：只能认最后一次（不串图） ==")
for idx in (0, 1, 0):                      # AI -> 快速算法 -> AI
    dlg.cb_cut.setCurrentIndex(idx)
    app.processEvents()
    time.sleep(0.15)
end = time.time() + 40
while dlg._busy_work and time.time() < end:
    app.processEvents()
    time.sleep(0.02)
time.sleep(0.3)
app.processEvents()
log = (BASE / "logs" / "ctl.log").read_text(encoding="utf-8", errors="replace")
say("   最后选的档位: %s   实际生效: %s" % (dlg.cb_cut.currentText(), dlg._info.get("mode")))
check("生效的是最后一次选择", dlg._info.get("mode") == "ai", str(dlg._info.get("mode")))
check("过期结果被丢掉了（日志有记录）", "丢弃过期结果" in log,
      str([l for l in log.splitlines() if "丢弃" in l][-2:]))

say()
say("== 4. 生成桌宠同样不卡（动图 110 帧） ==")
frames2, durs2 = petmaker.load_sequence(GIF) if GIF.exists() else (frames, durs)
dlg.views = [frames2[0]]
dlg._anim_frames, dlg._anim_durs = frames2, durs2
dlg.ed_name.setText("测试上传")
dlg.cb_motion.setCurrentIndex(1)
t0 = time.time()
dlg.accept_import()
dt = time.time() - t0
check("accept_import() 立刻返回", dt < 0.5, "%.3f s" % dt)
end = time.time() + 90
while dlg._busy_work and time.time() < end:
    app.processEvents()
    time.sleep(0.02)
say("   pet_id=%s" % dlg.pet_id)
check("生成成功、拿到形象 id", bool(dlg.pet_id), str(dlg.pet_id))
man_file = paths.find_asset(dlg.pet_id + "/_frames.json") if dlg.pet_id else None
check("素材真的落盘了", man_file is not None and man_file.exists(), str(man_file))
if man_file:
    man = json.loads(man_file.read_text(encoding="utf-8"))
    idle = man["idle"]
    n_files = len(idle["files"]) if isinstance(idle, dict) else len(idle)
    n_ms = len(idle.get("ms", [])) if isinstance(idle, dict) else 0
    say("   落盘清单: idle %d 帧, ms %d 个, 轨道 %s" % (n_files, n_ms, list(man)))
    check("动图帧数完整落盘", n_files == len(frames2), "%d vs %d" % (n_files, len(frames2)))
    check("每帧时长也对齐（动图按原速播）", n_ms == n_files, "%d vs %d" % (n_ms, n_files))
    spec2 = importlib.util.spec_from_file_location("deskpet2", BASE / "deskpet.py")
    dp2 = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(dp2)
    raw2, per2 = dp2.load_frames(dlg.pet_id)
    check("桌宠引擎能加载生成的形象", "idle" in raw2, str(list(raw2)))
    check("引擎读到的每帧时长 = 原 GIF 的时长",
          list(per2.get("idle", []))[:6] == [int(x) for x in durs2[:6]],
          "%s" % str(per2.get("idle", [])[:6]))

petmaker.cutout = real_cutout
petmaker.cutout_ai = real_ai
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-upload.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
