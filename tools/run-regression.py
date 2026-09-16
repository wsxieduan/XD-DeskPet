# -*- coding: utf-8 -*-
"""跑一遍源码级回归：先备份主人真实的 config/pets，跑完还原。"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(r"D:/dsh/deskpet")
DATA = Path(os.environ["APPDATA"]) / "DeskPet"
BAK = BASE / "selftest" / "userdata-backup"
# 整目录备份：测试里有的会装/删形象素材（assets/ 下），只备份三个 json 是不够的
if BAK.exists():
    shutil.rmtree(BAK, ignore_errors=True)
shutil.copytree(DATA, BAK, ignore=shutil.ignore_patterns("logs"))
print("已整目录备份 %s -> %s（%d 个文件）"
      % (DATA, BAK, sum(1 for _ in BAK.rglob("*") if _.is_file())))

def pet_window_pids():
    """桌面上还开着"桌宠"窗口的进程 —— 用来确认真的杀干净了。"""
    import ctypes
    from ctypes import wintypes
    out = []
    u = ctypes.WinDLL("user32")
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

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


def kill_pets():
    """反复杀到真的没有为止。
    为什么不能只杀一次：漏掉一只的话，它会在我们"还原数据"之后继续把自己那份启动快照
    写回 config.json —— 表现就是"测试跑完，主人的形象/层级/大小全被改歪了"（真发生过）。"""
    for i in range(6):
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(BASE / "tools" / "kill-all-deskpet.ps1")],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.2)
        left = pet_window_pids()
        if not left:
            return True
        print("  还有桌宠进程 %s，再杀一轮" % left)
    print("  ！杀不干净:", pet_window_pids())
    return False


TESTS = ["test-features.py", "test-toggle.py", "test-toggle2.py", "test-bubblefit.py",
         "test-multipet.py", "test-uifit.py", "test-import.py", "test-anim.py",
         "test-firstrun.py", "test-fallback.py", "test-upload.py",
         "test-sounds.py", "test-bond.py", "test-bond-spin.py", "test-zoom-e2e.py"]
summary = []
for t in TESTS:
    p = BASE / "tools" / t
    if not p.exists():
        summary.append((t, "缺失"))
        continue
    t0 = time.time()
    r = subprocess.run([sys.executable, str(p)], cwd=str(BASE), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900)
    out = (r.stdout or "") + (r.stderr or "")
    fails = [l.strip() for l in out.splitlines() if "[FAIL]" in l]
    oks = [l for l in out.splitlines() if "[OK]" in l]
    summary.append((t, "退出%d 通过%d 失败%d 用时%.0fs" % (r.returncode, len(oks), len(fails), time.time() - t0),
                    fails[:4], out.strip().splitlines()[-2:]))
    print("%-22s %s" % (t, summary[-1][1]))
    for f in fails[:4]:
        print("      ", f)
    for l in out.strip().splitlines()[-2:]:
        print("       >", l[:160])
print()
print("失败测试:", [s[0] for s in summary if "失败0" not in s[1] and s[1] != "缺失"] or "无")
# 还原之前必须先杀掉所有桌宠：测试留下的进程还在跑的话，它会在我们还原之后
# 又把自己那份 pets.json 条目写回去 —— 上一轮就是这么把主人的配置改掉的（pet1 变成了 nailong）。
kill_pets()
# 整目录还原（logs 留着，方便回看）
for name in ("config.json", "pets.json", "ui.json"):
    src = BAK / name
    if src.exists():
        shutil.copy2(src, DATA / name)
if (BAK / "assets").exists():
    if (DATA / "assets").exists():
        shutil.rmtree(DATA / "assets", ignore_errors=True)
    shutil.copytree(BAK / "assets", DATA / "assets")
import hashlib


def _tree(root):
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.md5(p.read_bytes()).hexdigest()
    return out


a, b = _tree(BAK), _tree(DATA)
# pet.pid 是运行期产物（桌宠自己会写），不算"数据被改坏"
a.pop("pet.pid", None)
b.pop("pet.pid", None)
diff = [k for k in a if a.get(k) != b.get(k)]
missing = [k for k in a if k not in b]
print("还原校验：备份 %d 个文件，还原后 %d 个，内容不一致 %d，缺失 %d"
      % (len(a), len(b), len(diff), len(missing)))
for k in (missing + diff)[:6]:
    print("   !!", k)
print("已还原主人数据" + ("（含形象素材）" if not missing else "（有缺失，见上）"))
