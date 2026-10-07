# 视频去水印下载器

一个带图形界面的 Python 工具：粘贴抖音 / 快手 / 小红书等平台作品链接，自动解析**无水印**源地址，按你设定的保存路径与命名规则下载到本地。支持单条与批量链接、视频与图集。

---

## 一、直接要 EXE？两条路（都不用懂代码）

### 方式 A：GitHub Actions 云端构建（推荐，本机不用装任何东西）

1. 把本项目整个文件夹推到你的 GitHub 仓库
2. 打开仓库页面 → **Actions** → 左侧选「构建 Windows EXE」→ 点 **Run workflow**
3. 等 3~5 分钟，跑完后在该次运行的 **Artifacts** 里下载 `视频去水印下载器-Windows`，解压即得 exe

配置文件已写好：`.github/workflows/build-windows.yml`。

### 方式 B：本机一键打包

1. 装 Python 3.9~3.12（<https://www.python.org/downloads/>，**安装时必须勾选 Add to PATH**）
2. 在本文件夹里 **双击 `build_windows.bat`**（或用 PowerShell 跑 `.\build_windows.ps1`）
3. 脚本会自动建虚拟环境、装依赖（清华源加速）、打包
4. 完成后自动打开 `dist` 文件夹，里面就是 `视频去水印下载器.exe`

脚本支持选「窗口版 / 调试版」。若打包失败或运行闪退，选调试版重跑，把黑色控制台里的报错发出来即可定位。

> 关于报毒：PyInstaller 打包的 exe 常被 Windows Defender / 360 / 火绒误报，选择「允许运行」或把 `dist` 目录加白名单即可。

---

## 二、源码运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动图形界面
python main.py

# 命令行模式（可选）
python main.py --cli "https://v.douyin.com/xxxx/" "https://www.kuaishou.com/short-video/xxxx"
python main.py --cli -f links.txt --naming title --quality 1080 --cover
```

> B 站等少数站点是分片流（DASH / m3u8），合并视频与音频需要 **ffmpeg** 并加入 PATH；其余平台不需要。

---

## 三、界面怎么用

1. **粘贴链接**：把抖音/快手/小红书的分享链接粘进输入框（支持一次多行、批量排队），右上角会实时显示识别出的平台。
2. **设置保存路径**：点击「浏览…」选择目录，默认 `下载/去水印下载`。
3. **命名方式**：`作者-标题`、`标题`、`作者-标题-日期`（文件名非法字符会自动清洗）。
4. **画质**：最佳 / 1080P 及以下 / 720P 及以下 / 480P 及以下。
5. **图集并发**：图集作品同时下载的图片数（默认 3）。
6. **可选**：同时保存封面、把文案保存为 txt。
7. 点「开始下载」，进度条与日志区会实时显示解析、下载、完成状态；中途可「停止」。

---

## 四、支持情况与去水印原理

| 平台 | 解析方式 | 无水印原理 |
| --- | --- | --- |
| 抖音 | yt-dlp | 取 `playwm` 之外的 `play_addr`（无水印）源 |
| 小红书 | yt-dlp | 取原始视频源地址 |
| B 站 / 西瓜 / 微博 | yt-dlp | 取原始源，分片流交给 yt-dlp 合并（需 ffmpeg） |
| 快手 | 自研解析 | 直接取页面内联数据里的 `srcNoMark` 字段（服务端标记的无水印地址） |

快手未内置于 yt-dlp，故单独实现：展开短链 → 抓作品页 → 提取 `srcNoMark` / 图集地址。

---

## 五、遇到风控 / 解析失败怎么办

- **快手返回验证页**：在界面「Cookie 设置」里粘贴浏览器登录后复制的 Cookie（含 `did`）。未登录时程序会自动生成随机 `did` 兜底，但仍可能被风控。
- **提示需要登录**：小红书、抖音的部分作品需要登录态，填入对应网站的 Cookie 即可。
- **网络受限**：可在「代理」中填 `http://127.0.0.1:7890` 之类的代理地址。
- **B 站 412 / 平台 403**：多为 IP 风控，换网络或稍后重试。
- **闪退看不到报错**：用调试版重打包（方式 B 选 2），控制台会打印完整错误。

---

## 六、目录结构

```
video_downloader/
├── main.py              # 入口：默认 GUI，--cli 走命令行
├── build.spec           # PyInstaller 打包配置（已验证可用）
├── build_windows.bat    # Windows 一键打包（双击即可）
├── build_windows.ps1    # 同上，PowerShell 版
├── .github/workflows/build-windows.yml   # 云端自动构建 exe
├── core/
│   ├── http.py          # 会话/短链展开/分块下载/文件名清洗
│   ├── models.py        # MediaResult、DownloadOptions 数据结构
│   ├── router.py        # 按链接分发到对应解析引擎
│   ├── ytdlp_engine.py  # 通用平台解析（抖音/小红书/B站/微博/西瓜）
│   ├── kuaishou.py      # 快手自研解析（srcNoMark）
│   └── pipeline.py      # 解析→命名→下载→保存，进度回调与取消
├── ui/
│   ├── app.py           # PySide6 主窗口与后台下载线程
│   └── theme.py         # 紫蓝配色 QSS 样式
└── assets/              # 图标（icon.svg / icon.png / icon.ico）
```

---

## 七、温馨提示

请仅下载自己拥有权利或已获授权的内容，遵守各平台服务条款与相关法律法规。
