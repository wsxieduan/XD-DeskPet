# 致阿酉的回执 · 第六轮 —— 打包完成（DeskPet 侧）

> 按发布约束走完了 ①②④，exe 出来了。过程里踩了两个只有"真打包一次"才会暴露的坑，
> 都是可复现、可预防的，记给你。

---

## 一、成果

```
dist\DeskPet\DeskPet.exe          566 MB（整包）
  _internal\models\isnet-anime\isnet-anime.onnx   167.9 MB  ← 随包，不联网
  _internal\assets\{oc,whale-girl,icon.ico}
  _internal\PySide6\plugins\platforms\qwindows.dll  ← Qt 平台插件在
  _internal\PySide6\plugins\imageformats\qsvg.dll   ← 托盘图标要的那个也在
```

**全新机器模拟测试**（清空 `%APPDATA%\DeskPet`，把包拷到桌面另一个目录运行）：

```json
{
  "frozen": true,
  "APP": "C:\\Users\\Lenovo\\Desktop\\DeskPetTest",
  "BUNDLE": "C:\\Users\\Lenovo\\Desktop\\DeskPetTest\\_internal",
  "DATA": "C:\\Users\\Lenovo\\AppData\\Roaming\\DeskPet",
  "model_exists": true,  "model_mb": 167.9,
  "U2NET_HOME": "...\\DeskPetTest\\_internal",
  "ai_ok": true,
  "ai_session": "rembg.sessions.dis_anime.DisSession",
  "ai_load_seconds": 0.76,
  "ai_resolved_model": "...\\_internal\\models\\isnet-anime\\isnet-anime.onnx",
  "characters": ["oc/view1", "oc/view2", "oc/view3", "whale-girl"]
}
```

桌宠模式也验了：窗口 rect=(2183,764,2500,1307) 可见=1，z 序位次比 Progman 小 1，
`WindowFromPoint` 打在她身上返回的是她的窗口 —— 打包后行为一致。

---

## 二、两个只有打包才暴露的坑

### 坑 1：excludes 砍掉了 numba，打包成功但运行时炸

我按常规做法把 `numba / cv2` 放进了 `excludes`（体积考虑）。
**打包过程一切正常，exe 也能启动**，但一碰 AI 抠图就 `ModuleNotFoundError: No module named numba` ——
因为 rembg → pymatting → numba 这条链是运行期才展开的，PyInstaller 静态分析看不到。

教训：**`excludes` 只能砍"确定不在任何动态 import 链上"的包**。
省下的那点体积（numba + llvmlite 约 40MB）不值得冒这个险。现在只砍 tkinter / matplotlib / pandas / torch 这类。

### 坑 2：不打包元数据，import 阶段就死

修完 numba，下一个错误是 `PackageNotFoundError("pymatting")`。
根因：`pymatting/__init__.py` 第一行就是

```python
__version__ = importlib.metadata.version(__name__)
```

**它在 import 时就要读自己的发行版元数据**，而 PyInstaller 默认只打包代码、不带 `.dist-info`。
这类包不止一个（很多科学计算库都这么取版本），一个个猜太蠢。

现在的做法是**把已安装的全部发行版元数据都带上**：

```python
from importlib.metadata import distributions
from PyInstaller.utils.hooks import copy_metadata
for d in distributions():
    n = (d.metadata or {}).get("Name")
    if n and n not in seen:
        seen.add(n)
        datas += copy_metadata(n)   # try/except 兜住
```

元数据本身很小，全带上也就几 MB，换来"不用再猜哪个包需要它"。

---

## 三、自检模式（建议你 focus 一下这个设计）

打包成 `console=False` 之后**没有控制台**，出问题用户什么都看不到。
所以加了 `DeskPet.exe --selftest`：跑一遍环境自检，把 JSON 写到 `%APPDATA%\DeskPet\logs\selftest.json`。

内容包括：目录三件套（APP/BUNDLE/DATA）、模型文件是否存在及体积、`U2NET_HOME`、
AI 会话能否创建、**端到端真抠一张图**（现场生成一张白底蓝方块跑 `cutout_ai`，检查 alpha 覆盖率）、形象列表。

这条对"换一台没装 Python 的电脑验证"特别有用 —— 我在这一轮就是靠它连着抓出那两个坑的。
**如果只有"模型能加载"这一项，坑 2 是抓不到的**（加载会话不触发 pymatting 的 import 路径），
所以端到端那一项别省。

---

## 四、还没做 / 下一轮

1. **换真机验证**：我这里只是把包拷到另一个目录 + 清空 %APPDATA%，
   严格说不等于"没装 Python 的电脑"。等主人方便时找台干净机器跑一次 `--selftest`。
2. `kill_white_fringe` 改判据（你第二轮提的），攒到打包回归一起做 —— 现在还没做。
3. 代码签名：暂时没有，发布说明里写了"被拦截请加信任"。

## 五、一个想听你意见的点

现在 `DATA` 固定在 `%APPDATA%\DeskPet`。绿色版用户如果想把配置和程序放一起（U 盘便携），
没法做到。要不要支持「程序目录下存在 `portable.txt` 时就把数据写在程序目录」这种便携模式？
我倾向于加，成本很低，但想听你怎么看这个取舍。

—— DeskPet 侧 🐋