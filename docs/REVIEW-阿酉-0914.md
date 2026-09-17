# 桌宠项目代码审查报告（阿酉 · 2026-09-14 18:50）

> 审查范围：deskpet.py / petctl.pyw / petmaker.py 全量源码（当时最新版本）。
> 分级：🔴 必须修（当前会出错） / 🟡 建议修（有隐患或体验问题） / 🟢 观察项（不改也能跑）。
> 每条都给了文件和行号，方便直接定位。

---

## 🔴 P0-1 pythonw 下 print 会让 apply_layer 断裂（deskpet.py 约 527 行）

**现象**：控制台启动桌宠用的是 `pythonw.exe`（petctl.pyw 里 `PYW` 变量），pythonw 下 `sys.stdout` 是 `None`。
`apply_layer()` 里的这句：

```python
print("layer: hwnd=%d class=%s exstyle=0x%x" % (...), flush=True)
```

会抛 `AttributeError: 'NoneType' object has no attribute 'write'`。这个异常发生在
`QTimer.singleShot(80, self.apply_layer)` 的回调里，**print 之后的代码全部不会执行**——
也就是 `push_to_bottom()` 和 `bottom_timer` 都没启动，壁纸层模式直接失效。

**为什么之前没发现**：用 `调试启动.bat`（python.exe）跑或手动验证时 stdout 存在，一切正常；
只有走控制台启动链（pythonw）才触发。

**修复（三选一）**：
```python
# 方案 A：直接删掉这行调试输出（推荐）
# 方案 B：包一层
if sys.stdout:
    print(...)
# 方案 C：写成通用安全输出
def log(*a): 
    try:
        print(*a, flush=True)
    except Exception:
        pass
```

**验证方法**：控制台点「显示桌宠」→ 桌宠应该沉到壁纸层（Win+D 能看到）；右键切「始终置顶」→ 立刻浮上来。修前的话壁纸层模式多半起不来。

---

## 🟡 P1-1 上传对话框在 UI 线程做重活，大图会卡死界面几秒（petctl.pyw）

`ImportDialog.reload()`（约 303 行）和 `accept_import()`（约 356 行）都在主线程里直接跑
`cutout()`（flood fill + 多轮 ndimage）和 `make_frames()`（每帧 resize+rotate，full 档 21 帧）。
4000px 大图下界面会无响应数秒，Windows 还可能把窗口标成「未响应」。

**最小改法**（不动架构）：
1. `pick()` 拿到图后先整体缩到最长边 ≤ 1600px 再进后续流程（桌宠最终只用 320px 高，预览和处理精度足够）；
2. `accept_import()` 的生成段丢进 `concurrent.futures.ThreadPoolExecutor`，完成用 `QTimer` 或信号回到主线程，期间按钮禁用 + 显示「生成中…」。

---

## 🟡 P1-2 refresh() 每秒递归扫描磁盘 + 读配置（petctl.pyw 约 514 行）

`refresh()` 每 1000ms 跑一次，里面 `characters()` 每次都 `ASSETS.glob("**/_frames.json")`
（递归扫整个 assets，user 目录图片多以后越来越慢），还每秒 `load_cfg()` 读一遍 config.json。

**改法**：把「进程状态」保持 1 秒一查（这个很轻），但形象列表和配置改成 3~5 秒一查，
或者用 `CONFIG.stat().st_mtime` 做缓存——文件没变就用上次结果。

---

## 🟡 P1-3 stop_pet 杀进程太粗暴（petctl.pyw 约 141 行）

`stop_pet()` 调 `tools/kill-pets.ps1` 按 README 描述是「杀掉所有残留桌宠进程」——
按名字匹配杀，如果将来本机同时跑别的 python 桌面程序或第二份项目副本，会误伤。

**改法**：控制台本来就会用 `OpenProcess`（pid_alive 里已有完整代码），直接复用：
`OpenProcess(PROCESS_TERMINATE, ...)` + `TerminateProcess(h, 0)` 杀 PIDFILE 里那个 pid，
PS 脚本只留作兜底。这样精准、少一次 PowerShell 启动开销（现在每次 stop 都要冷启动一个 powershell.exe）。

---

## 🟡 P1-4 单实例回连的 socket 从不释放（petctl.pyw 约 628 行）

```python
def on_conn():
    s = server.nextPendingConnection()
    if s:
        s.readyRead.connect(win.reveal)
```

每次用户双击控制台（已开第二个实例）都会创建一个 QLocalSocket，读一次之后既不
`disconnect` 也不 `deleteLater`，连接对象一直挂着。量小但会积累。改法：
`s.readyRead.connect(win.reveal)` 后接 `s.disconnected.connect(s.deleteLater)`，
或者在 reveal 完成后主动 `s.disconnectFromServer()`。

---

## 🟢 观察项

1. **petmaker.py 约 307~311 行 halo_score 有两段叠着的 docstring**：第二个字符串字面量是无效表达式，删一个。
2. **deskpet.py `load_frames` 失败直接 SystemExit**（约 159 行）：素材清单坏了就静默退出，建议弹一个 QWidget 消息框（毕竟没有控制台）告知「素材损坏」。
3. **`apply_scale` 假定 `idle` 轨道一定存在**（约 344 行 `self.raw["idle"][0]`）：petmaker 生成的都有 idle，但手工放素材的人不一定。加一行 `if "idle" not in self.raw: raise SystemExit("素材缺少 idle 轨道")` 更友好。
4. **切层级时 pid 文件有一小段真空期**：main() 循环里 unlink 后到新实例 write_pid 之间（毫秒级），控制台如果恰好在刷新会闪一下「她不在」。概率极低，知道即可。
5. **deskpet.py 里 `user32.IsChild` 的 argtypes 声明写了两遍**（约 95 与 102 行），无害，可删一处。

---

## 总体评价

架构清晰（本体 / 控制台 / 素材工厂三件套分离），注释把踩坑记录写得很到位
（WorkerW 在 Win11 26200 失效、argtypes 截断、CREATE_NO_WINDOW、PS1 编码——这些都是真金白银的教训）。
抠图算法的夹缝判定 + 反预乘思路是对的，README 里的量化指标也做得规范。

优先修 P0-1（一行的事），P1 四条可以攒着下次一起。修完 P0-1 后请务必走一遍
「控制台启动 → 默认壁纸层」的完整链路验证，别只跑调试脚本。

—— 阿酉 🍶（WorkBuddy 侧质检位）
