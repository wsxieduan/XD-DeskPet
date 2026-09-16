# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata
from importlib.metadata import distributions

datas = [('D:\\dsh\\deskpet\\build_stage\\assets', 'assets'), ('D:\\dsh\\deskpet\\build_stage\\full.txt', '.'), ('D:\\dsh\\deskpet\\build_stage\\default.txt', '.'), ('D:\\dsh\\deskpet\\build_stage\\models', 'models')]
# 很多科学计算包在 __init__ 里用 importlib.metadata.version(__name__) 读自己的版本
# （pymatting 就是），只打包代码不带元数据的话 import 阶段就 PackageNotFoundError。
# 与其一个个猜，不如把已安装的全部发行版元数据都带上 —— 元数据很小。
_seen = set()
for _d in distributions():
    _n = (_d.metadata or {}).get('Name')
    if not _n or _n in _seen:
        continue
    _seen.add(_n)
    try:
        datas += copy_metadata(_n)
    except Exception:
        pass

binaries = []
hiddenimports = collect_submodules('rembg')

_d, _b, _h = collect_all('onnxruntime')
datas += _d
binaries += _b
hiddenimports += _h

# 注意：numba / cv2 不要排除 —— rembg 的依赖链会 import 它们，
# 砍掉之后打包能成功，但运行时报 ModuleNotFoundError（自检抓到的，代价是一次重打）
excludes = ['tkinter', 'matplotlib', 'pandas', 'IPython', 'notebook', 'pytest', 'PyQt5', 'PyQt6', 'PySide2', 'torch', 'tensorflow']

a = Analysis([r'D:\dsh\deskpet\main.py'],
             pathex=[r'D:\dsh\deskpet'],
             binaries=binaries,
             datas=datas,
             hiddenimports=hiddenimports,
             excludes=excludes,
             noarchive=False)
# ——— 瘦身（第七轮 review 的 P0）———
# opengl32sw.dll 20MB：Qt 的软件 OpenGL 回退，我们纯 QWidget 绘制根本用不到
# translations/*.qm 7MB：Qt 自带界面翻译，我们的界面文案是自己写的中文
# plugins/tls：单实例用的是 QLocalSocket（本地命名管道），不走 TLS
def _keep(name):
    n = name.replace(chr(92), '/').lower()
    if n.endswith('opengl32sw.dll'):
        return False
    if '/translations/' in ('/' + n) or n.startswith('pyside6/translations'):
        return False
    if n.startswith('pyside6/plugins/tls'):
        return False
    return True

a.binaries = [x for x in a.binaries if _keep(x[0])]
a.datas = [x for x in a.datas if _keep(x[0])]

pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DeskPet',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=r'D:\dsh\deskpet\assets\icon.ico')

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DeskPet')
