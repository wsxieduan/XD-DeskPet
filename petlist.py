r"""petlist.py —— 多桌宠实例管理

原来只有"一只桌宠"的世界观：config.json 里存 character/x/y/scale，pet.pid 存唯一进程号。
但用户发现桌面上会同时存在好几只（各自都能跑），控制台却只能管一只 —— 不如把它做成一等功能。

拆成两份数据：
  config.json  全局设置（行为开关、台词、对话配色、显示层级、音量……）—— 所有桌宠共享
  pets.json    实例列表（每只的形象 / 位置 / 大小 / 进程号）—— 每只一份

向后兼容：pets.json 不存在时，用 config.json 里原来的单宠物信息造出第一条。
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path

import paths

try:
    import msvcrt                      # Windows 文件锁（只在 Windows 上跑，这里兜个底）
except ImportError:                    # pragma: no cover
    msvcrt = None


@contextmanager
def _lock(timeout: float = 3.0):
    """给 pets.json 的"读-改-写"上个锁。

    为什么必须有：pets.json 是**多个进程**（每只桌宠 + 控制台）都会读改写的小文件。
    没有锁时会出现丢更新：A 读到旧列表 → B 写进自己的 pid → A 把手里那份旧列表写回去，
    B 的 pid 就没了。实测症状：起两只桌宠，第二只的 pid 被第一只覆盖成 null，
    控制台于是"看不见"它（关不掉、显示未启动）。"""
    if msvcrt is None:
        yield
        return
    lock = paths.data_root() / "pets.lock"
    f = open(lock, "a+")
    got = False
    t0 = time.time()
    while True:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            got = True
            break
        except OSError:
            if time.time() - t0 > timeout:
                break                  # 实在拿不到也要往下走，不能把桌宠卡死
            time.sleep(0.02)
    try:
        yield
    finally:
        if got:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        f.close()


# 形象的默认大小。奶龙的帧是 160x160 的原生尺寸（源 GIF 就这么大），
# 而用户自己传的形象会被统一到 320 高，所以它要放大一点，观感才和别人一致。
# 没列在这里的形象一律按 1.0。自 v1.5 起大小可以自由缩放（Ctrl+滚轮 / 拖右下角手柄），
# 这里只是"第一次出现时"的初值。
CHAR_SCALE = {"nailong": 1.6}


def _file() -> Path:
    return paths.data_root() / "pets.json"


def load_pets() -> list:
    f = _file()
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict) and p.get("id")]
    except Exception:
        pass
    return []


def save_pets(pets: list) -> None:
    paths.atomic_write_text(_file(), json.dumps(pets, indent=2, ensure_ascii=False))


def ensure_first() -> list:
    """首次运行（或从单宠物版本升级）：把 config.json 里那只变成 pets.json 的第一条。"""
    pets = load_pets()
    if pets:
        return pets
    try:
        cfg = json.loads(paths.config_path().read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    scr_w, scr_h = 1707, 912
    char = cfg.get("character") or paths.DEFAULT_CHARACTER
    pets = [{
        "id": "pet1",
        "character": char,
        "x": int(cfg.get("x", scr_w - 320)),
        "y": int(cfg.get("y", scr_h - 480)),
        "scale": float(cfg.get("scale", CHAR_SCALE.get(char, 1.0))),
        "pid": None,
    }]
    save_pets(pets)
    return pets


def new_id(pets: list) -> str:
    n = 1
    used = {p.get("id") for p in pets}
    while ("pet%d" % n) in used:
        n += 1
    return "pet%d" % n


def add_pet(character: str, x: int, y: int, scale: float = 1.0) -> dict:
    ensure_first()
    with _lock():
        pets = load_pets()
        p = {"id": new_id(pets), "character": character, "x": int(x), "y": int(y),
             "scale": float(scale), "pid": None, "createdAt": int(time.time())}
        pets.append(p)
        save_pets(pets)
    return p


def remove_pet(pet_id: str) -> bool:
    with _lock():
        pets = load_pets()
        keep = [p for p in pets if p.get("id") != pet_id]
        if len(keep) == len(pets):
            return False
        save_pets(keep)
    return True


def update_pet(pet_id: str, **kw) -> None:
    with _lock():
        pets = load_pets()
        for p in pets:
            if p.get("id") == pet_id:
                p.update(kw)
                break
        save_pets(pets)


def set_bond(a: str, b: str | None) -> None:
    """把 a 和 b 互设成绑定的伙伴（双向写）；b=None 表示解除 a 的绑定。

    为什么双向写：两只桌宠是独立进程，各自只读自己那一条。双向存最省事，
    也不会出现"A 认为绑定着 B，B 却不认"的半截状态。"""
    with _lock():
        pets = load_pets()
        old = None
        for p in pets:
            if p.get("id") == a:
                old = p.get("bond")
        for p in pets:
            if p.get("id") == a:
                p["bond"] = b
            elif p.get("id") == b:
                p["bond"] = a
            elif old and p.get("id") == old and old != b:
                p["bond"] = None      # 换伙伴时，旧伙伴那边也要解开
        save_pets(pets)


def get_pet(pet_id: str):
    for p in load_pets():
        if p.get("id") == pet_id:
            return p
    return None


def free_spot(index: int, win_w: int = 220, win_h: int = 380):
    """给新桌宠找一个不重叠的落点（沿屏幕右下往左上排）。"""
    s = 1707, 912
    cols = 4
    col = index % cols
    row = index // cols
    x = s[0] - win_w - 40 - col * (win_w + 20)
    y = s[1] - win_h - 60 - row * 60
    return max(6, x), max(6, y)