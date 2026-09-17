# 桌宠项目审查 · 第七轮（阿酉 · 2026-09-15 10:45）—— 打包验收 + 瘦身分析

> 一句话总结：**打包这条线验收通过，`--selftest` 的端到端设计是亮点；便携模式建议加；
> Lite 版 187MB 我做了解剖，现实瘦身下限约 110~130MB，之前 60~90 的目标是我估乐观了，修正它。**

---

## 一、第六轮验收：通过 ✅

- 单 exe 双模式（main.py 分发 --pet / --selftest）、数据目录三件套（APP/BUNDLE/DATA）、
  U2NET_HOME 指向随包模型——发布约束的三件事全按蓝图落地。
- 两个坑的复盘质量很高，尤其坑 1 的教训值得写进任何 PyInstaller 教程：
  **excludes 只能砍「确定不在动态 import 链上」的包**，rembg→pymatting→numba 是运行期才展开的。
- `--selftest` 用随包真实角色图做端到端抠图验证（合成方块会被动漫模型正确拒绝——这个坑也记下了），
  这是「换机验证」的正确姿势。

## 二、回答你的问题：便携模式——建议加 ✅

`portable.txt` 方案成本一行判断，收益是 U 盘用户和「不想碰 %APPDATA%」的用户，没有副作用。
两个实现注意：
1. portable 模式下 exe 必须放在**可写目录**（用户放 Program Files 又要便携会静默失败）——
   `portable.txt` 里写一行中文说明，或者启动时检测到不可写就在日志/气泡里提示；
2. 自启快捷方式照常指向 exe 路径，不受影响。放心加。

## 三、Lite 版瘦身解剖（数据实测）

构成（_internal 实测）：**PySide6 72.3MB** / scipy+libs 38.4MB / numpy+libs 26.3MB /
Pillow 12.8MB / python313.dll 6.8MB / libcrypto 5.5MB / assets 4.4MB。

按性价比排：

| 手段 | 预期收益 | 成本 | 建议 |
|---|---|---|---|
| 1. PySide6 砍无用 Qt 模块 | **-20~30MB** | 低：spec 里排除 Qt6Pdf/Qt6Qml/Qt6Quick/Qt6Charts/Qt6Network(若未用)/translations/*.qm，只留 QtGui/QtCore/QtWidgets/qwindows/qsvg | **P0，先做** |
| 2. 开 UPX | -30~40% | 低，但杀软误报率上升——我们本来就没签名 | 折衷：只 UPX 第三方 DLL，不 UPX exe 本体 |
| 3. 弃 scipy，纯 numpy 重写 | -38MB | 中：ndimage 用到的只有 label/mean/std/dilation/erosion/fill_holes/sobel，numpy 手写可行但 label 和 flood fill 要小心性能（1600px 图上纯 Python 循环会慢，需向量化） | P2，追求极致再做 |
| 4. libcrypto 5.5MB | -5MB | 查清来源（多半是 _ssl 连带），精简版禁 _ssl | 顺手做 |

**修正后的目标**：做完 1+4 约 150MB；再上 2 约 110~120MB；3 做完逼近 80~90MB。
之前我说的 60~90MB 低估了 Python+Qt 的固定成本，抱歉——**建议把「Lite ≈ 110~120MB」定为 v1.0 的达标线**，
第 3 条留到 v1.1。

## 四、挂账提醒

- `kill_white_fringe` 改「背景色距离」判据（第二轮提的）——已挂账两轮，打包回归时一起。
- 真机验证（无 Python 电脑跑 --selftest）仍是待办，主人找台旧笔记本就行。
- 第六轮的「发布说明.md」我看过目录还没细读，推 GitHub 前我会连 main.py/paths.py 一起补一轮常规审查。

## 五、GitHub 进度同步（给主人看）

本地仓库已 init + 暂存 422 个文件（zip/模型/日志已排除），等主人账号三件套（用户名/仓库名/token）
即可推送。主人已定调：不急，先把优化做完——正好，推之前把上表的 P0 做了，简历项目更体面。

—— 阿酉 🍶（WorkBuddy 侧质检位 · 第七轮）
