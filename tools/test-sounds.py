# -*- coding: utf-8 -*-
"""test-sounds.py —— 互动音效绑定（阿酉《需求卡-音效与联系人》功能一）验收。

  · 内置音效是不是合法 WAV、时长够短
  · 绑定/多绑随机/清空回落，桌宠侧解析对不对
  · 非 WAV 上传有没有明确提示（不静默吞掉）
  · 端到端：真起一只桌宠，点它一下，日志里能看到"播了哪个音效"
用独立的 APPDATA 跑，不碰主人的数据。
"""
import ctypes, json, os, shutil, subprocess, sys, time, wave
from ctypes import wintypes
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")
TMP = BASE / "selftest" / "appdata-sounds"
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
(TMP / "DeskPet" / ".migrated").write_text("t", encoding="utf-8")
os.environ["APPDATA"] = str(TMP)
ctypes.windll.shcore.SetProcessDpiAwareness(2)
import paths
paths.migrate_from_app_dir()
lines, fails = [], []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    print(lines[-1], flush=True)


def check(n, ok, d=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + n + ("  " + d if d else ""))
    if not ok:
        fails.append(n)


say("== 1. 内置音效 ==")
BUILTIN = sorted((BASE / "assets" / "sounds").glob("*.wav"))
say("   内置: " + ", ".join(p.name for p in BUILTIN))
check("内置音效 >= 3 个", len(BUILTIN) >= 3, "%d 个" % len(BUILTIN))
bad = []
for p in BUILTIN:
    try:
        with wave.open(str(p)) as w:
            secs = w.getnframes() / float(w.getframerate())
            if w.getnchannels() != 1 or w.getsampwidth() != 2 or secs > 1.5:
                bad.append("%s(%dch/%dbit/%.2fs)" % (p.name, w.getnchannels(),
                                                     w.getsampwidth() * 8, secs))
    except Exception as e:
        bad.append("%s 读不了:%s" % (p.name, e))
check("都是单声道 16bit、时长 <= 1.5s（太长的会盖住上一条）", not bad, str(bad))

say()
say("== 2. 桌宠侧：绑定解析 / 随机池 / 回落 ==")
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
import deskpet

cfgp = paths.config_path()


def write_cfg(**kw):
    try:
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}                        # 全新数据目录：还没有 config.json
    cfg.update(kw)
    cfgp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


write_cfg(character="nailong", x=20, y=300, scale=1.0, sound=True,
          sounds={"click": ["sounds/bell.wav"], "grab": [], "land": [], "spawn": []})
pet = deskpet.DeskPet(None)
say("   click -> %s" % [p.name for p in pet.sfx["click"]])
check("绑定的 click 解析到了 bell.wav", [p.name for p in pet.sfx["click"]] == ["bell.wav"],
      str([p.name for p in pet.sfx["click"]]))
check("没绑的（grab）回落到内置 boop", [p.name for p in pet.sfx["grab"]] == ["boop.wav"],
      str([p.name for p in pet.sfx["grab"]]))

# 多绑随机：把 winsound 换掉，看它到底挑了哪些
played = []
real_play = deskpet.winsound.PlaySound
deskpet.winsound.PlaySound = lambda path, flags: played.append(Path(path).name)
write_cfg(sounds={"click": ["sounds/bell.wav", "sounds/pop.wav"], "grab": [], "land": [],
                  "spawn": []})
pet._load_sounds()
for _ in range(12):
    pet.play_sfx("click")
say("   12 次随机结果: %s" % sorted(set(played)))
check("多绑时两类都出现过（随机池生效）",
      set(played) == {"bell.wav", "pop.wav"}, str(sorted(set(played))))
played.clear()
pet.sound_on = False
pet.play_sfx("click")
check("关掉音效后不出声", not played, str(played))
pet.sound_on = True
pet.play_sfx("click")
check("开着音效时确实调用了系统播放", len(played) == 1, str(played))

say()
say("== 3. 控制台：上传 / 提示 / 清空 ==")
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
# 关键：进程内 new 出来的桌宠会把 pet.pid 写成**本测试进程**的 pid，
# 控制台一 apply() 就会去"停掉那只桌宠" —— 把自己杀掉，静默退出、连堆栈都没有（踩过）。
# stop_pet 现在会拒杀本进程，这里也顺手把 pet.pid 清掉，让状态干净。
pet.close()
try:
    paths.pid_path().unlink()
except Exception:
    pass
w = ctl.Console()
app.processEvents()
writes = []
ctl.save_cfg = lambda cfg: (writes.append(dict(cfg)),
                            paths.atomic_write_text(ctl.CONFIG, json.dumps(cfg, indent=2,
                                                                          ensure_ascii=False)))
