"""verify-final.py —— 最终验收：壁纸层可见性 + 被盖住隐藏 + 拖拽 + 点击反馈"""
import ctypes, json, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
from PIL import Image, ImageChops, ImageGrab

BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import paths
OUT = BASE / "selftest"
lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(name, ok, detail=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok: fails.append(name)

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.mouse_event.argtypes = [wintypes.DWORD] * 5

def kill_pets():
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(BASE / "tools" / "kill-pets.ps1")],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget
app = QApplication([])
DPI = float(app.primaryScreen().devicePixelRatio())

SCALE, X, Y, W, H = 1.0, 0, 340, 211, 358
BOX = (0, int(Y * DPI) - 4, int(W * DPI) + 4, int((Y + H) * DPI) + 4)
HINT = 38   # 气泡区高度（逻辑）

def shot(box=None):
    return ImageGrab.grab(bbox=box or BOX).convert("RGB")

def cnt(a, b):
    d = ImageChops.difference(a, b)
    return sum(1 for p in d.convert("L").get_flattened_data() if p > 20)

def write_cfg(**kw):
    cfg = json.loads((paths.config_path()).read_text(encoding="utf-8"))
    cfg.update(kw)
    (paths.config_path()).write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

def pet_windows():
    """从外面看：桌宠进程到底开了哪些窗口、在哪。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
    ctl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ctl)
    pid = ctl.read_pid()
    if pid is None:
        return "pet.pid 不存在", pid
    u = ctypes.WinDLL("user32")
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u.EnumWindows.argtypes = [EnumProc, wintypes.LPARAM]
    found = []

    def cb(h, l):
        wp = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid:
            b = ctypes.create_unicode_buffer(256)
            u.GetClassNameW(h, b, 256)
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            found.append("%s rect=(%d,%d,%d,%d) 可见=%s" % (
                b.value, r.left, r.top, r.right, r.bottom, bool(u.IsWindowVisible(h))))
        return True

    u.EnumWindows(EnumProc(cb), 0)
    return ("; ".join(found) or "没找到窗口"), pid


def start():
    # 行为系统会让"点固定坐标"这条测试失效：她会自己溜达走、也会被测试用的鼠标吓跑。
    # 所以验收时先关掉行为，行为本身由 test-behavior.py 单独验。
    write_cfg(mode="desktop", character="oc/view1", scale=SCALE, sound=True, x=X, y=Y,
              behavior={"roam": False, "flee": False, "inertia": False, "recycle": False})
    lf = open(OUT / "pet-stdout.log", "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, str(BASE / "deskpet.py")], stdout=lf, stderr=subprocess.STDOUT)
    time.sleep(3.5)
    info, pid = pet_windows()
    say("   桌宠进程 pid=%s" % pid)
    say("   她的窗口: " + info)
    return p

cover = QWidget()
cover.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
cover.setStyleSheet("background:#101820")

kill_pets(); time.sleep(0.5)
A = shot()
cover.setGeometry(X - 40, Y - 40, W + 80, H + 80); cover.show(); cover.raise_()
QApplication.processEvents(); time.sleep(1.0)
A2 = shot()
cover.hide(); QApplication.processEvents(); time.sleep(0.8)
say("基线已取（DPI=%s，区域=%s）" % (DPI, BOX))
say()

p = start()
for ln in (OUT / "pet-stdout.log").read_text(encoding="utf-8", errors="replace").strip().splitlines():
    say("  日志:", ln)
say()
open_n = cnt(A, shot())
check("裸露壁纸时看得见她", open_n > 1500, "差异像素=" + str(open_n))

cover.show(); cover.raise_(); QApplication.processEvents(); time.sleep(1.2)
cov_n = cnt(A2, shot())
check("被普通窗口盖住时完全消失", cov_n == 0, "差异像素=" + str(cov_n))
cover.hide(); QApplication.processEvents(); time.sleep(1.0)

# 点击反馈：气泡区应该出现内容
bubble_box = (0, int(Y * DPI), int(W * DPI), int((Y + HINT) * DPI))
before_b = shot(bubble_box)
cx = int((X + W / 2) * DPI); cy = int((Y + H * 0.72) * DPI)
user32.SetCursorPos(cx, cy); time.sleep(0.4)
user32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.12)
user32.mouse_event(0x0004, 0, 0, 0, 0); time.sleep(0.55)
after_b = shot(bubble_box)
click_n = cnt(before_b, after_b)
check("点击后弹出气泡台词", click_n > 300, "气泡区变化像素=" + str(click_n))
shot().save(OUT / "final-click.png")
time.sleep(2.2)

# 拖拽
cfg0 = json.loads((paths.config_path()).read_text(encoding="utf-8"))
p0 = (cfg0.get("x"), cfg0.get("y"))
user32.SetCursorPos(cx, cy); time.sleep(0.4)
user32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.2)
for i in range(1, 8):
    user32.SetCursorPos(cx + int(i * 10 * DPI), cy - int(i * 4 * DPI)); time.sleep(0.09)
user32.mouse_event(0x0004, 0, 0, 0, 0); time.sleep(1.2)
cfg1 = json.loads((paths.config_path()).read_text(encoding="utf-8"))
p1 = (cfg1.get("x"), cfg1.get("y"))
check("拖拽改变位置并记住", p1 != p0, str(p0) + " -> " + str(p1))

p.terminate(); time.sleep(1.0); kill_pets()
say()
say("结果:", "全部通过" if not fails else "失败: " + ", ".join(fails))
(OUT / "report-final-verify.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
