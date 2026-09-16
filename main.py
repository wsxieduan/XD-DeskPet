"""main.py —— 单 exe 双模式入口

用户双击 exe：进控制台（托盘 + 面板）
exe --pet    ：进桌宠本体（由控制台或开机自启拉起）

打包时不需要把 .py 当数据塞进去：两个入口都是正规模块，PyInstaller 会一起编译。
"""
from __future__ import annotations

import sys


def selftest() -> int:
    """--selftest：环境自检，把结果写成 JSON。
    打包成 windowed exe 之后没有控制台，出问题只能靠文件诊断；
    这条也是"换一台没装 Python 的电脑验证"时最省事的检查手段。"""
    import json
    import os
    import time

    import paths

    rep: dict = {"frozen": bool(getattr(sys, "frozen", False)),
                 "APP": str(paths.APP), "BUNDLE": str(paths.BUNDLE), "DATA": str(paths.DATA)}
    mf = paths.model_dir() / "isnet-anime" / "isnet-anime.onnx"
    rep["model_file"] = str(mf)
    rep["model_exists"] = mf.exists()
    rep["model_mb"] = round(mf.stat().st_size / 1048576, 1) if mf.exists() else 0
    try:
        paths.setup_model_env()
        rep["U2NET_HOME"] = os.environ.get("U2NET_HOME")
        from rembg import new_session
        t0 = time.time()
        sess = new_session("isnet-anime")
        rep["ai_ok"] = True
        rep["ai_session"] = type(sess).__module__ + "." + type(sess).__name__
        rep["ai_load_seconds"] = round(time.time() - t0, 2)
        C = type(sess)
        rep["ai_resolved_model"] = str(C.resolve_existing(C.name() + ".onnx"))
    except Exception as e:
        rep["ai_ok"] = False
        rep["ai_error"] = repr(e)
    # 端到端：真的抠一张图。只验证"模型能加载"不够 —— 用户要的是"上传图片就能出桌宠"，
    # 那就要把整条链路跑通一次。
    # 输入用**代码画出来的合成小人**（petmaker.make_test_fixture），不依赖任何随包素材：
    # 内置形象是一张不透明动图（奶龙 GIF），动漫分割模型在它上面会正确地判定
    # "整张图都是背景"，拿它当测试输入只会误报失败（实测抽 16 帧全失败）。
    # 也不能用"纯色方块"——模型同样会正确地判定"这不是角色"，这个坑踩过。
    fix = paths.log_dir() / "selftest-fixture.png"
    try:
        import petmaker
        petmaker.make_test_fixture().save(fix)
        rep["fixture"] = str(fix)
    except Exception as e:
        rep["fixture_error"] = repr(e)
    reps = []
    ok = False
    if fix.exists():
        try:
            import numpy as _np
            import petmaker
            t0 = time.time()
            res = petmaker.cutout_ai(fix, max_side=512)
            cover = float((_np.asarray(res.image)[..., 3] > 128).mean())
            reps.append({"image": "合成测试图", "seconds": round(time.time() - t0, 2),
                         "size": list(res.image.size), "alpha_ratio": round(cover, 4)})
            if cover > 0.15:
                ok = True
                rep["cutout_seconds"] = round(time.time() - t0, 2)
                rep["cutout_alpha_ratio"] = round(cover, 4)
        except Exception as e:
            reps.append({"image": "合成测试图", "error": repr(e)[:200]})
    rep["cutout_ok"] = ok
    rep["cutout_trials"] = reps
    # 精简版没有 AI 链，但"快速算法抠图"必须还能用（它依赖 scipy.ndimage）。
    # 砍 scipy 子模块时最容易把这条链砍断，所以这里单独端到端验一次。
    if not ok and fix.exists():
        try:
            import numpy as _np
            import petmaker
            t0 = time.time()
            res = petmaker.cutout(fix, "normal", max_side=512)
            cov = float((_np.asarray(res.image)[..., 3] > 128).mean())
            rep["algo_cutout_ok"] = cov > 0.15
            rep["algo_cutout_seconds"] = round(time.time() - t0, 2)
            rep["algo_cutout_alpha_ratio"] = round(cov, 4)
        except Exception as e:
            rep["algo_cutout_ok"] = False
            rep["algo_cutout_error"] = repr(e)
    try:
        chars = []
        for root in paths.asset_roots():
            if root.exists():
                for p in root.glob("**/_frames.json"):
                    chars.append(p.parent.relative_to(root).as_posix())
        rep["characters"] = sorted(set(chars))
    except Exception as e:
        rep["characters_error"] = repr(e)
    out = paths.log_dir() / "selftest.json"
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if "--pet" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--pet"]
        import deskpet
        return int(deskpet.main() or 0)
    import petctl
    return int(petctl.main() or 0)


if __name__ == "__main__":
    sys.exit(main())