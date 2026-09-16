# -*- coding: utf-8 -*-
r"""make-kit.py —— 打"给朋友品鉴"的包

产物 = 程序本体 + 三份给人看的文档：
  1-先看我-30秒上手.txt   （最短的上手 + 想让他重点试什么）
  2-产品介绍.txt          （这东西是什么、亮点、两个版本怎么选）
  3-使用说明书.txt        （完整说明书：每个功能怎么用、常见问题、出问题怎么查）
文档由仓库根目录的 产品介绍.md / 使用说明书.md 转过来（带 BOM 的 UTF-8，记事本直接能看）。

数据目录默认是**便携模式**：写在解压目录的 data\ 里，测完删文件夹就干净，
有异常让他把 data\logs 发回来即可。

用法：
  python tools/make-kit.py --lite
  python tools/make-kit.py --full
"""
import io, os, shutil, sys, zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
VER = "v1.6"
LITE = "--lite" in sys.argv
SRC = BASE / "dist" / ("DeskPet-Lite" if LITE else "DeskPet")
KITNAME = "DeskPet-%s-%s" % ("精简版" if LITE else "完整版", VER)
OUTDIR = BASE / "dist-kit"


def _tpl(s: str) -> str:
    return s.replace("{VER}", VER)


SHORT_LITE = r"""桌宠 DeskPet 精简版 {VER} —— 先看我（30 秒上手）

【它是什么】
贴在 Windows 桌面上的小桌宠。不用装 Python、不用联网，解压就能用。
默认"只贴在壁纸上"：被窗口盖住就自动消失，把窗口挪开又露出来 —— 这是故意的，不是 bug。

【三步开始】
1) 把整个文件夹解压出来（别只拖 DeskPet.exe 出来，旁边的 _internal 要一起）。
2) 双击 DeskPet.exe  →  出现的小窗口叫「桌宠控制台」。
3) 点最下面蓝色的「＋ 召唤一个桌宠」。她会出现屏幕右侧。
   关掉控制台窗口 = 收进右下角托盘；双击托盘图标再打开。

【想让你重点帮我试这几件事】
1. 点她一下：应该冒出台词气泡 + 有一声"叮"的音效。
2. 拖她：能拖到别处，松手还会往前滑一小段（惯性）。
3. 鼠标放到她身上，按住 Ctrl 滚滚轮：她会变大变小，而且**脚底不动**（往上长）。
4. 右键她 →「调整大小」→ 拖右下角那个小方块，也是一样的效果。
5. 用浏览器窗口盖住她再挪开：应该"被盖住 / 又露出来"。
6. 控制台里「显示层级」切到"始终置顶"：她应该浮在所有窗口上面；再切回来。
7. 召唤**两只**，在「伴侣」里互相选上，点「一起转圈」：
   两只应该围着同一个圆心一左一右转 20 秒（转速可选「魔性」，还能整只翻过来）。
8. 控制台展开「互动音效」：给"点击"绑一个你自己的 WAV，再点她试试（只支持 WAV）。
9. 想换形象：控制台「＋ 上传」，传一张图或者一个 GIF 试试。

   这个精简版**不含 AI 抠图**（上传静态图走"快速算法"，纯色背景效果最好）。
   想试 AI 抠图请用完整版那个包。

【出问题怎么办】
· 把整个文件夹里的 data\logs 目录打包发我就行（里面有日志，不含隐私）。
· 杀毒软件可能报警（程序没做数字签名），选"允许/信任"。
· 想彻底删掉：托盘右键退出 → 删掉整个文件夹（数据都在解压目录的 data\ 里）。

【详细说明】
看同目录的《2-产品介绍》和《3-使用说明书》。
"""

