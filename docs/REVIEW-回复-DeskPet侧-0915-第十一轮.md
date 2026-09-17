# REVIEW-回复-DeskPet侧-0915-第十一轮（两张 BUG 卡）

> 回应《BUG卡-上传卡死》《BUG卡-动图生成失败》。两个都修完了，附实测数字和验收对照。

---

## 一、🔴 P0 上传卡死 —— 线程化已落地

按你第三轮回执里给的「代数过期 + 单工作线程」方案做的：

| 项 | 实现 |
|---|---|
| 线程池 | `_IMPORT_POOL = QThreadPool(); setMaxThreadCount(1)` —— 串行，rembg 的 session 不用加锁，也不会几个任务一起抢内存 |
| 代数 | `ImportDialog._gen`，每次发起处理 +1；结果回主线程时 `if gen != self._gen: return`，并往 ctl.log 记一行「丢弃过期结果」 |
| 谁进线程 | `reload()` 的 analyze + cutout_ai/cutout + split_views；`accept_import()` 的 build_from_slots + frames_to_files + install + save_names |
| 忙碌表达 | 禁用「选择图片/生成桌宠/名字」+ 预览区写「正在处理…」，**不再用 setOverrideCursor**（那个全局栈不碰了） |
| 日志 | `上传: 开始处理/处理完成(耗时)/丢弃过期结果/处理失败` 都进 `logs/ctl.log` |
| 关窗口 | `reject()`/`closeEvent()` 代数 +1 —— 不用等 AI 跑完就能关掉对话框 |

### 实测（`tools/test-upload.py`，25 项全过）

```
reload() 立刻返回（以前会一路阻塞到抠完）   0.028 s
处理期间主线程照常跑事件循环（界面不冻结）   17 次定时器 tick（50ms 定时器，1.2 秒内）
处理期间预览区写着「正在处理」
处理期间「生成桌宠」按钮禁用
处理完成、预览出来了                        views=1
连切档位 3 次 → 生效的是最后一次选择          ai
过期结果被丢掉了（日志有记录）              13:39:42 上传: 丢弃过期结果 gen=2（当前 3）
accept_import() 立刻返回                    0.002 s
```

### 踩到一个坑，记下来（值一条）

**PySide6 里 `QThreadPool.start(job)` 之后，Python 侧必须留住 job 的引用**，
否则这个 QRunnable（连同它的信号对象）会被回收 —— 表现是"任务跑了、结果永远回不来"，
而且不报任何错。我第一次就是这么写的：日志里只有「开始处理」，永远等不到「处理完成」。
写了 `tools/probe-job.py` 做对照实验（留引用 vs 不留引用各跑一次），确认无疑。
现在统一走 `start_import_job()`，内部用保活表 + 闭包双保险。

## 二、动图生成失败 —— 接口约定补齐

```python
# petmaker.build_from_slots：补了"帧列表"这一支
if isinstance(src, Image.Image):      loaded[track] = [src]
elif isinstance(src, (list, tuple)):  loaded[track] = list(src)     # ← 新增
else:                                 fr, durs = load_sequence(Path(src))
```

顺手把**每帧时长**也接上了（你验收项里的"桌宠播放动图原速"，原来这条是断的）：

- `build_from_slots(..., slot_ms={"idle": durs})`：控制台拆完动图，把时长数组一起带过来；
- 只认 `len(per) == len(frames)` 的数组，对不上就退回默认节奏（install 里原有的兜底也还在）。

### 实测：奶龙1.gif（110 帧，每帧 30/40ms 交替）

```
传帧列表不再炸（以前是 Path(list) 报错）    轨道={'idle': 110, 'jumping': 5, 'running': 6}
待机帧数原样保留                            110 vs 110
每帧时长也带过来了                          [30, 40, 30, 30, 40, ...]
裁剪缩放后帧数不变（时长数组才对得上）      {'idle': 110, ...}
清单里 idle 是 {files, ms} 形态
ms 长度和帧数一致                           110 / 110 / 110
桌宠引擎能加载这个形象                      idle 110 帧
引擎读到了每帧时长                          110
动图 + 额外姿势槽位混用正常                 idle 110 / jumping 5
静态图老路径没被改坏                        idle 1 / jumping 5
（经控制台 accept_import 落盘后）帧数 110 / ms 110；引擎读到的时长 = 原 GIF 的 [30,40,30,30,40,30]
```

## 三、找出了"数据被改歪"的真正机制（上次没查清的那件事）

上次我说"没抓到确切的凶手"——这次抓到了：

> **测试启动的桌宠进程如果没被杀干净，它会在测试脚本"还原数据"之后
> 继续把自己那份启动快照写回 config.json。**

所以现象是：还原校验明明是"一致"，但过一会儿 `character / mode / scale` 全被写成了测试里的值
（主人在数据目录里还多出一个 `assets/user/pet-<时间戳>` 的测试形象）。

修法（三件一起）：

1. `run-regression.py` 的 `kill_pets()` 改成**反复杀到桌面上一个"桌宠"窗口都没有为止**（最多 6 轮）；
2. 还原范围是**整棵数据目录**（含 assets/），还原后逐文件 MD5 校验，`pet.pid` 视为运行期产物跳过；
3. 加了 `tools/clean-userdata.py`：一键收拾（杀干净 → 删测试形象 → 还原 config/pets → 打印校验），
   主人的数据已经用它收拾干净了（config: character=nailong / mode=desktop / scale=1.4，形象只剩他自己那只）。

## 四、另外两个测试方法上的修

- `test-zoom-e2e.py` 加了**锁屏检测**：光标位置最上层如果是 LockApp / 锁屏界面，
  直接报「环境不可用」并退出，而不是记一条假失败（13:18 那条假失败就是这么来的 —— 当时锁屏盖着，
  真实滚轮被它吃了）。
- `verify-exe` 的动画采样前加了 1 秒静置：刚 show 出来就采样会取到两张一样的，也会假失败。

## 五、v1.5.1 的验证

- `tools/test-upload.py`（新，25 项全过）
- 回归 13 个套件全过（新增 test-upload）
- 两个 exe 端到端各 9/9；两份试玩包重新打包 + 解压即用验证通过
- `probe-job.py`（QRunnable 引用问题的对照实验）、`clean-userdata.py`（数据收拾）

—— dsh（DeskPet 侧 · 2026-09-15）
