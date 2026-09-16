"""petmaker.py —— 抠图 + 生成桌宠帧的通用模块

控制台的"上传图片生成桌宠"和命令行脚本共用这一份实现。

抠图流程（针对带背景的立绘，不是简单把白色变透明）：
  1. 边框取中位数估计背景色，并评估背景干净程度
  2. 用宽松阈值得到"疑似背景"，从图像边界 flood fill 出"确定在角色外面"的区域
  3. 被角色轮廓围住的空洞逐个判断：颜色贴近背景色 -> 是夹缝，透明；否则 -> 是角色身上的浅色，保留
     （这一步是"白底没抠干净"的关键：手臂和身体之间的背景也是白的，但它不是角色的一部分）
  4. 只在外圈过渡带按到背景色的距离算 alpha，内部硬性不透明
  5. 反预乘去掉边缘混进去的背景色，再叠一层 alpha 收缩，削掉最外圈那一圈白边
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

# 强度预设：(疑似背景阈值, 硬前景阈值, alpha 收缩量, 空洞判定容差, 空洞平整度容差, 强制不透明阈值)
#   hole_tol   空洞平均色距小于它 -> 认为是被围住的背景夹缝（如两腿之间）
#   flat_tol   空洞色距标准差小于它 -> 说明这块很平整，更像背景而不是衣服
#   core_tol   只有色距大于它的像素才允许被强制设为完全不透明。这是一条兜底：
#              即使某个夹缝没被判定出来，只要它几乎就是背景色，也不会被 core 钉成白块。
#              注意别设太高：角色的浅色部分（皮肤、浅发）色距本来就不大，
#              设成 70 会把她们整片弄成半透明（实测不透明占比从 0.505 掉到 0.405）。
STRENGTHS = {
    "soft":   (48.0, 110.0, 0.00, 26.0, 20.0, 0.0),
    "normal": (60.0, 100.0, 0.10, 40.0, 30.0, 0.0),
    "strong": (76.0, 92.0,  0.22, 58.0, 42.0, 0.0),
}
TARGET_H = 320
CANVAS_GROW = (1.35, 1.30)
MAX_SIDE = 4096
MAX_FILESIZE = 24 * 1024 * 1024
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


@dataclass
class CutoutResult:
    image: Image.Image
    warnings: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)


def _border_pixels(a: np.ndarray, band: int = 3) -> np.ndarray:
    return np.concatenate([a[:band].reshape(-1, a.shape[2]), a[-band:].reshape(-1, a.shape[2]),
                           a[:, :band].reshape(-1, a.shape[2]), a[:, -band:].reshape(-1, a.shape[2])])


def analyze(path: Path) -> dict:
    """看一张图值不值得自动抠图，返回诊断信息。"""
    info = {"path": str(path), "size": None, "has_alpha": False, "alpha_ratio": 0.0,
            "bg": None, "bg_uniform": 0.0, "ok": True, "warnings": []}
    try:
        if path.stat().st_size > MAX_FILESIZE:
            info["ok"] = False
            info["warnings"].append("文件超过 24MB")
        im = Image.open(path)
    except Exception as e:
        info["ok"] = False
        info["warnings"].append("打不开：" + str(e))
        return info

    info["size"] = im.size
    if im.width > MAX_SIDE or im.height > MAX_SIDE:
        info["ok"] = False
        info["warnings"].append("尺寸超过 " + str(MAX_SIDE) + "px，请先缩小")

    rgba = im.convert("RGBA")
    al = np.asarray(rgba)[..., 3]
    info["alpha_ratio"] = float((al < 250).mean())
    info["has_alpha"] = info["alpha_ratio"] > 0.02

    if not info["has_alpha"]:
        a = np.asarray(rgba.convert("RGB")).astype(np.float32)
        border = _border_pixels(a)
        bg = np.median(border, axis=0)
        d = np.sqrt(((border - bg) ** 2).sum(axis=1))
        info["bg"] = [int(v) for v in bg]
        info["bg_uniform"] = float((d < 30).mean())
        if info["bg_uniform"] < 0.80:
            info["warnings"].append(
                "背景不干净（边框只有 %.0f%% 接近同色），自动抠图可能有残留，建议先用纯色背景的图" % (100 * info["bg_uniform"]))
    return info


def cutout(path: Path, strength: str = "normal", max_side: int = 2048) -> CutoutResult:
    t_bgish, t_fg, shrink, hole_tol, flat_tol, core_tol = STRENGTHS.get(strength, STRENGTHS["normal"])
    src = Image.open(path)
    info0 = {}
    # 桌宠最终只用 320px 高，处理前先缩到 max_side 足够，能省掉大量无谓计算
    if max(src.size) > max_side:
        k = max_side / float(max(src.size))
        src = src.resize((max(1, int(src.width * k)), max(1, int(src.height * k))), Image.LANCZOS)
        info0["downscaled_to"] = max_side
    rgba = src.convert("RGBA")
    arr = np.asarray(rgba).astype(np.float32)
    h, w, _ = arr.shape
    alpha0 = arr[..., 3]
    warnings: list[str] = []
    info: dict = {}

    # 已经有透明通道：直接用，只做裁切
    if (alpha0 < 250).mean() > 0.02:
        info["mode"] = "alpha"
        out = rgba
    else:
        info["mode"] = "matte"
        rgb = arr[..., :3]
        border = _border_pixels(rgb)
        bg = np.median(border, axis=0)
        bd = np.sqrt(((border - bg) ** 2).sum(axis=1))
        uniform = float((bd < 30).mean())
        info["bg"] = [int(v) for v in bg]
        info["bg_uniform"] = uniform
        if uniform < 0.80:
            warnings.append("背景不太干净，抠图可能留残影（可换更强的清理强度试试）")

        dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
        bgish = dist < t_bgish

        # 从四边 flood fill，得到"确定在角色外面"的区域
        seed = np.zeros((h, w), dtype=bool)
        seed[0, :] = seed[-1, :] = True
        seed[:, 0] = seed[:, -1] = True
        seed &= bgish
        lbl_bg, n_bg = ndimage.label(bgish, structure=np.ones((3, 3), dtype=int))
        outside_labels = set(np.unique(lbl_bg[seed])) - {0}
        outside = np.isin(lbl_bg, list(outside_labels)) if outside_labels else np.zeros((h, w), dtype=bool)

        # 被围住的疑似背景区域：逐个判断是夹缝还是角色身上的浅色。
        # 判据两条：颜色接近背景色（均值小）+ 这块本身很平整（标准差小）。
        # 只用均值会漏掉带一点阴影的夹缝（比如两腿之间），那正是"白底没抠干净"的来源。
        # 这里刻意不做开运算：细长的夹缝被腐蚀掉之后就再也判不出来了，改用面积下限过滤。
        holes = bgish & ~outside
        lbl_h, n_h = ndimage.label(holes, structure=np.ones((3, 3), dtype=int))
        gap_count, kept_count = 0, 0
        gap_mask = np.zeros((h, w), dtype=bool)
        if n_h:
            idx = np.arange(1, n_h + 1)
            mean_d = ndimage.mean(dist, lbl_h, index=idx)
            std_d = ndimage.standard_deviation(dist, lbl_h, index=idx)
            areas = ndimage.sum(holes, lbl_h, index=idx)
            for i in range(n_h):
                if areas[i] < 4:
                    continue
                if mean_d[i] < hole_tol and std_d[i] < flat_tol:
                    gap_mask |= (lbl_h == i + 1)
                    gap_count += 1
                else:
                    kept_count += 1
        info["gaps_transparent"] = gap_count
        info["holes_kept"] = kept_count

        fg = ~outside & ~gap_mask
        fg = ndimage.binary_fill_holes(fg)
        # 关键修复：core 只罩住"颜色明显不是背景"的像素。
        # 旧写法 core = erode(fg) 会把夹缝内部也钉成完全不透明，于是两腿之间留一块白。
        core = ndimage.binary_erosion(fg, iterations=2) & (dist >= core_tol)

        a = np.clip((dist - 6.0) / (t_fg - 6.0), 0.0, 1.0)
        a[core] = 1.0

        # 收缩最外圈：削掉残留的背景混色（白边就是这儿来的）
        if shrink > 0:
            a = np.clip((a - shrink) / (1.0 - shrink), 0.0, 1.0)
        a[~ndimage.binary_dilation(fg, iterations=2)] = 0.0

        # 反预乘：把边缘上混进来的背景色减掉
        al3 = a[..., None]
        safe = np.maximum(al3, 0.03)
        rgb2 = np.clip((rgb - bg * (1 - al3)) / safe, 0, 255)
        rgb2 = np.where(al3 > 0.03, rgb2, rgb)
        arr = np.dstack([rgb2, a * 255]).astype(np.uint8)
        out = Image.fromarray(arr, "RGBA")

    # 裁到内容包围盒
    bb = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bb is None:
        raise ValueError("这张图里找不到角色（全是背景色？）")
    pad = 4
    out = out.crop((max(0, bb[0] - pad), max(0, bb[1] - pad),
                    min(out.width, bb[2] + pad), min(out.height, bb[3] + pad)))
    info.update(info0)
    info["content"] = out.size
    info["coverage"] = float((np.asarray(out)[..., 3] > 24).mean())
    return CutoutResult(out, warnings, info)


_AI_SESSION = None
AI_MODEL = "isnet-anime"      # 动漫角色专用分割模型；通用图可换 "isnet-general-use"


def ai_status():
    """AI 抠图能不能用，返回 (可用?, 说明)。"""
    try:
        import onnxruntime  # noqa: F401
    except Exception as e:
        return False, "缺 onnxruntime：" + str(e)[:120]
    try:
        import rembg  # noqa: F401
    except Exception as e:
        return False, "缺 rembg：" + str(e)[:120]
    return True, "可用（模型 " + AI_MODEL + "）"


def _decontaminate(img: Image.Image) -> Image.Image:
    """把半透明边缘上混进来的背景色减掉（反预乘），去掉"白边"的最后一点残留。"""
    a = np.asarray(img.convert("RGBA")).astype(np.float32)
    alpha = a[..., 3] / 255.0
    rgb = a[..., :3]
    edge = (alpha > 0.02) & (alpha < 0.98)
    if edge.sum() == 0:
        return img
    border = np.concatenate([rgb[:3].reshape(-1, 3), rgb[-3:].reshape(-1, 3),
                             rgb[:, :3].reshape(-1, 3), rgb[:, -3:].reshape(-1, 3)])
    # 只用"几乎全透明"的像素来估背景色，避免把角色算进去
    flat = border[(np.concatenate([alpha[:3].ravel(), alpha[-3:].ravel(),
                                   alpha[:, :3].ravel(), alpha[:, -3:].ravel()]) < 0.05)]
    if len(flat) < 20:
        return img
    bg = np.median(flat, axis=0)
    al = alpha[..., None]
    safe = np.maximum(al, 0.05)
    fixed = (rgb - bg * (1 - al)) / safe
    out = np.where(edge[..., None], np.clip(fixed, 0, 255), rgb)
    res = np.dstack([out, a[..., 3]]).astype(np.uint8)
    return Image.fromarray(res, "RGBA")


def _estimate_bg(orig: Image.Image):
    """从原图四边估背景色（透明像素不参与）。"""
    o = np.asarray(orig.convert("RGB")).astype(np.float32)
    a = np.asarray(orig.convert("RGBA"))[..., 3].astype(np.float32) / 255.0
    edge = np.concatenate([o[:3].reshape(-1, 3), o[-3:].reshape(-1, 3),
                           o[:, :3].reshape(-1, 3), o[:, -3:].reshape(-1, 3)])
    ea = np.concatenate([a[:3].ravel(), a[-3:].ravel(), a[:, :3].ravel(), a[:, -3:].ravel()])
    opaque = edge[ea > 0.5]
    if len(opaque) < 20:
        opaque = edge
    return np.median(opaque, axis=0)


def kill_white_fringe(img: Image.Image, radius: int = 3, bg=None,
                      tol: float = 55.0) -> Image.Image:
    """把轮廓外面那一圈"发白的半透明像素"直接判成背景。

    为什么必须这么做：边缘像素的颜色 = alpha*前景 + (1-alpha)*背景。当像素本身
    几乎就是背景色时（obs≈bg），反预乘解出来的前景色也是 bg —— 数学上就还原不出
    真正的前景色。这类像素唯一的正确处理就是让它们彻底透明，否则屏幕上就是一圈白雾。

    代价：角色身上如果有纯白部分，它最外圈 radius 个像素会被削掉一点（1~3px，几乎看不出）。"""
    a = np.asarray(img.convert("RGBA")).astype(np.float32)
    al = a[..., 3] / 255.0
    solid = al > 0.78
    if solid.sum() == 0:
        return img
    ring = ndimage.binary_dilation(solid, iterations=radius) & ~solid
    rgb = a[..., :3]
    # 判据用"到背景色的距离"，而不是"泛白 + 低饱和"。
    # 为什么：泛白判据等于假设背景永远是白的 —— 黑底图上的浅色边缘会被整圈啃掉，
    # 而黑底比白底更常见。原图在手，背景色是已知量，直接用（阿酉第二轮的建议）。
    if bg is None:
        lum = rgb.mean(axis=2)
        sat = rgb.max(axis=2) - rgb.min(axis=2)
        kill = ring & (lum > 205) & (sat < 26)
    else:
        dist = np.sqrt(((rgb - np.asarray(bg, dtype=np.float32)) ** 2).sum(axis=2))
        kill = ring & (dist < tol)
    if kill.sum() == 0:
        return img
    out = a.copy()
    out[..., 3] = np.where(kill, 0.0, a[..., 3])
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def _defringe(img: Image.Image, lo: float, hi: float) -> Image.Image:
    """把 AI 那种很软的 alpha 边缘收紧：
    低于 lo 的一律当背景（否则会留一圈几乎看不见但确实存在的白雾），
    高于 hi 的当实体，中间线性过渡。配合反预乘一起用，边缘就干净了。"""
    a = np.asarray(img.convert("RGBA")).astype(np.float32)
    al = a[..., 3] / 255.0
    al = np.clip((al - lo) / max(1e-6, hi - lo), 0.0, 1.0)
    out = a.copy()
    out[..., 3] = al * 255.0
    return Image.fromarray(out.astype(np.uint8), "RGBA")


# 内部夹缝清理强度 -> 单块面积上限（占角色面积的比例）
GAP_LEVELS = {"off": 0.0, "low": 0.015, "normal": 0.04, "strong": 0.10}


def cutout_ai(path: Path, model: str = AI_MODEL, max_side: int = 1600,
              fringe: tuple[float, float] = (0.35, 0.75), gap_level: str = "normal"):
    """用 AI 分割模型抠图。背景再乱也能出干净结果，缺点是要先下模型、单张几秒到几十秒。"""
    from rembg import new_session, remove
    global _AI_SESSION
    if _AI_SESSION is None:
        _AI_SESSION = new_session(model)
    src = Image.open(path).convert("RGBA")
    work = src
    scale = 1.0
    if max(src.size) > max_side:
        scale = max_side / float(max(src.size))
        work = src.resize((max(1, int(src.width * scale)), max(1, int(src.height * scale))),
                          Image.LANCZOS)
    out = remove(work, session=_AI_SESSION, post_process_mask=True)
    if scale != 1.0:
        out = out.resize(src.size, Image.LANCZOS)
    # 顺序很重要：必须先用"模型原始的 alpha"做反预乘，再收紧边缘。
    # 反过来的话，反预乘用的 alpha 已经被改过，减背景色就减错了，白边照样留着。
    out = _decontaminate(out)
    if fringe[0] > 0 or fringe[1] < 1.0:
        out = _defringe(out, fringe[0], fringe[1])
    out = kill_white_fringe(out, bg=_estimate_bg(work))
    ratio = GAP_LEVELS.get(gap_level, GAP_LEVELS["normal"])
    if ratio > 0:
        out = clean_inner_background(out, work, max_area_ratio=ratio)
    bb = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    info = {"mode": "ai", "model": model, "resized": scale != 1.0, "fringe": fringe,
            "gap_level": gap_level}
    if bb is None:
        raise ValueError("AI 认为整张图都是背景，没找到角色")
    pad = 4
    out = out.crop((max(0, bb[0] - pad), max(0, bb[1] - pad),
                    min(out.width, bb[2] + pad), min(out.height, bb[3] + pad)))
    info["content"] = out.size
    info["coverage"] = float((np.asarray(out)[..., 3] > 24).mean())
    return CutoutResult(out, [], info)


def suitability(path: Path) -> dict:
    """给图片打个"适不适合做成桌宠"的分级，并给出具体建议。

    为什么需要它：自动抠图对"轮廓"很准，但对**被角色围住的、颜色又和背景接近的区域**
    （发丝缝、浅色毛衣、白底上的皮肤）在原理上分不开 —— 那不是算法不够好，是信息不足。
    所以正解不是硬抠，而是**在用户上传时就把这件事说清楚**，引导他给出好处理的图。

    分级：A 直接可用 / B 能出好结果 / C 会有明显瑕疵 / D 基本没法用"""
    info = analyze(path)
    if not info.get("ok", True):
        return {"grade": "D", "label": "不能用", "reasons": list(info.get("warnings", [])),
                "advice": "换一张图：格式/体积/尺寸不符合要求。", "info": info}

    reasons: list[str] = []
    advice: list[str] = []
    grade = "A"

    # 1) 自带透明通道 = 最理想，根本不需要抠图
    if info["has_alpha"]:
        info["grade"] = "A"
        return {"grade": "A", "label": "最理想（自带透明底）",
                "reasons": ["这张图已经有透明通道，直接就能用，不会有任何抠图瑕疵"],
                "advice": "什么都不用改，直接生成即可。", "info": info}

    im = Image.open(path).convert("RGB")
    k = 700 / max(im.size) if max(im.size) > 700 else 1.0
    small = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    a = np.asarray(small).astype(np.float32)
    border = _border_pixels(a)
    bg = np.median(border, axis=0)
    d = np.sqrt(((a - bg) ** 2).sum(axis=2))
    uniform = float((d.reshape(-1) < 30).mean())

    # 2) 背景干不干净
    if info["bg_uniform"] >= 0.95:
        reasons.append("背景是干净的纯色底（干净度 %.0f%%），轮廓能抠得很准" % (100 * info["bg_uniform"]))
    elif info["bg_uniform"] >= 0.75:
        grade = "B"
        reasons.append("背景比较干净（%.0f%%），轮廓没问题" % (100 * info["bg_uniform"]))
    else:
        grade = "C"
        reasons.append("背景很杂（干净度只有 %.0f%%），自动抠图容易留残影" % (100 * info["bg_uniform"]))
        advice.append("复杂背景建议先自己抠一下，或者换一张纯色/白底的图")

    # 3) 关键判据：角色自己有多少面积"颜色就接近背景"
    #    这才是"白底 + 浅色角色"的坑 —— 抠图会在发丝缝、浅色衣服、皮肤褶皱处留白块。
    #    做法：先把连到画布边缘的背景 flood fill 掉，剩下的算角色；再看角色里有多少像素
    #    颜色接近背景色。比例越高，越容易出现抠不干净的白色块。
    bgish = d < 40
    seed = np.zeros(bgish.shape, dtype=bool)
    seed[0, :] |= bgish[0, :]
    seed[-1, :] |= bgish[-1, :]
    seed[:, 0] |= bgish[:, 0]
    seed[:, -1] |= bgish[:, -1]
    lb, _ = ndimage.label(bgish, structure=np.ones((3, 3), dtype=int))
    outer = set(np.unique(lb[seed])) - {0}
    outside = np.isin(lb, list(outer)) if outer else np.zeros(bgish.shape, dtype=bool)
    body = ~outside
    body &= ~ndimage.binary_erosion(~body, iterations=1) if body.any() else body
    body_area = int(body.sum())
    if body_area > 500:
        near_ratio = float((bgish & body).sum()) / body_area
        info["near_bg_ratio"] = near_ratio
        line = "角色里有 %.0f%% 的面积颜色接近背景" % (100 * near_ratio)
        if near_ratio > 0.18:
            grade = "D" if near_ratio > 0.40 else "C"
            reasons.append(line + " —— 这是最容易留白块的一类图")
            advice.append("这种图自动抠图会在**发丝缝、浅色衣服、脖子边**留下白色块，"
                          "这是原理上分不开的（背景和角色同色，信息不足），不是参数问题")
            advice.append("最省事的办法：先用任意抠图工具（手机相册自带的都行）出一张"
                          "**透明底的 PNG** 再上传，那样一个白块都不会有")
        elif near_ratio > 0.08:
            if grade == "A":
                grade = "B"
            reasons.append(line + "，发丝缝可能留少量白块")
            advice.append("生成后先看棋盘格预览；如果发丝缝有白块，换一张透明底的 PNG 最省事")
        else:
            reasons.append(line + "，很少，基本不会留白块")

    # 4) 分辨率
    h = info["size"][1]
    if h < 300:
        grade = "C" if grade != "A" else "B"
        reasons.append("图片高度只有 %dpx，做成桌宠会糊" % h)
        advice.append("建议至少 500px 高")

    # 5) 人物有没有被裁到
    # 只有背景干净的时候，"边缘还有非背景色"才说明人物被裁到了；
    # 复杂背景的边缘本来就不是背景色，直接判断会全员误报
    edge = np.concatenate([d[0, :], d[-1, :], d[:, 0], d[:, -1]])
    if info["bg_uniform"] >= 0.90 and (edge > 60).mean() > 0.04:
        reasons.append("角色好像被画面边缘裁到了一部分")
        advice.append("换一张人物完整的图，缺胳膊少腿的话生成出来会很怪")

    if not advice:
        advice.append("直接生成就行。")
    label = {"A": "很好（推荐直接生成）", "B": "可以（结果不错）",
             "C": "勉强（会有明显瑕疵）", "D": "不建议"}[grade]
    info["grade"] = grade
    return {"grade": grade, "label": label, "reasons": reasons, "advice": advice, "info": info}


def _detail_map(orig_rgb: np.ndarray) -> np.ndarray:
    """原图的高频细节掩码（描边、五官、针织纹理、发丝都算）。
    当安全阀用：夹缝清理如果会抹掉大量细节，说明清过头了。"""
    g = orig_rgb.mean(axis=2)
    gx = ndimage.sobel(g, axis=1)
    gy = ndimage.sobel(g, axis=0)
    return np.hypot(gx, gy) > 60.0


def clean_inner_background(cut: Image.Image, orig: Image.Image,
                           tol: float = 14.0, flat: float = 22.0,
                           max_area_ratio: float = 0.04,
                           cluster_px: int = 12,
                           detail_guard: float = 0.06):
    """AI 抠完之后清掉被角色围住的背景块（发丝缝、脖子边的空隙）。

    第三版。前两版在白底加浅色角色上闯过祸（阿酉视觉验收发现豆包图的白毛衣被蛀空、
    下半张脸被清掉），原因有三，这里逐条堵上：

      1. tol 太大（30）—— 皮肤的色距约 20~40，被误判成背景。收到 14：
         真夹缝是背景直接透进来，色距通常小于 10。
      2. 面积上限防不住被纹理切碎的区域 —— 针织毛衣被切成一堆小块，每块都小于上限。
         对策：先把候选区域膨胀 cluster_px 再聚类，整簇面积超限就整簇放弃。
         真夹缝彼此离得远，膨胀后不会并成大块；纹理碎块会并成一大块而被否掉。
      3. 判据里没有这是不是角色身上东西的概念。加一道细节存活率安全阀：
         统计清理会抹掉多少原图高频细节，超过 detail_guard 就降档重试，
         仍然超标就干脆不清。宁可留白边，也不能把角色啃了。

    返回值可能是原图（一档都没通过安全阀），调用方不必特殊处理。"""
    # orig 必须和 cut 同尺寸同坐标系（所以在裁剪之前调用）
    if orig.size != cut.size:
        orig = orig.resize(cut.size, Image.LANCZOS)
    o = np.asarray(orig.convert("RGB")).astype(np.float32)
    a = np.asarray(cut.convert("RGBA")).astype(np.float32)
    alpha = a[..., 3]
    h, w = alpha.shape

    border = np.concatenate([o[:3].reshape(-1, 3), o[-3:].reshape(-1, 3),
                             o[:, :3].reshape(-1, 3), o[:, -3:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    d = np.sqrt(((o - bg) ** 2).sum(axis=2))

    solid = alpha > 128
    if solid.sum() == 0:
        return cut

    # 候选 = "被角色围住的、颜色就是背景的区域"，与 AI 的 mask 无关地重新算一遍。
    # 关键点：AI 常常把发丝缝、脖子边的空隙判成实心 —— 那样它既不是"空洞"、
    # 也不在轮廓边缘，前两版逻辑就这么漏掉了（实测只能清掉 1.5%）。
    bgish = d < tol
    seed = np.zeros((h, w), dtype=bool)
    seed[0, :] |= bgish[0, :]
    seed[-1, :] |= bgish[-1, :]
    seed[:, 0] |= bgish[:, 0]
    seed[:, -1] |= bgish[:, -1]
    lbl_bg, _ = ndimage.label(bgish, structure=np.ones((3, 3), dtype=int))
    outer = set(np.unique(lbl_bg[seed])) - {0}
    outside = np.isin(lbl_bg, list(outer)) if outer else np.zeros((h, w), dtype=bool)
    cand = bgish & ~outside

    if not cand.any():
        return cut
    detail = _detail_map(o)
    total_detail = max(1, int((detail & solid).sum()))

    # 逐级降档重试，任何一档的细节损失超标就往下退，全都不安全就不清。
    for ratio in (max_area_ratio, max_area_ratio * 0.4, max_area_ratio * 0.15):
        kill = _select_gaps(cand, d, tol=tol, flat=flat,
                            limit=ratio * float(solid.sum()), cluster_px=cluster_px)
        if not kill.any():
            continue
        if int((detail & kill).sum()) / total_detail <= detail_guard:
            out = a.copy()
            out[..., 3] = np.where(kill, 0.0, alpha)
            return Image.fromarray(out.astype(np.uint8), "RGBA")
    return cut


def _select_gaps(cand: np.ndarray, d: np.ndarray, tol: float, flat: float,
                 limit: float, cluster_px: int) -> np.ndarray:
    """从候选里挑真夹缝。

    先用膨胀聚类否掉纹理碎块 —— 它们膨胀后会并成一大块、超过 limit，
    而真夹缝彼此离得远，膨胀后仍然是独立小块。"""
    lbl, n = ndimage.label(cand, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return np.zeros(cand.shape, dtype=bool)

    grown = ndimage.binary_dilation(cand, iterations=cluster_px,
                                    structure=np.ones((3, 3), dtype=int))
    glbl, gn = ndimage.label(grown, structure=np.ones((3, 3), dtype=int))
    garea = ndimage.sum(grown, glbl, index=np.arange(1, gn + 1))
    cluster_of = glbl[cand]
    bad = set(np.where(garea > limit)[0] + 1)

    idx = np.arange(1, n + 1)
    areas = ndimage.sum(cand, lbl, index=idx)
    mean_d = ndimage.mean(d, lbl, index=idx)
    std_d = ndimage.standard_deviation(d, lbl, index=idx)

    kill = np.zeros(cand.shape, dtype=bool)
    for i in range(n):
        if areas[i] < 3 or cluster_of[i] in bad:
            continue
        if mean_d[i] < tol and std_d[i] < flat:
            kill |= (lbl == i + 1)
    return kill


def split_views(img: Image.Image, count: int = 3, min_area: int = 40, band: int = 70):
    """把一张角色设定图切成 count 个视图（按 x 从左到右）。

    取面积最大的 count 块当锚点，其余碎块只有在 bbox 完整落进某个锚点带里时才收编，
    避免横跨两个视图的杂质被拉进来。返回 [PIL 图, ...]。"""
    a = np.asarray(img.convert("RGBA"))[..., 3]
    solid = a > 24
    lbl, n = ndimage.label(solid, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return []
    sizes = ndimage.sum(solid, lbl, index=np.arange(1, n + 1))
    boxes = {}
    for k in range(1, n + 1):
        ys, xs = np.where(lbl == k)
        boxes[k] = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    anchors = sorted(sorted(range(1, n + 1), key=lambda k: -sizes[k - 1])[:count],
                     key=lambda k: boxes[k][0])
    out = []
    for anchor in anchors:
        x0, y0, x1, y1 = boxes[anchor]
        m = (lbl == anchor)
        for k in range(1, n + 1):
            if k == anchor or sizes[k - 1] < min_area:
                continue
            bx0, by0, bx1, by1 = boxes[k]
            if x0 - band <= bx0 and bx1 <= x1 + band and y0 - band <= by0 and by1 <= y1 + band:
                m |= (lbl == k)
        ys, xs = np.where(m)
        pad = 6
        out.append(img.crop((max(0, xs.min() - pad), max(0, ys.min() - pad),
                             min(img.width, xs.max() + pad), min(img.height, ys.max() + pad))))
    return out


def halo_score(img: Image.Image, want_band: bool = False):
    """粗略的"白边"指标：紧贴轮廓外侧那一圈像素里有多少是发白的。越低越好。
    want_band=True 时一并返回该圈的像素数（用来确认指标不是"没样本所以是 0"）。"""
    a = np.asarray(img.convert("RGBA")).astype(np.float32)
    al = a[..., 3]
    if al.max() == 0:
        return 0.0
    solid = al > 200
    band = ndimage.binary_dilation(solid, iterations=2) & ~solid & (al > 12)
    if band.sum() == 0:
        return (0.0, 0) if want_band else 0.0
    px = a[band][:, :3]
    lum = px.mean(axis=1)
    sat = px.max(axis=1) - px.min(axis=1)
    whitish = (lum > 205) & (sat < 26)
    score = float(whitish.mean())
    return (score, int(band.sum())) if want_band else score


# ------------------------------------------------------------------ 生成动画
def _pivot_of(img: Image.Image) -> tuple[float, float]:
    bb = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return ((bb[0] + bb[2]) / 2.0, float(bb[3]))


def _warped(img, pivot, sx, sy, angle, dx, dy, canvas):
    nw, nh = max(1, int(round(img.width * sx))), max(1, int(round(img.height * sy)))
    im = img.resize((nw, nh), Image.LANCZOS)
    px, py = pivot[0] * sx, pivot[1] * sy
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, center=(px, py), expand=False)
    out = Image.new("RGBA", canvas, (0, 0, 0, 0))
    out.alpha_composite(im, (int(round(canvas[0] / 2.0 - px + dx)),
                             int(round(canvas[1] - py + dy))))
    return out


def make_frames(img: Image.Image, mode: str = "full") -> dict[str, list[Image.Image]]:
    """三种档位，都由同一张图程序化生成，不需要你画多张：
      still    只有一帧，完全不动
      reactive 待机不动，但点击时压扁回弹一下（2 条轨道）
      full     待机浮动呼吸 + 点击跳跃 + 拖拽摇摆（3 条轨道）"""
    pivot = _pivot_of(img)
    units = float(img.height)
    canvas = (int(img.width * CANVAS_GROW[0]), int(img.height * CANVAS_GROW[1]))

    if mode == "still":
        return {"idle": [img]}

    if mode == "reactive":
        press = []
        for sx, sy in ((1.07, 0.92), (0.96, 1.05), (1.0, 1.0), (1.03, 0.97), (1.0, 1.0)):
            press.append(_warped(img, pivot, sx, sy, 0, 0, 0, canvas))
        return {"idle": [img], "jumping": press}

    idle, jump, sway = [], [], []
    for i in range(8):
        t = i / 8.0 * 2 * math.pi
        dy = -0.016 * units * (1 - math.cos(t)) / 2
        br = 0.010 * math.sin(t)
        idle.append(_warped(img, pivot, 1.0 + br, 1.0 - br, 0, 0, dy, canvas))
    for sx, sy, dy in ((1.06, 0.93, 0.000), (0.97, 1.05, -0.040), (0.99, 1.02, -0.095),
                       (1.00, 1.00, -0.115), (0.98, 1.02, -0.070), (1.08, 0.90, 0.000),
                       (0.99, 1.02, -0.010)):
        jump.append(_warped(img, pivot, sx, sy, 0, 0, dy * units, canvas))
    for i in range(6):
        t = i / 6.0 * 2 * math.pi
        sway.append(_warped(img, pivot, 1.0, 1.0, 4.5 * math.sin(t), 0,
                            -0.006 * units * abs(math.sin(t)), canvas))
    return {"idle": idle, "jumping": jump, "running": sway}


def frames_to_files(tracks: dict, target_h: int = TARGET_H):
    """统一裁到同一包围盒并按目标高度缩放，返回 {轨道: [PIL图]} 与最终尺寸。"""
    x0 = y0 = 10 ** 9
    x1 = y1 = -1
    for frames in tracks.values():
        for f in frames:
            bb = f.getchannel("A").point(lambda v: 255 if v > 6 else 0).getbbox()
            if bb:
                x0, y0 = min(x0, bb[0]), min(y0, bb[1])
                x1, y1 = max(x1, bb[2]), max(y1, bb[3])
    if x1 < 0:
        raise ValueError("生成的帧是空的")
    w0, h0 = x1 - x0, y1 - y0
    mx, myt, myb = int(w0 * 0.035), int(h0 * 0.030), int(h0 * 0.015)
    fw, fh = tracks[list(tracks)[0]][0].size
    x0, y0 = max(0, x0 - mx), max(0, y0 - myt)
    x1, y1 = min(fw, x1 + mx), min(fh, y1 + myb)
    scale = target_h / float(y1 - y0)
    out = {}
    for track, frames in tracks.items():
        out[track] = [f.crop((x0, y0, x1, y1)).resize(
            (max(1, int(round((x1 - x0) * scale))), max(1, int(round((y1 - y0) * scale)))),
            Image.LANCZOS) for f in frames]
    return out


# ------------------------------------------------------------------ 动图 / 多姿势
def load_sequence(path: Path, max_side: int = 1200):
    """把一张图读成"帧序列"。动图（GIF / APNG / 动态 WebP）会返回全部帧和每帧时长，
    静态图返回单帧。

    这是从 dsh-whale-widget 0.3.0 学来的方向：它支持上传 GIF/APNG 当角色。
    对桌宠来说这条路特别值 —— **动画贴纸通常本来就是透明底**，
    既不需要抠图（那套启发式在浅色角色上本来就不可靠），又能直接得到真正的动态。
    返回 (frames, durations_ms 或 None)。"""
    im = Image.open(path)
    frames = []
    durations = []
    n = getattr(im, "n_frames", 1)
    for i in range(n):
        try:
            im.seek(i)
        except EOFError:
            break
        fr = im.convert("RGBA").copy()
        frames.append(fr)
        durations.append(int(im.info.get("duration", 0) or 0))
    if len(frames) <= 1:
        single = im.convert("RGBA")
        if max(single.size) > max_side:
            k = max_side / float(max(single.size))
            single = single.resize((max(1, int(single.width * k)),
                                    max(1, int(single.height * k))), Image.LANCZOS)
        return [single], None

    # 动图：所有帧统一缩放到同一尺寸（有些 GIF 帧尺寸不一致）
    w = max(f.width for f in frames)
    h = max(f.height for f in frames)
    k = min(1.0, max_side / float(max(w, h)))
    out = []
    for f in frames:
        if f.size != (w, h):
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            canvas.paste(f, ((w - f.width) // 2, (h - f.height) // 2), f)
            f = canvas
        if k < 1.0:
            f = f.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)
        out.append(f)
    # 时长兜底：GIF 里常见 duration=0，按 100ms 处理
    durs = [d if 16 <= d <= 5000 else 100 for d in durations]
    return out, durs


def align_frames(frames, size=None):
    """把一组帧对齐到同一画布（动图各帧尺寸不一致时用）。"""
    if not frames:
        return frames
    w = size[0] if size else max(f.width for f in frames)
    h = size[1] if size else max(f.height for f in frames)
    out = []
    for f in frames:
        if f.size == (w, h):
            out.append(f)
            continue
        c = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        c.paste(f, ((w - f.width) // 2, (h - f.height) // 2), f)
        out.append(c)
    return out


def build_from_slots(slots: dict, mode: str = "full", fallback_image=None,
                     slot_ms: dict | None = None):
    """按"每类动作给一张图（可以是动图）"生成完整轨道。

    slots: {"idle": Path | PIL图 | 帧列表 | None, "jumping": ..., "running": ...}
      · Path    —— 图或动图文件（内部自己拆帧）
      · PIL图   —— 单帧
      · 帧列表  —— 调用方已经拆好的帧（控制台为了不卡界面，自己在别处拆的）
    slot_ms: {"idle": [每帧毫秒, ...]}，和帧列表配套；只认长度对得上的数组。
    没给的轨道就用 idle 那张图程序化生成（现有做法）。
    返回 (tracks, ms) —— ms[track] 是每帧时长数组，None 表示用默认节奏。"""
    loaded = {}
    ms = {}
    for track in ("idle", "jumping", "running"):
        src = slots.get(track)
        if src is None:
            continue
        if isinstance(src, Image.Image):
            loaded[track] = [src]
        elif isinstance(src, (list, tuple)):
            # 已经是帧列表：控制台拆动图时走的这条。
            # 以前这里只有 Path / Image 两个分支，传列表进来会在 Path(list) 直接炸 ——
            # "argument should be a str or an os.PathLike object ... not 'list'"
            # （阿酉 BUG 卡 · 主人实测上传动图时报的就是这个）
            loaded[track] = list(src)
            per = (slot_ms or {}).get(track)
            if per and len(per) == len(src):
                ms[track] = [int(x) for x in per]
        else:
            fr, durs = load_sequence(Path(src))
            loaded[track] = fr
            if durs:
                ms[track] = durs

    if "idle" not in loaded:
        if fallback_image is None:
            raise ValueError("至少要有一张待机图")
        loaded["idle"] = [fallback_image]

    # 各轨道的帧尺寸可能不同，统一到 idle 的尺寸再交给后续流程
    base = loaded["idle"][0]
    for k in list(loaded.keys()):
        loaded[k] = align_frames(loaded[k], base.size)

    tracks = {}
    tracks["idle"] = loaded["idle"]

    for track in ("jumping", "running"):
        if track in loaded and len(loaded[track]) > 1:
            # 用户给了动图 —— 直接用它，别再程序化生成
            tracks[track] = loaded[track]
        else:
            # 静态图（或没给）：用程序化生成把这张图变成动画
            one = loaded.get(track, [base])[0]
            gen = make_frames(one, "reactive" if track == "jumping" else "full")
            tracks[track] = gen.get(track, gen.get("jumping", [base]))

    if mode == "still":
        tracks = {"idle": tracks["idle"][:1]}
        ms = {}
    elif mode == "reactive":
        tracks.pop("running", None)
    return tracks, ms


def install(assets_root: Path, pet_id: str, tracks: dict, ms: dict | None = None,
            gray_preview: bool = False) -> dict:
    """把帧写进 assets/user/<pet_id>/ 并生成 _frames.json。"""
    import re
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", pet_id):
        raise ValueError("形象 id 只能用小写字母、数字和短横线，1-32 位")
    d = assets_root / "user" / pet_id
    d.mkdir(parents=True, exist_ok=True)
    for old in d.glob("*.png"):
        old.unlink()
    manifest = {}
    for track, frames in tracks.items():
        names = []
        for i, f in enumerate(frames, 1):
            name = "%s-%d.png" % (track, i)
            f.save(d / name)
            names.append(name)
        # 有自定义节奏（动图带来的每帧时长）就写成 {"files":[...],"ms":[...]}，
        # 没有就还是老格式（纯文件名数组）—— 老素材不用迁移。
        per = (ms or {}).get(track)
        if per and len(per) == len(names):
            manifest[track] = {"files": names, "ms": [int(x) for x in per]}
        else:
            manifest[track] = names
    (d / "_frames.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# ------------------------------------------------------------------ 自检用的合成测试图
def make_test_fixture(size: int = 512) -> Image.Image:
    """画一个"合成小人"，给 --selftest 验证抠图链路用。

    为什么不用随包形象当测试输入：内置形象是一张**不透明**的动图（奶龙 GIF），
    动漫分割模型在它上面会正确地判定"整张图都是背景"，自检就会误报失败。
    而合成人物既不需要随包多带一张图，模型也确实认（实测 AI 抠图 alpha 占比 0.57）。
    """
    from PIL import ImageDraw
    im = Image.new("RGB", (size, size), (176, 214, 240))       # 天蓝底
    d = ImageDraw.Draw(im)
    cx = size // 2
    d.rounded_rectangle([cx - 92, 250, cx + 92, 430], radius=40, fill=(240, 240, 245),
                        outline=(60, 50, 60), width=7)                       # 身体
    d.line([(cx - 92, 290), (cx - 150, 350)], fill=(240, 240, 245), width=34)  # 手臂
    d.line([(cx + 92, 290), (cx + 150, 350)], fill=(240, 240, 245), width=34)
    d.line([(cx - 45, 425), (cx - 45, 480)], fill=(60, 50, 60), width=30)      # 腿
    d.line([(cx + 45, 425), (cx + 45, 480)], fill=(60, 50, 60), width=30)
    d.ellipse([cx - 105, 70, cx + 105, 280], fill=(252, 226, 206),
              outline=(60, 50, 60), width=7)                                # 脸
    d.chord([cx - 112, 58, cx + 112, 250], 180, 360, fill=(86, 60, 110),
            outline=(60, 50, 60), width=6)                                  # 头发
    d.ellipse([cx - 128, 150, cx - 88, 260], fill=(86, 60, 110))
    d.ellipse([cx + 88, 150, cx + 128, 260], fill=(86, 60, 110))
    d.ellipse([cx - 62, 170, cx - 30, 220], fill=(40, 36, 48))                # 眼睛
    d.ellipse([cx + 30, 170, cx + 62, 220], fill=(40, 36, 48))
    d.ellipse([cx - 54, 178, cx - 42, 192], fill=(255, 255, 255))
    d.ellipse([cx + 38, 178, cx + 50, 192], fill=(255, 255, 255))
    d.ellipse([cx - 88, 214, cx - 60, 236], fill=(250, 190, 190))             # 腮红
    d.ellipse([cx + 60, 214, cx + 88, 236], fill=(250, 190, 190))
    d.arc([cx - 22, 218, cx + 22, 250], 20, 160, fill=(60, 50, 60), width=5)  # 嘴
    return im
