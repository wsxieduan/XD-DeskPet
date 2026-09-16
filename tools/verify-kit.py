# -*- coding: utf-8 -*-
"""verify-kit.py —— 把试玩包 zip 解到干净目录，按"朋友拿到手"的方式验一遍。

验的是：解压即用（不用 Python）、便携模式数据落在 exe 旁边、自检通过、形象只有奶龙。
用法：python tools/verify-kit.py dist-kit/DeskPet-精简版-v1.4.zip
"""
import json, os, shutil, subprocess, sys, time, zipfile
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(r"D:/dsh/deskpet")
ZIP = Path(sys.argv[1]) if len(sys.argv) > 1 else (BASE / "dist-kit" / "DeskPet-精简版-v1.4.zip")
OUT = BASE / "selftest" / "kit-extract" / ZIP.stem
lines, fails = [], []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    print(lines[-1], flush=True)


def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok:
        fails.append(n)


if OUT.exists():
    shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir(parents=True)
with zipfile.ZipFile(ZIP) as z:
    z.extractall(OUT)
say("解压到: %s" % OUT)
top = [p for p in OUT.iterdir() if p.is_dir()]
appdir = (top[0] / "DeskPet") if top and (top[0] / "DeskPet").exists() else OUT
exe = appdir / "DeskPet.exe"
check("解压出 DeskPet.exe", exe.exists(), str(exe))
check("带了 _internal（不是光秃秃一个 exe）", (appdir / "_internal").exists())
check("带了便携标记 portable.txt", (appdir / "portable.txt").exists())
check("带了给朋友看的说明", any("说明" in p.name for p in top[0].glob("*.txt")) if top else False,
      str([p.name for p in (top[0] if top else OUT).glob("*.txt")]))

# 自检：不设 APPDATA，让它自己决定数据目录（便携模式下应该是 exe 旁边的 data）
env = dict(os.environ)
env.pop("APPDATA", None)
t0 = time.time()
r = subprocess.run([str(exe), "--selftest"], cwd=str(appdir), env=env, timeout=600)
say("--selftest 退出码 %d，用时 %.1fs" % (r.returncode, time.time() - t0))
rep = appdir / "data" / "logs" / "selftest.json"
check("自检报告写在 exe 旁边的 data\（便携模式生效）", rep.exists(), str(rep))
if rep.exists():
    d = json.loads(rep.read_text(encoding="utf-8"))
    say("   characters=%s  frozen=%s" % (d.get("characters"), d.get("frozen")))
    check("打包后确实只有一个形象", d.get("characters") == ["nailong"], str(d.get("characters")))
    check("是打包版（frozen=true）", d.get("frozen") is True)
    check("数据目录就在解压目录里", str(appdir) in str(d.get("DATA")), str(d.get("DATA")))
    # 完整版验 AI 那条链，精简版没有 AI 链（自检里 cutout_ok=false 是预期的），验快速算法那条。
    if d.get("cutout_ok"):
        check("AI 抠图端到端可用（完整版）", True, "alpha 占比 " + str(d.get("cutout_alpha_ratio")))
    elif d.get("algo_cutout_ok"):
        check("快速算法抠图可用（精简版）", True, "alpha 占比 " + str(d.get("algo_cutout_alpha_ratio")))
        check("精简版确实没有 AI 链（符合预期）", not d.get("ai_ok"), str(d.get("ai_error"))[:60])
    else:
        check("至少有一条抠图链可用", False, json.dumps(d, ensure_ascii=False)[:200])
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / ("report-kit-%s.txt" % ZIP.stem)).write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
