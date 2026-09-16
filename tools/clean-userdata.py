# -*- coding: utf-8 -*-
"""clean-userdata.py —— 把数据目录收拾干净。

背景：回归测试里启动的桌宠进程如果没被杀干净，它会在测试脚本"还原数据"之后
继续把自己那份启动快照写回 config.json（character/mode/scale 都被写歪），
还会留下测试用的一次性形象目录。这里一次性收拾：
  ① 反复杀到真的没有桌宠进程为止；
  ② 删掉测试留下的形象目录（只保留主人自己的那只）；
  ③ 还原 config.json / pets.json；
  ④ 校验并打印。
"""
import ctypes, json, os, shutil, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"D:/dsh/deskpet")
DATA = Path(os.environ["APPDATA"]) / "DeskPet"
KEEP_CHARS = {"xiaoduan-doubao"}


def pet_procs():
    """现在还有哪些桌宠进程（打包的 exe + 源码跑的 python）。"""
    out = []
    EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u = ctypes.WinDLL("user32")
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    def cb(h, l):
        if u.IsWindowVisible(h):
            b = ctypes.create_unicode_buffer(64)
            u.GetWindowTextW(h, b, 64)
            if b.value == "桌宠":
                wp = wintypes.DWORD()
                u.GetWindowThreadProcessId(h, ctypes.byref(wp))
                out.append(int(wp.value))
        return True

    u.EnumWindows(EP(cb), 0)
    return out


for i in range(6):
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(BASE / "tools" / "kill-all-deskpet.ps1")],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    left = pet_procs()
    if not left:
        print("桌宠进程已清空（第 %d 轮）" % (i + 1))
        break
    print("第 %d 轮还剩 %s，继续杀" % (i + 1, left))
else:
    print("！仍有进程没杀干净:", pet_procs())

userdir = DATA / "assets" / "user"
for d in sorted(userdir.glob("*")):
    if d.is_dir() and d.name not in KEEP_CHARS:
        shutil.rmtree(d, ignore_errors=True)
        print("删掉测试留下的形象目录:", d.name)
if not (userdir / "xiaoduan-doubao").exists():
    shutil.copytree(BASE / "assets" / "user" / "xiaoduan-doubao", userdir / "xiaoduan-doubao")
    print("主人自己的形象素材已补回")

pets = [{"id": "pet1", "character": "user/xiaoduan-doubao", "x": 299, "y": 328,
         "scale": 1.4, "pid": None}]
(DATA / "pets.json").write_text(json.dumps(pets, indent=2, ensure_ascii=False), encoding="utf-8")
try:
    cfg = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
except Exception:
    cfg = {}
cfg["character"] = "nailong"
cfg["mode"] = "desktop"
# 大小也归位：测试里缩放过的值（比如顶到上限 3.0）会留在全局配置里，
# 单宠物模式（开机自启）那只就会用它显示成一只巨型桌宠
cfg["scale"] = float(pets[0]["scale"])
cfg.setdefault("sound", True)
cfg.setdefault("behavior", {"roam": True, "flee": True, "inertia": True, "recycle": True})
(DATA / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
try:
    names_path = userdir / "names.json"
    names = json.loads(names_path.read_text(encoding="utf-8")) if names_path.exists() else {}
    names = {k: v for k, v in names.items() if k.split("/")[-1] in KEEP_CHARS}
    names["user/xiaoduan-doubao"] = "谢小端（豆包图）"
    names_path.write_text(json.dumps(names, indent=2, ensure_ascii=False), encoding="utf-8")
except Exception as e:
    print("names.json 处理失败:", e)

print()
print("形象:", [p.parent.relative_to(DATA).as_posix() for p in (DATA / "assets").rglob("_frames.json")])
print("pets.json:", json.dumps(pets, ensure_ascii=False))
print("config: character=%s mode=%s scale=%s" % (cfg["character"], cfg["mode"], cfg.get("scale")))
