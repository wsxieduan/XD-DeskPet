import importlib.util, subprocess, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
lines = []
lines.append("初始 autostart = " + str(ctl.autostart_on()))
ctl.set_autostart(True)
time.sleep(1.0)
lnk = ctl.startup_dir() / "deskpet.lnk"
lines.append("创建后 autostart = " + str(ctl.autostart_on()))
out = subprocess.run(["powershell", "-NoProfile", "-Command",
                      "$ws=New-Object -ComObject WScript.Shell;"
                      "$l=$ws.CreateShortcut('" + str(lnk) + "');"
                      "Write-Output ($l.TargetPath + ' || ' + $l.Arguments)"],
                     capture_output=True, text=True, creationflags=0x08000000)
lines.append("快捷方式指向 = " + out.stdout.strip())
ok = "petctl.py" in out.stdout and "--autostart" in out.stdout and "pythonw" in out.stdout.lower()
lines.append("检查通过 = " + str(ok))
ctl.set_autostart(False)
time.sleep(0.6)
lines.append("清理后 autostart = " + str(ctl.autostart_on()))
(BASE / "selftest" / "report-autostart.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
