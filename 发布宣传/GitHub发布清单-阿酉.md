# GitHub 发布操作清单（阿酉 · 2026-09-16）

> 分工：**你只做第一步（浏览器里 5 分钟）**，剩下的我来/dsh 来。

---

## 你要做的（一次性，5 分钟）

1. **注册/登录** github.com（用户名想认真点，简历要用）；
2. **建仓库**：右上角 + → New repository → 名字 `DeskPet` → 选 Public →
   **三个初始化勾选框都不要勾**（README/.gitignore/license 本地都有）→ Create；
3. **生成令牌给我**：头像 → Settings → Developer settings → Personal access tokens →
   Tokens (classic) → Generate new token (classic) → 勾 `repo` 大类 → 生成 →
   **立刻复制**（只显示一次）。

把三样发我：**用户名 + 仓库名 + token**，我 30 秒内推送完毕。

## 我/dsh 接手的事（你不用管）

1. 刷新本地暂存（文件比初版多了不少）、按最新 config.json 状态补 .gitignore、
   写首次 commit（作者用你的 GitHub 身份）+ push；
2. **Release**：把试玩包 zip 挂到 Releases 页（观众只在这里下载，不碰 git）；
   发布包必须确认不含 nailong/科比音效（dsh 已做自动排除，挂载前我再核一遍）；
3. README 首屏补 2~3 张 GIF（录屏我来出脚本）+ 双语简介；
4. 仓座行情/标签：topics 加 `desktop-pet / pyside6 / pyinstaller / windows`。

## 上传后的收尾（可选，但建议）

- [ ] 找台没装 Python 的电脑跑 `DeskPet-Lite.exe --selftest`，把 selftest.json 截图放进 README
      （「无环境依赖实机验证」是简历和视频里都有分量的证据）；
- [ ] 视频简介里的下载地址在发布后填入。

—— 阿酉 🍶
