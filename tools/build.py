"""build.py —— 打包成独立 exe（PyInstaller onedir）

产出一份"下载即用"的绿色版：用户解压后双击 DeskPet.exe 就能用，
不需要 Python、不需要联网下模型。

  onedir 而不是 onefile：onefile 每次启动要解压到临时目录（3~5 秒），
  桌宠是常驻程序，启动速度更重要；而且 onedir 被杀软误报的概率更低。
"""
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LITE = "--lite" in sys.argv
# --release：对外发布用。发布物里不能带版权素材（内置的奶龙），
# 换成 tools/make-placeholder.py 画出来的几何小人，并写一个 default.txt 告诉程序默认用它。
RELEASE = "--release" in sys.argv
PLACEHOLDER = "placeholder"
STAGE = BASE / ("build_stage_lite" if LITE else "build_stage")
# 目录名：开发/试玩包用 DeskPet / DeskPet-Lite（快捷方式、说明文档都按这个写）；
# 发布模式单独一个名字，免得把它跟试玩包互相覆盖。
OUT_NAME = (("DeskPet-Release-" + ("Lite" if LITE else "Full")) if RELEASE
            else ("DeskPet-Lite" if LITE else "DeskPet"))
# 目录名区分两个版本，但里面的 exe 统一叫 DeskPet.exe ——
# 说明文档、桌面快捷方式、以及"双击哪个文件"就不用分版本改了。
# （以前精简版叫 DeskPet-Lite.exe，写文档时漏改一次就会指错文件，踩过）
EXE_NAME = "DeskPet"

# 精简版砍掉整条 AI 抠图链（rembg + onnxruntime + 模型 ≈ 250MB+）。
# 抠图引导面板会把用户导向"自己出一张透明底 PNG"，这条路本来就更靠谱（见 README 第三节）。
AI_CHAIN = ["rembg", "onnxruntime", "pymatting", "numba", "llvmlite",
            "skimage", "imageio", "pooch", "tqdm"]

# 精简版额外砍掉 _ssl：它会连带 5.5MB libcrypto + 1MB libssl。
# 我们运行时不需要联网（模型随包），单实例走 QLocalSocket 不用 TLS。
# 这条有风险，所以自检里的端到端项必须留着兜底 —— 砍错了会 import 失败。
LITE_EXTRA = ["_ssl", "ssl"]

# scipy 里我们只用到 scipy.ndimage（label / fill_holes / dilation / mean / sobel），
# 其余子模块可以砍掉，省 ~40MB。砍完必须用"算法抠图"端到端验一次（自检里有）。
# 只砍确定无关的。scipy.special / scipy.sparse / scipy.linalg 不能砍 ——
# scipy.ndimage 内部会 import 它们，砍了打包能过、运行时 ModuleNotFoundError
# （自检里的"算法抠图"那项就是为这个加的，确实抓到了）。
SCIPY_TRIM = ["scipy.signal", "scipy.spatial", "scipy.interpolate", "scipy.stats",
              "scipy.io", "scipy.optimize", "scipy.fft", "scipy.cluster",
              "scipy.odr", "scipy.datasets", "scipy.differentiate", "scipy.integrate"]

# 只把"该随包分发"的东西放进去：内置形象 + 图标 + 模型。
# oc-backup（备份）、oc-src（抠好的原图）、user（主人在开发机上自己传的）都不该进发行包。
# 内置形象只有一个（奶龙，由 tools/make-nailong.py 从源 GIF 生成）。
# oc / oc-src / oc-backup / whale-girl / user 都留在源码目录里不进发行包 ——
# 发行包里的"形象"就是用户开箱看到的那一个，别的都不带。
KEEP_ASSETS = [PLACEHOLDER] if RELEASE else ["nailong"]
KEEP_FILES = ["icon.ico"]