msgs = []


# 直接把 Qt 类替换成假的：给 QMessageBox 这种 Qt 类挂静态方法会踩到 PySide6 的
# "把 Python 可调用对象塞进 C++ 静态槽"，进程会静默退出（0 码、无堆栈）—— 这次踩了。
class FakeMsgBox:
    @staticmethod
    def information(*a, **k):
        msgs.append(a[2] if len(a) > 2 else "")

    @staticmethod
    def warning(*a, **k):
        msgs.append(a[2] if len(a) > 2 else "")

    @staticmethod
    def question(*a, **k):
        msgs.append(a[2] if len(a) > 2 else "")
        return ctl.QMessageBox.No


class FakeFileDialog:
    FILES = []

    @staticmethod
    def getOpenFileNames(*a, **k):
        return list(FakeFileDialog.FILES), ""


ctl.QMessageBox = FakeMsgBox
ctl.QFileDialog = FakeFileDialog
# 造两个假的"用户音效"：一个 wav、一个 mp3
userdir = TMP / "user-sounds"
userdir.mkdir(exist_ok=True)
good = userdir / "myclick.wav"
with wave.open(str(good), "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(22050)
    f.writeframes(b"\x00\x00" * 2205)
badfile = userdir / "myclick.mp3"
badfile.write_bytes(b"ID3fake")
FakeFileDialog.FILES = [str(good), str(badfile)]
w.on_add_sound("click")
app.processEvents()
landed = paths.asset_root_for_write() / "sounds" / "myclick.wav"
check("WAV 被复制进音效库", landed.exists(), str(landed))
check("绑定写进了 config", any("sounds/myclick.wav" in (c.get("sounds", {}).get("click") or [])
                            for c in writes), str([c.get("sounds") for c in writes][-1:]))
check("非 WAV 有明确提示（不是静默吞掉）", any("WAV" in m for m in msgs), str(msgs[:1])[:80])
w.refresh()
app.processEvents()
say("   控制台状态: click=%s" % w.sfx_status["click"].text())
# 这一类的绑定数量要显示出来（前面几节已经绑了 bell/pop，这次又加了 myclick）
check("控制台显示已绑数量", w.sfx_status["click"].text().startswith("3 个"),
      w.sfx_status["click"].text())
# 清空
writes.clear()
w.on_clear_sound("click")
app.processEvents()
check("清空后 config 里这一类是空数组",
      any((c.get("sounds", {}).get("click") == []) for c in writes),
      str([c.get("sounds") for c in writes][-1:]))
w.close()
pet.close()
deskpet.winsound.PlaySound = real_play

say()
say("== 4. 端到端：真点一下桌宠，日志里要能看到播的是哪个音效 ==")
write_cfg(character="nailong", x=20, y=300, scale=1.0, sound=True,
          sounds={"click": ["sounds/chirp.wav"], "grab": [], "land": [], "spawn": []},
          behavior={"roam": False, "flee": False})
env = dict(os.environ)
env["APPDATA"] = str(TMP)
p = subprocess.Popen([sys.executable, str(BASE / "deskpet.py")], cwd=str(BASE), env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)
u = ctypes.WinDLL("user32")
u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
u.IsWindowVisible.argtypes = [wintypes.HWND]
u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
EP = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
wins = []


def cb(h, l):
    wp = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(wp))
    if wp.value == p.pid and u.IsWindowVisible(h):
        r = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(r))
        if r.right - r.left > 20:
            wins.append((h, r.left, r.top, r.right - r.left, r.bottom - r.top))
    return True


u.EnumWindows(EP(cb), 0)
if wins:
    h, x, y, ww, wh = wins[0]
    lp = ((wh - 30) << 16) | (ww // 2)
    u.PostMessageW(h, 0x0200, 0, lp)
    u.PostMessageW(h, 0x0201, 1, lp)
    time.sleep(0.15)
    u.PostMessageW(h, 0x0202, 0, lp)
    time.sleep(1.2)
log = (TMP / "DeskPet" / "logs" / "deskpet.log").read_text(encoding="utf-8", errors="replace")
hits = [l for l in log.splitlines() if "音效(" in l]
say("   日志里的音效行: %s" % hits[-3:])
check("点击触发了绑定音效 chirp.wav", any("音效(click): chirp.wav" in l for l in hits), str(hits[-1:]))
check("出场音效也走了绑定/回落", any("音效(spawn)" in l for l in hits), "")
p.terminate()
time.sleep(0.5)
subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(BASE / "tools" / "kill-all-deskpet.ps1")], stdout=subprocess.DEVNULL)
say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
(BASE / "selftest" / "report-sounds.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
