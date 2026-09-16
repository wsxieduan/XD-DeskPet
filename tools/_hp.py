# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
s = io.open(r"D:\dsh\deskpet\tools\verify-exe-v14.py", encoding="utf-8").read()
print("h_pet = None 存在:", "h_pet = None" in s)
print("global h_pet 存在:", "global h_pet" in s)
print("MOUSEEVENTF 行:", [l for l in s.split(chr(10)) if "MOUSEEVENTF_LEFTDOWN" in l][:2])
print("窗口出现行:", [l for l in s.split(chr(10)) if "桌宠窗口出现" in l][:2])
