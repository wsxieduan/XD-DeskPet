"""test-console.py —— 验证控制台：闪窗是否消失 + 上传对话框能否工作"""
import importlib.util, subprocess, sys, time
from pathlib import Path
from PIL import Image, ImageChops, ImageGrab

BASE = Path(r"D:/dsh/deskpet")
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)

lines = []
def say(*a): lines.append(" ".join(str(x) for x in a))
fails = []
def check(name, ok, detail=""):
    say(("  [OK]   " if ok else "  [FAIL] ") + name + ("  " + detail if detail else ""))
    if not ok: fails.append(name)

churn = BASE / "tools" / "churn.ps1"
def measure(secs):
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                          "-File", str(churn), str(secs)],
                         capture_output=True, text=True, creationflags=0x08000000)
    for tok in out.stdout.strip().split():
        if tok.isdigit():
            return int(tok)
    return -1

say("== 1. 闪窗验证：控制台跑着的时候，系统有没有在不停新建控制台 ==")
ctl.stop_pet()
subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force"],
               capture_output=True, creationflags=0x08000000)
time.sleep(1.5)
base_churn = measure(8)
say("   控制台没运行时的 conhost 变动数 =", base_churn, "（这是系统本身的背景值）")

from PySide6.QtWidgets import QApplication
app = QApplication([])
log = open(BASE / "selftest" / "ctl2.log", "w", encoding="utf-8")
p = subprocess.Popen([str(ctl.PYW), str(BASE / "petctl.py")], cwd=str(BASE),
                     stdout=log, stderr=subprocess.STDOUT, creationflags=0x08000000 | 0x00000008)
time.sleep(4.0)
run_churn = measure(8)
say("   控制台运行时的 conhost 变动数 =", run_churn)
check("控制台不再疯狂新建控制台窗口", run_churn <= base_churn + 2,
      "差值 " + str(run_churn - base_churn) + "（修复前是每秒 1 个以上）")

win_out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne '' } | "
                          "ForEach-Object { $_.MainWindowTitle }) -join ','"],
                         capture_output=True, text=True, creationflags=0x08000000)
say("   当前窗口:", win_out.stdout.strip())
check("控制台窗口在", "桌宠控制台" in win_out.stdout)

say()
say("== 2. 上传对话框（程序化测试，不点鼠标）==")
img = Path(r"D:/dsh/图片/双色发双马尾少女设定-角色-谢小端-三视图1.jpg")
dlg = ctl.ImportDialog()
dlg.path = img
dlg.ed_name.setText("测试形象")
dlg.reload()
check("对话框能完成分析+抠图", len(dlg.views) >= 1, "切出 " + str(len(dlg.views)) + " 个角色")
check("预览图已渲染", dlg.lb_preview.pixmap() is not None and not dlg.lb_preview.pixmap().isNull())
say("   信息面板内容: " + dlg.lb_info.text().replace(chr(10), " | ")[:260])

for i in range(dlg.cb_strength.count()):
    dlg.cb_strength.setCurrentIndex(i)
    dlg.reload()
    check("抠图强度 " + dlg.cb_strength.currentText()[:2] + " 能用", len(dlg.views) >= 1,
          "切出 " + str(len(dlg.views)) + " 个")

dlg.cb_motion.setCurrentIndex(1)   # 静态 + 点击有反应
dlg.cb_view.setCurrentIndex(2)
dlg.accept_import()
check("生成并安装成功", getattr(dlg, "pet_id", None) is not None, str(getattr(dlg, "pet_id", None)))
chars = [v for _, v in ctl.characters()]
check("新形象进入列表", getattr(dlg, "pet_id", "") in chars)

say()
say("结果: " + ("全部通过" if not fails else "失败: " + ", ".join(fails)))
log.close()
subprocess.run(["powershell", "-NoProfile", "-Command",
                "Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force"],
               capture_output=True, creationflags=0x08000000)
(BASE / "selftest" / "report-console.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
