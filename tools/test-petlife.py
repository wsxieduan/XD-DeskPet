import subprocess, sys, time
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)

lines = []
lines.append("启动前 pet_running = " + str(ctl.pet_running()))
subprocess.run(["powershell", "-NoProfile", "-Command",
                "Start-Process -FilePath pythonw -ArgumentList '" + str(BASE / "deskpet.py") +
                "' -WorkingDirectory '" + str(BASE) + "'"],
               creationflags=0x08000000)
for i in range(1, 16):
    time.sleep(1.0)
    ok = ctl.pet_running()
    pid = ctl.read_pid()
    lines.append("  第 %2d 秒: pet_running=%-5s pid=%s" % (i, ok, pid))
    if not ok and i > 2:
        lines.append("  -> 她在第 %d 秒之后不见了" % i)
        break
out = subprocess.run(["powershell", "-NoProfile", "-Command",
                      "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' } | "
                      "ForEach-Object { $_.ProcessId.ToString() + ' ' + $_.Name + ' ' + $_.CommandLine }"],
                     capture_output=True, text=True, creationflags=0x08000000)
lines.append("当前 python 进程:")
for l in out.stdout.strip().splitlines():
    lines.append("   " + l)
(BASE / "selftest" / "report-petlife.txt").write_text(chr(10).join(lines), encoding="utf-8")
print("ok")
