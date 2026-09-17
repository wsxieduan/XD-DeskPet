r"""paths.py —— 程序目录（只读）与数据目录（可写）的分离

为什么必须这么做：如果 config.json / 日志 / 用户素材都写在 exe 旁边，
用户把 exe 放进 C:\Program Files\ 之后普通权限进程没有写权限，
保存位置、生成桌宠、写日志会全部静默失败 —— 表现为"设置不生效"还查不出原因。

  APP  = 程序目录（只读）：exe / 源码 + 自带素材（内置形象、models、icon）
  DATA = 数据目录（可写）：%APPDATA%\DeskPet\（config、pet.pid、logs、assets/user、assets/bubbles）

资源查找顺序：DATA 优先，APP 兜底。新生成的东西一律写进 DATA。
"""
from __future__ import annotations

import os
import secrets
import shutil
import sys
import time
from pathlib import Path

APP_NAME = "DeskPet"

def _app_dir() -> Path:
    """exe 所在目录（用户看得见的那个地方）。开发时等于源码目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundle_dir() -> Path:
    """只读资源目录（内置素材就放这儿）。
    PyInstaller 6 的 onedir 会把 --add-data 的东西放进 _internal，也就是 sys._MEIPASS，
    不是 exe 旁边 —— 这一点搞错会导致打包后"找不到素材"。"""
    mp = getattr(sys, "_MEIPASS", None)
    if mp:
        return Path(mp)
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    """可写数据目录。

    便携模式：程序目录下放一个 portable.txt，数据就写在程序目录旁的 data/ 里
    （U 盘用户、不想碰 %APPDATA% 的用户）。
    注意：便携模式要求 exe 在可写目录里 —— 放进 Program Files 又开便携会失败，
    这时退回 %APPDATA% 并在日志里说明，而不是静默出问题。
    """
    for base in (APP, BUNDLE):
        try:
            if (base / "portable.txt").exists():
                d = base / "data"
                d.mkdir(parents=True, exist_ok=True)
                probe = d / ".write-test"
                probe.write_text("x", encoding="utf-8")
                probe.unlink()
                return d
        except Exception:
            print("[paths] portable.txt 存在但目录不可写，退回 %APPDATA%：", base, flush=True)
            break
    base = os.environ.get("APPDATA")
    if not base:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    d = Path(base) / APP_NAME
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        # 极端情况下 APPDATA 也写不了，退回程序目录，至少不崩
        d = _app_dir()
    return d


APP: Path = _app_dir()        # exe 所在目录
BUNDLE: Path = _bundle_dir()  # 内置资源目录（开发时 == APP）
DATA: Path = _data_dir()      # 可写数据目录


def _default_character() -> str:
    """随包内置的那个形象 id（必须放在 BUNDLE 之后才能求值）。

    开发/试玩包是 nailong（奶龙，149 帧，由 tools/make-nailong.py 从 GIF 生成）；
    发布包是 placeholder（纯代码画的几何小人）——
    奶龙是版权素材，不进对外发布物（阿酉第十轮 review 的发布红线）。
    打包时由 tools/build.py 往包里写一个 default.txt，运行时以它为准。

    为什么不做成"多内置形象"：内置形象是给用户开箱即用的兜底，一个就够；
    用户想要别的自己传（控制台的"上传"）。
    """
    try:
        v = (BUNDLE / "default.txt").read_text(encoding="utf-8").strip()
        if v:
            return v
    except Exception:
        pass
    return "nailong"


DEFAULT_CHARACTER = _default_character()


def data_root() -> Path:
    return DATA


def asset_roots() -> list[Path]:
    """素材根目录，按查找优先级排列：用户数据优先，内置素材兜底。"""
    roots = [DATA / "assets"]
    if BUNDLE != DATA:
        roots.append(BUNDLE / "assets")
    return roots


def find_asset(rel: str) -> Path | None:
    """按 rel（如 oc/view1/_frames.json）找资源，DATA 优先。"""
    for base in asset_roots():
        p = base / rel
        if p.exists():
            return p
    return None


def asset_root_for_write() -> Path:
    """新建素材写到这里。"""
    d = DATA / "assets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """原子写：先写同目录临时文件再 os.replace 顶替。

    为什么必须这样：桌宠（漫游时会频繁保存位置）和控制台是两个进程，无锁写同一个
    config.json。直接 write_text 的话，对方可能读到只写了一半的文件，json.loads 直接炸
    —— 测试里真的抓到了这个（JSONDecodeError: Expecting value）。
    os.replace 在同卷上是原子的：读者要么看到旧的完整内容，要么看到新的完整内容。

    临时名必须是"每进程每次调用唯一"（外部测试 BUG-1，阿酉已复核复现）：
    以前所有写者共用 config.json.tmp 这一个名字，桌宠刚 os.replace 把 tmp 移走、
    控制台还在往那个已消失的 tmp 里写 —— PermissionError 三连
    （[Errno 13] / [WinError 32] / [WinError 5]），且调用方吞了异常，
    用户只看到"设置偶尔没生效"，日志里一个字都没有。
    实测 2 进程按漫游节奏写，固定名的冲突率 0.2%~0.8%；唯一名 + 失败清理后为 0%。"""
    tmp = path.with_name("%s.%d.%s.tmp" % (path.name, os.getpid(), secrets.token_hex(4)))
    try:
        tmp.write_text(text, encoding=encoding)
        # 第二层竞争：os.replace 撞上"对方正 open() 读目标文件"会抛
        # PermissionError [WinError 5] —— CRT 的 open 不带 FILE_SHARE_DELETE，
        # rename 顶替会被拒。读方都是毫秒级瞬间，短重试就能等到它读完
        # （退避到 ~90ms，仍失败才 raise，让调用方的日志接手）。
        # 两层都堵上之后，2 进程按漫游节奏实测冲突率 0%（外部测试 BUG-1）。
        for attempt in range(8):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 7:
                    raise
                time.sleep(0.0025 * (attempt + 1))
    except Exception:
        try:
            tmp.unlink(missing_ok=True)     # 失败要清理，别给数据目录留垃圾
        except Exception:
            pass
        raise


def config_path() -> Path:
    return DATA / "config.json"


def pid_path() -> Path:
    return DATA / "pet.pid"


def log_dir() -> Path:
    d = DATA / "logs"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        d = APP
    return d


def is_lite() -> bool:
    """精简版标记（打包时放进去的 lite.txt）。用来把文案改成
    "此版本不含 AI 抠图"，而不是让用户看到"缺少 rembg"这种他看不懂的话。"""
    try:
        return (BUNDLE / "lite.txt").exists()
    except Exception:
        return False


def model_dir() -> Path:
    """随包分发的模型目录（只读）。打包后在 _internal/models，开发时在源码目录。"""
    return BUNDLE / "models"


def setup_model_env() -> None:
    """让 rembg 用随包的模型，而不是去 ~/.rembg 找、找不到就联网下 170MB。
    离线用户点一下 AI 抠图就废掉，这是不能接受的。"""
    m = model_dir()
    if m.exists():
        # rembg 的 model_dir() = <home>/models/<名字>，
        # 所以 home 要指到 models 的父目录，别指到 models 本身（踩过）
        os.environ.setdefault("U2NET_HOME", str(m.parent))
        os.environ.setdefault("REMBG_HOME", str(m.parent))


def migrate_from_app_dir() -> list[str]:
    """首次运行：把老版本散在程序目录里的数据搬到 DATA，只做一次。"""
    marker = DATA / ".migrated"
    moved: list[str] = []
    if marker.exists() or DATA == APP:
        return moved
    for name in ("config.json",):
        src, dst = APP / name, DATA / name
        try:
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)
                moved.append(name)
        except Exception:
            pass
    for sub in ("assets/user", "assets/bubbles"):
        src, dst = APP / sub, DATA / sub
        if not src.exists():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for f in src.iterdir():
            try:
                if f.is_file() and not (dst / f.name).exists():
                    shutil.copy2(f, dst / f.name)
                    moved.append(sub + "/" + f.name)
                elif f.is_dir() and not (dst / f.name).exists():
                    shutil.copytree(f, dst / f.name)      # 用户上传的形象是目录，别漏
                    moved.append(sub + "/" + f.name + "/")
            except Exception:
                pass
    try:
        marker.write_text("migrated " + str(len(moved)), encoding="utf-8")
    except Exception:
        pass
    return moved