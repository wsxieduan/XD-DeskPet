# 桌宠项目代码审查 · 第二轮（阿酉 · 2026-09-14 19:15）

> 复查范围：deskpet.py / petctl.pyw 本轮修改后的全量代码 + logs 运行日志 + selftest 报告。
> 结论先行：**上一轮的 P0 已修复干净，还顺手修掉了一个我没料到的深层问题**。但新接入的 AI 抠图带来 1 个新 P0 和 1 个升级版卡顿问题，详见下文。

---

## ✅ 已确认修复（都核实过）

1. **P0 print 崩溃** → 新增 `_setup_log()`，启动即把 stdout/stderr 重定向到 `logs/deskpet.log`。
   已用日志验证：19:07 之后父进程是 `pythonw.exe`，`layer:` 行照常输出——修复有效。
2. **「看得见点不到」** → `push_to_bottom` 从 `HWND_BOTTOM`（会落到桌面图标层下面，
   WindowFromPoint 命中 SysListView32）改为插到 Progman 正上方。这个发现很漂亮，
   注释里把两个坑都写明白了。`report-final-verify.txt` 四项全过（裸露可见 / 被盖消失 / 点击气泡 / 拖拽记忆）。
3. **控制台无限重启隐患** → `QButtonGroup` 显式分组 + `refresh()` 期间 `_syncing` 护栏，
   「刷新→toggled→apply→重启→再刷新」的环路堵住了。
4. **新功能完成度不错**：气泡配色（自动推导 + 自定义 + 实时预览 + `bubble_resolved` 回写所见即所得，
   还考虑了 WCAG 对比度）；AI 抠图选项（rembg/isnet-anime）已接进上传对话框。日志双份（ctl.log / deskpet.log）便于排查。

---

## 🔴 N1（新 P0）：AI 抠图一次，鼠标指针永久变「等待」（petctl.pyw reload()）

`ImportDialog.reload()` 里光标覆盖栈不平衡：

```python
316:  QApplication.setOverrideCursor(Qt.WaitCursor)   # 设第 1 次
331:  QApplication.setOverrideCursor(Qt.WaitCursor)   # AI 模式又设第 2 次
...
344:  finally: QApplication.restoreOverrideCursor()   # 只恢复 1 次
```

Qt 的 override cursor 是**栈**，set 两次必须 restore 两次。走 AI 路径后栈里永远剩一个
WaitCursor——**整个应用的鼠标指针永久变沙漏**，直到重启控制台。而 UI 上 AI 是默认
第一项（「推荐」），几乎必触发。dsh 自己测试时大概率已经出现了，只是没注意光标形状。

**修法（二选一）**：
- 直接删掉 331 行那次重复的 set（外层 316 已经设过了，AI 慢也是同一种等待）；
- 或严谨一点：把两处包成配对的 try/finally。

---

## 🟡 N2：AI 抠图 + 生成动画仍卡在 UI 线程（上轮 P1-1，这轮更严重了）

`reload()` 的 `cutout_ai()`（模型首次加载 + 推理，10~60 秒级）和 `accept_import()` 的
`make_frames()`（full 档 21 帧仿射变换）都还在主线程跑，期间整个控制台「未响应」。
AI 一接入，这个问题的体感会从「卡一下」变成「卡半分钟」。

**最低成本改法**：AI 路径先把原图缩到最长边 ≤1600px 再喂给 `cutout_ai`
（它内部本来就按 2048 处理，最终素材只用 320px 高，1600 绰绰有余）；
根治则用 `concurrent.futures` 丢线程 + 信号回主线程。建议至少做缩图这一步。

---

## 🟡 N3：push_to_bottom 每 500ms 做一次「全窗口枚举 + 双广播」

新版 `push_to_bottom` 每次都调 `find_desktop_host()`：`EnumWindows` 枚举全部顶层窗口 +
对 Progman 发**两次** `WM_SPAWN_WORKER` 广播（这条消息是让桌面生成 WorkerW 的）。
`bottom_timer` 每 500ms 跑一遍，等于每秒两次桌面广播 + 全量枚举——浪费 CPU，
频繁戳 Progman 也没必要。

**改法**：把 host hwnd 缓存下来（`self._host`），`SetWindowPos` 失败或
`IsWindow(host)` 为假时才重新查找；重申间隔放宽到 1~2 秒足够。

---

## 🟡 上轮遗留、这轮还没动的（不急，攒着一起修）

| 编号 | 内容 | 位置 |
|---|---|---|
| P1-2 | `refresh()` 每秒递归 glob 整个 assets + 每秒读 config.json；建议形象列表 3~5 秒一查或按 mtime 缓存 | petctl.pyw `_refresh_inner` |
| P1-3 | `stop_pet` 仍按名字匹配杀全部 python 进程（kill-pets.ps1），有误伤风险；建议改用已有的 OpenProcess + TerminateProcess 只杀 PIDFILE 那个 pid | petctl.pyw `stop_pet` |
| P1-4 | 单实例回连的 QLocalSocket 从不 `deleteLater`，慢泄漏 | petctl.pyw `on_conn` |

## 🟢 本轮新增观察项

1. `_setup_log()` 里 `sz` 被赋值两次、`hasattr(_c, "wintypes")` 恒为真——冗余无害，可简化。
2. `logs/*.log` 追加模式无轮转，长期挂机会一直涨。建议超过 1MB 时改名 `.old` 重开。
3. `BubblePreview` 的渐变 top 色没带 alpha（桌宠实际画的是半透明），预览会比实物略实一点。几乎不可见，知道即可。
4. petmaker.py 的 `halo_score` 双 docstring、deskpet.py 的 `FindWindowW`/`IsChild` argtypes 重复声明——上轮观察项，仍在，无害。

---

## 总评

这一轮修得相当漂亮：P0 一击即中，「看得见点不到」的根因分析（图标层挡点击）比上一轮
报告的理解更深一层，气泡配色的 HSV 推导 + 对比度考量也看得出下了功夫。验证脚本覆盖
也全。当前真正要动手的就一件事：**N1 的光标泄漏，五行代码的事，建议马上修**；
N2 缩图、N3 缓存 host 可以和遗留三条攒成下一批。

—— 阿酉 🍶（WorkBuddy 侧质检位 · 第二轮）