SHORT_FULL = r"""桌宠 DeskPet 完整版 {VER} —— 先看我（30 秒上手）

【它是什么】
贴在 Windows 桌面上的小桌宠。不用装 Python、不用联网，解压就能用。
默认"只贴在壁纸上"：被窗口盖住就自动消失，把窗口挪开又露出来 —— 这是故意的，不是 bug。

这个版本比精简版多带了 **AI 抠图模型**（约 168MB），所以体积大不少 ——
好处是**上传任何照片/插画**（背景再乱）都能抠出干净的角色。

【三步开始】
1) 把整个文件夹解压出来（别只拖 DeskPet.exe 出来，旁边的 _internal 要一起）。
   解压后文件夹比较大（约 540MB），慢是正常的。
2) 双击 DeskPet.exe  →  出现的小窗口叫「桌宠控制台」。
3) 点最下面蓝色的「＋ 召唤一个桌宠」。她会出现屏幕右侧。
   关掉控制台窗口 = 收进右下角托盘；双击托盘图标再打开。

【想让你重点帮我试这几件事】
1. 点她一下：应该冒出台词气泡 + 有一声"叮"的音效。
2. 拖她：能拖到别处，松手还会往前滑一小段（惯性）。
3. 鼠标放到她身上，按住 Ctrl 滚滚轮：她会变大变小，而且**脚底不动**（往上长）。
4. 用浏览器窗口盖住她再挪开：应该"被盖住 / 又露出来"。
5. **重点：上传一张真人照片或插画**（控制台「＋ 上传」→ 抠图方式选「智能 AI」）。
   第一次会加载模型，等几十秒是正常的；界面不会卡，预览是棋盘格底，白边一眼能看出来。
   如果某张图本来就不好抠（角色和背景颜色太接近），把抠图方式改成「不抠图」直接用原图也可以。
6. 传一个 **GIF 动图**试试 —— 会直接拿它的帧当动画，**按原速播**，效果最好。
7. 召唤**两只**，在「伴侣」里互相选上，点「一起转圈」：
   两只应该围着同一个圆心一左一右转 20 秒（转速可选「魔性」，还能整只翻过来）。
8. 控制台展开「互动音效」：给"点击"绑一个你自己的 WAV，再点她试试（只支持 WAV）。

【出问题怎么办】
· 把整个文件夹里的 data\logs 目录打包发我就行（里面有日志，不含隐私）。
· 杀毒软件可能报警（程序没做数字签名），选"允许/信任"。
· 想彻底删掉：托盘右键退出 → 删掉整个文件夹（数据都在解压目录的 data\ 里）。

【详细说明】
看同目录的《2-产品介绍》和《3-使用说明书》。
"""


def write_text(path: Path, text: str) -> None:
    # 带 BOM 的 UTF-8：Windows 记事本双击打开不会乱码（老版本记事本对无 BOM 的中文会猜错编码）
    io.open(path, "w", encoding="utf-8-sig").write(text)


def main():
    if not SRC.exists():
        print("!! 找不到 %s，先跑 tools/build.py %s" % (SRC, "--lite" if LITE else ""))
        return 1
    OUTDIR.mkdir(exist_ok=True)
    stage = OUTDIR / KITNAME
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    app = stage / "DeskPet"
    shutil.copytree(SRC, app)
    write_text(app / "portable.txt",
               "便携模式：数据写在同目录的 data\\ 里（把这一行删掉就改回写 %APPDATA%）。\n")
    write_text(stage / "1-先看我-30秒上手.txt", _tpl(SHORT_LITE if LITE else SHORT_FULL))
    for src_name, dst_name in (("产品介绍.md", "2-产品介绍.txt"),
                               ("使用说明书.md", "3-使用说明书.txt")):
        src = BASE / src_name
        if src.exists():
            write_text(stage / dst_name, src.read_text(encoding="utf-8"))
        else:
            print("!! 缺 %s（文档没生成）" % src_name)
    zpath = OUTDIR / (KITNAME + ".zip")
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(stage):
            for f in files:
                p = Path(root) / f
                z.write(p, p.relative_to(OUTDIR))
    total = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file()) / 1048576.0
    print("试玩包目录: %s  (%.0f MB)" % (stage, total))
    print("zip: %s  (%.0f MB)" % (zpath, zpath.stat().st_size / 1048576.0))
    return 0


sys.exit(main())
