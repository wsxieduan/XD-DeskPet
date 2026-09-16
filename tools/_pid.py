# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\petctl.py", encoding="utf-8").read()
for key in ("def read_pid", "def pet_running", "def stop_pet", "def start_pet", "def _accepted_exe_names", "def pid_alive"):
    i = s.find(key)
    print("=== %s ===" % key)
    print(s[i:i+900] if i >= 0 else "没找到")