def stage():
    if STAGE.exists():
        shutil.rmtree(STAGE)
    a = STAGE / "assets"
    a.mkdir(parents=True)
    for name in KEEP_ASSETS:
        src = BASE / "assets" / name
        if src.exists():
            shutil.copytree(src, a / name)
    for name in KEEP_FILES:
        src = BASE / "assets" / name
        if src.exists():
            shutil.copy2(src, a / name)
    if LITE:
        print("精简版：不带 AI 模型")
    else:
        m = STAGE / "models"
        m.mkdir(parents=True)
        src = BASE / "models" / "isnet-anime" / "isnet-anime.onnx"
        if src.exists():
            dst = m / "isnet-anime"
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst / "isnet-anime.onnx")
        else:
            print("!! 找不到模型:", src)
    # 打个标记，让程序自己知道这是精简版（好把文案改成"此版本不含 AI 抠图"）
    (STAGE / ("lite.txt" if LITE else "full.txt")).write_text("1", encoding="utf-8")
    # 默认形象写进包里：发布包 = placeholder（零版权风险），开发/试玩包 = nailong
    (STAGE / "default.txt").write_text(PLACEHOLDER if RELEASE else "nailong", encoding="utf-8")
    if RELEASE:
        print("★ 发布模式：内置形象 = %s（已排除版权素材 nailong）" % PLACEHOLDER)
        if not (BASE / "assets" / PLACEHOLDER).exists():
            print("!! 缺少占位形象，先跑：python tools/make-placeholder.py")
    size = sum(f.stat().st_size for f in STAGE.rglob("*") if f.is_file()) / 1024 / 1024
    print("staged %.0f MB -> %s" % (size, STAGE))


SPEC = """# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata
from importlib.metadata import distributions

datas = %DATAS%
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

%ORT%

# 注意：numba / cv2 不要排除 —— rembg 的依赖链会 import 它们，
# 砍掉之后打包能成功，但运行时报 ModuleNotFoundError（自检抓到的，代价是一次重打）
excludes = %EXCLUDES%

a = Analysis([r'%MAIN%'],
             pathex=[r'%BASE%'],
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

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='%EXENAME%',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=r'%ICON%')

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='%NAME%')
"""


def main():
    stage()
    spec = BASE / "DeskPet.spec"
    base_ex = ['tkinter', 'matplotlib', 'pandas', 'IPython', 'notebook', 'pytest',
               'PyQt5', 'PyQt6', 'PySide2', 'torch', 'tensorflow']
    tout = base_ex + AI_CHAIN + LITE_EXTRA if LITE else base_ex
    dlist = [(str(STAGE / "assets"), "assets")]
    # 版本标记必须真的进包：以前只写在 STAGE 根目录、没进 datas，
    # 结果精简版里 paths.is_lite() 永远返回 False ——
    # 界面照样给出"智能 AI"选项，点下去才报"AI 抠图组件异常"，
    # 用户看到的是"这软件坏了"，而不是"这个版本不含 AI 抠图"。
    dlist.append((str(STAGE / ("lite.txt" if LITE else "full.txt")), "."))
    dlist.append((str(STAGE / "default.txt"), "."))
    if not LITE:
        dlist.append((str(STAGE / "models"), "models"))
    NL = chr(10)
    ort = NL.join(["_d, _b, _h = collect_all('onnxruntime')",
                   "datas += _d", "binaries += _b", "hiddenimports += _h"]) if not LITE else "pass"
    if LITE:
        tout = tout + SCIPY_TRIM
    spec.write_text(
        SPEC.replace("%STAGE%", str(STAGE)).replace("%MAIN%", str(BASE / "main.py"))
            .replace("%BASE%", str(BASE)).replace("%ICON%", str(BASE / "assets" / "icon.ico"))
            .replace("%EXCLUDES%", repr(tout)).replace("%NAME%", OUT_NAME)
            .replace("%EXENAME%", EXE_NAME)
            .replace("%DATAS%", repr(dlist)).replace("%ORT%", ort),
        encoding="utf-8")
    print("spec ->", spec)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--distpath", str(BASE / "dist"), "--workpath", str(BASE / "build_pyi"),
           str(spec)]
    print("running:", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(BASE))
    out = BASE / "dist" / OUT_NAME
    if out.exists():
        size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1024 / 1024
        exe = out / (EXE_NAME + ".exe")
        print("")
        print("=" * 60)
        print("打包完成: %s" % out)
        print("体积: %.0f MB" % size)
        print("主程序: %s  存在=%s" % (exe, exe.exists()))
        print("=" * 60)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())