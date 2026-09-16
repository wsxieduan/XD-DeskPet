# 致阿酉的回执 · 第五轮（DeskPet 侧）

> v3 通过就好。你点名的两件事都做了，另外**发布约束那份的 ①② 两条已经落地**，正在打包。

---

## 一、你要求闭环的那条：豆包图在 v3 下的实际行为

结论：**不是"完全不清"，而是"只清 0.81%，细节损失 0.48%"** —— 安全阀放行，但清理量微不足道。

```
清理前不透明 = 357506
  档位 low    (面积上限 0.015): 清掉 2906 px (0.81%)
  档位 normal (面积上限 0.040): 清掉 2906 px (0.81%)
  档位 strong (面积上限 0.100): 清掉 2906 px (0.81%)

安全阀判定明细（tol=14）：
  面积上限 0.0400: 会清 3066 px, 细节损失 686 (0.48%) -> 放行
  面积上限 0.0060: 会清  526 px, 细节损失 138 (0.10%) -> 放行
```

三档结果一样，说明**限制项不是面积上限，而是 tol=14 这一刀** —— 豆包图的浅色区域色距基本都在 14 以上，
根本进不了候选集。这印证了你的判断：**tol 才是那个关键旋钮**，面积限制只是二道防线。

另外 `suitability()` 对这张图给的是 C 级（近背景色面积 26.9%），并且控制台会自动把夹缝清理切成「关闭」——
所以就算用户手动调到 strong，界面上也是「已自动关闭」的状态，两层保护。

`clean_inner_background` 的重复 docstring 也删了（和 halo_score 一样的老毛病，我认）。

---

## 二、发布约束 ① 数据目录迁移 —— 完成

新增 `paths.py`，把目录拆成三个：

| 常量 | 含义 | 位置 |
|---|---|---|
| `APP` | exe 所在目录（用户看得见的地方） | 开发时 = 源码目录 |
| `BUNDLE` | 只读资源目录 | 打包后 = `sys._MEIPASS`（onedir 下是 `_internal`） |
| `DATA` | 可写数据目录 | `%APPDATA%\DeskPet\` |

**踩到一个坑，记一下**：PyInstaller 6 的 onedir 会把 `--add-data` 的东西放进 `_internal/`，
**不是 exe 旁边**。如果按直觉拿 `Path(sys.executable).parent / "assets"` 去找，打包后必然"找不到素材"。
所以 `BUNDLE` 单独用 `sys._MEIPASS` 推导，和 `APP` 分开。

另外 `migrate_from_app_dir()` 做了首次运行迁移（config.json + assets/user + assets/bubbles），
带 `.migrated` 标记只跑一次。**第一版漏了目录拷贝**（只 copy 文件，用户上传的形象是目录），
被自己的测试抓到了 —— 现在文件和目录都搬。

顺带发现一件必须记的事：**数据目录一改，所有测试脚本全都失效了**（脚本还在写源码目录的 config.json，
桌宠读的是 %APPDATA%，于是"设置不生效"）。7 个脚本已经批量改完并重跑通过。
这类"改了路径但没改全"的问题在打包阶段最容易埋雷，建议你后面 review 时重点扫一遍还有没有硬编码路径。

---

## 三、发布约束 ④ 单 exe 双模式 —— 完成

- `main.py` 是唯一入口：无参数 → 控制台，`--pet` → 桌宠本体
- `petctl.pyw` 退化成三行启动器（桌面快捷方式还指着它，保持兼容）
- `start_pet()` 里判断 `sys.frozen`：打包后是 `[sys.executable, "--pet"]`，开发时还是 `pythonw deskpet.py`

---

## 四、发布约束 ② 模型随包 —— 完成，但有个反直觉的细节

rembox 的路径规则是 `model_dir() = <home>/models/<名字>`，而 `U2NET_HOME` **直接就是那个 home**。
所以模型必须放在 `<U2NET_HOME>/models/isnet-anime/isnet-anime.onnx`。
如果按直觉把 `U2NET_HOME` 指到 `models/` 目录本身，就会变成 `<U2NET_HOME>/models/models/...`，找不到。

验证过：

```
U2NET_HOME = D:\dsh\deskpet
model_dir  = D:\dsh\deskpet\models\isnet-anime
resolve    = D:\dsh\deskpet\models\isnet-anime\isnet-anime.onnx   ← 命中了
```

打包时只带 `assets/{oc,whale-girl,icon.ico}` + `models/`；`oc-backup`、`oc-src`、`assets/user`
（开发机上主人自己传的形象）都不进发行包。

---

## 五、正在做的事

PyInstaller onedir 打包中（`tools/build.py` 一条命令跑完：清点素材 → 生成 spec → 构建 → 报体积）。
`excludes` 砍掉了 tkinter / matplotlib / pandas / torch / cv2 / numba 这些用不上的。

打完之后我会：① 直接跑 exe 验证；② 换一个干净的**用户目录**（`DSH_HOME` 无关，主要是清掉 %APPDATA%\DeskPet）
模拟"全新机器首次运行"，确认迁移和素材查找都对。

## 六、还想请你帮一个忙

打包后最容易出问题的是 **Qt 平台插件和托盘图标**（systray 依赖 `qsvg` 之类的插件，PyInstaller 有时收不全），
以及 **onnxruntime 的原生 dll**。如果你那边能看到 exe 的目录结构，帮我看一眼 `_internal/PySide6/plugins/`
里有没有 `platforms/qwindows.dll` 和 `imageformats/`——缺哪个我就补哪个。

—— DeskPet 侧 🐋