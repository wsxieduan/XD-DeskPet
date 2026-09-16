# -*- coding: utf-8 -*-
"""找出谁删了主人的形象素材：先还原，再逐个测试跑一遍，每步检查一次。"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"D:/dsh/deskpet")
DATA = Path(os.environ["APPDATA"]) / "DeskPet"
TARGET = DATA / "assets" / "user" / "xiaoduan-doubao"
SRC = BASE / "assets" / "user" / "xiaoduan-doubao"


def state():
    n = len(list((DATA / "assets").rglob("_frames.json")))
    names = (DATA / "assets" / "user" / "names.json")
    keys = []
    if names.exists():
        try:
            keys = list(json.loads(names.read_text(encoding="utf-8")))
        except Exception:
            keys = ["<坏>"]
    pets = []
    p = DATA / "pets.json"
    if p.exists():
        try:
            pets = [x.get("character") for x in json.loads(p.read_text(encoding="utf-8"))]
        except Exception:
            pets = ["<坏>"]
    return "形象数=%d 目标存在=%s names=%s pets=%s" % (
        n, TARGET.exists(), keys, pets)


# 还原
TARGET.parent.mkdir(parents=True, exist_ok=True)
if TARGET.exists():
    shutil.rmtree(TARGET)
shutil.copytree(SRC, TARGET)
print("还原后:", state())
print()
TESTS = ["test-features.py", "test-toggle.py", "test-toggle2.py", "test-bubblefit.py",
         "test-multipet.py", "test-uifit.py", "test-import.py", "test-anim.py",
         "test-firstrun.py", "test-fallback.py", "test-zoom.py", "test-zoom-e2e.py"]
for t in TESTS:
    p = BASE / "tools" / t
    if not p.exists():
        continue
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(BASE / "tools" / "kill-all-deskpet.ps1")],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    before = state()
    subprocess.run([sys.executable, str(p)], cwd=str(BASE), stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=900)
    after = state()
    flag = "  <<< 变了！" if before != after else ""
    print("%-20s %s%s" % (t, after, flag))
    if before != after:
        print("      之前:", before)
