# -*- coding: utf-8 -*-
import os, shutil, sys, json
from pathlib import Path
BASE = Path(r"D:/dsh/deskpet")
sys.path.insert(0, str(BASE))
TMP = BASE / "selftest" / "appdata-dbg"
if TMP.exists():
    shutil.rmtree(TMP, ignore_errors=True)
(TMP / "DeskPet").mkdir(parents=True)
os.environ["APPDATA"] = str(TMP)
sys.stdout.reconfigure(encoding="utf-8")
import paths, petlist
print("paths.DATA      =", paths.DATA)
print("paths.BUNDLE    =", paths.BUNDLE)
print("asset_roots     =", paths.asset_roots())
print("petlist._file() =", petlist._file(), petlist._file().exists())
print("config_path     =", paths.config_path(), paths.config_path().exists())
print("pets in data    =", petlist.load_pets())
import importlib.util
spec = importlib.util.spec_from_file_location("petctl", BASE / "petctl.py")
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)
print("ctl.ASSETS      =", ctl.ASSETS)
print("ctl.NAMES       =", ctl.NAMES, ctl.NAMES.exists())
print("ctl.DATA_DIR    =", getattr(ctl, "DATA_DIR", "无"))
print("ctl.BASE        =", ctl.BASE)
