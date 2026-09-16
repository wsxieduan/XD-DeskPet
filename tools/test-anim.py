"""test-anim.py —— 动图（GIF）与多姿势上传的端到端测试"""
import sys, json, time
from pathlib import Path
import numpy as np
from PIL import Image
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import petmaker, paths
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(name, ok, detail=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok: fails.append(name)

# 造一张透明底动图：一个小方块的弹跳 + 颜色变化，每帧时长不同
frames = []
for i in range(6):
    im = Image.new("RGBA", (120, 160), (0, 0, 0, 0))
    px = im.load()
    y0 = 40 + int(30 * abs(np.sin(i / 6.0 * np.pi)))
    for y in range(y0, y0 + 60):
        for x in range(35, 85):
            px[x, y] = (60 + i * 25, 120, 220 - i * 20, 255)
    frames.append(im)
gif = BASE / "selftest" / "test-anim.gif"
frames[0].save(gif, save_all=True, append_images=frames[1:],
               duration=[80, 120, 160, 120, 80, 200], loop=0, disposal=2)
say("测试动图: %s  %d 帧" % (gif.name, len(frames)))
say()

say("== 1. load_sequence 读动图 ==")
seq, durs = petmaker.load_sequence(gif)
check("读出了全部帧", len(seq) == 6, "%d 帧" % len(seq))
check("读出了每帧时长", durs is not None and len(durs) == 6, str(durs))
check("帧带透明通道", np.asarray(seq[0])[..., 3].min() == 0)

say()
say("== 2. 静态图仍走原路 ==")
static = BASE / "assets" / "whale-girl" / "idle-1.png"
s2, d2 = petmaker.load_sequence(static)
check("静态图返回单帧且无时长", len(s2) == 1 and d2 is None, "%d 帧 durations=%s" % (len(s2), d2))

say()
say("== 3. build_from_slots：动图当待机 + 程序化生成其它轨道 ==")
tracks, ms = petmaker.build_from_slots({"idle": gif}, mode="full")
check("idle 用了动图的 6 帧", len(tracks.get("idle", [])) == 6, str({k: len(v) for k, v in tracks.items()}))
check("idle 带上了每帧时长", ms.get("idle") == [80, 120, 160, 120, 80, 200], str(ms.get("idle")))
check("其它轨道被程序化生成", len(tracks.get("jumping", [])) > 1 and len(tracks.get("running", [])) > 1)

say()
say("== 4. 多姿势：给三种不同来源 ==")
tracks2, ms2 = petmaker.build_from_slots(
    {"idle": gif, "jumping": static, "running": gif}, mode="full")
check("idle 来自动图", len(tracks2["idle"]) == 6)
check("jumping 来自静态图（程序化出多帧）", len(tracks2["jumping"]) > 2, "%d 帧" % len(tracks2["jumping"]))
check("running 来自动图", len(tracks2["running"]) == 6)

say()
say("== 5. 安装 + 桌宠能读回每帧时长 ==")
final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
man = petmaker.install(paths.asset_root_for_write(), "zz-anim-test", final, ms=ms)
check("_frames.json 写成了带 ms 的新格式",
      isinstance(man.get("idle"), dict) and man["idle"].get("ms") == [80, 120, 160, 120, 80, 200],
      json.dumps(man.get("idle"))[:80])
from PySide6.QtWidgets import QApplication
app = QApplication([])
import importlib.util
spec = importlib.util.spec_from_file_location("deskpet", BASE / "deskpet.py")
dp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dp)
c = json.loads(paths.config_path().read_text(encoding="utf-8"))
c["character"] = "user/zz-anim-test"
paths.config_path().write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
pet = dp.DeskPet()
check("桌宠读出 6 帧 idle", len(pet.frames["idle"]) == 6, "%d 帧" % len(pet.frames["idle"]))
check("桌宠读到了每帧时长", (pet.frame_ms or {}).get("idle") == [80, 120, 160, 120, 80, 200],
      str((pet.frame_ms or {}).get("idle")))
pet.play("idle")
check("播放时立刻用了第 1 帧的 80ms", pet.timer.interval() == 80, "%dms" % pet.timer.interval())
pet.close()

say()
say("== 6. 清理 ==")
import shutil
shutil.rmtree(paths.asset_root_for_write() / "user" / "zz-anim-test", ignore_errors=True)
c["character"] = "oc/view1"
paths.config_path().write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")
gif.unlink(missing_ok=True)
say("  已清理测试形象")
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-anim.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")