"""test-import.py —— 验证"上传图片生成桌宠"整条流水线（不经 GUI）"""
import json, shutil, sys
from pathlib import Path
import numpy as np
from PIL import Image

BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import petmaker

lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(name, ok, detail=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok: fails.append(name)

IMAGES = sorted(Path(r"D:/dsh/图片").glob("*.jp*g")) + sorted(Path(r"D:/dsh/图片").glob("*.png"))
say("== 1. 对每张图做可用性分析 ==")
for p in IMAGES:
    info = petmaker.analyze(p)
    say("   %-58s %s %s" % (p.name[:56], str(info["size"]),
        ("自带透明通道" if info["has_alpha"] else "背景干净度 %.0f%%" % (100 * info["bg_uniform"]))
        + ("  ⚠ " + "；".join(info["warnings"]) if info["warnings"] else "  可用")))

say()
say("== 2. 三种动态档位 ==")
src = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图.jpg")
res = petmaker.cutout(src, "normal")
views = petmaker.split_views(res.image, 3)
say("   抠图: 背景 %s 干净度 %.0f%% 透明夹缝 %d 处 白边指标 %.3f" % (
    res.info.get("bg"), 100 * res.info.get("bg_uniform", 0),
    res.info.get("gaps_transparent", 0), petmaker.halo_score(views[0])))
for mode in ("still", "reactive", "full"):
    tracks = petmaker.make_frames(views[0], mode)
    final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
    sizes = {k: len(v) for k, v in final.items()}
    say("   %-9s 轨道 %-34s 单帧尺寸 %s" % (mode, str(sizes), str(final["idle"][0].size)))
    check("档位 " + mode + " 能生成", all(len(v) > 0 for v in final.values()))

say()
say("== 3. 真正安装一个（用第 2 个视图，模拟用户上传）==")
tracks = petmaker.make_frames(views[1], "full")
final = petmaker.frames_to_files(tracks, petmaker.TARGET_H)
manifest = petmaker.install(BASE / "assets", "test-upload", final)
d = BASE / "assets" / "user" / "test-upload"
check("素材目录已生成", d.exists() and (d / "_frames.json").exists(), str(d))
n = len(list(d.glob("*.png")))
check("帧文件数量正确", n == sum(len(v) for v in manifest.values()), str(n) + " 个 png")
say("   _frames.json: " + json.dumps(manifest))

cnt = 0
bad = []
for f in d.glob("*.png"):
    a = np.asarray(Image.open(f).convert("RGBA"))
    if a[..., 3].max() == 0:
        bad.append(f.name)
    cnt += 1
check("所有帧都不是空的", not bad, ("空帧: " + str(bad)) if bad else str(cnt) + " 帧都有内容")

say()
say("== 4. 桌宠引擎能不能吃下它 ==")
import importlib
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
names = ctl.load_names()
names["user/test-upload"] = "测试上传"
ctl.save_names(names)
chars = ctl.characters()
say("   控制台形象列表: " + str([c[0] for c in chars]))
check("新形象出现在列表里", any(v == "user/test-upload" for _, v in chars))

cfg = ctl.load_cfg()
cfg["character"] = "user/test-upload"
ctl.save_cfg(cfg)
import subprocess
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-pets.ps1")], capture_output=True, creationflags=0x08000000)
import time
subprocess.Popen([str(ctl.PYW), str(BASE / "deskpet.py")], cwd=str(BASE),
                 creationflags=0x08000000 | 0x00000008)
time.sleep(3.5)
check("桌宠用新形象起来了", ctl.pet_running(), "pid=" + str(ctl.read_pid()))
ctl.stop_pet()

say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-import.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
