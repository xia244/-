# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Windows / macOS / Linux 通用）。

用法：
    pyinstaller build.spec --clean --noconfirm
产物在 dist/ 目录下。
"""
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.dirname(__file__) if "__file__" in globals() else os.getcwd())

# ---- yt-dlp：提取器是动态导入的，必须整包收集，否则运行时报 "Unsupported URL" ----
hidden = []
hidden += collect_submodules("yt_dlp.extractor")
hidden += collect_submodules("yt_dlp.networking")
hidden += collect_submodules("yt_dlp.downloader")
hidden += collect_submodules("yt_dlp.postprocessor")
hidden += [
    "yt_dlp",
    "yt_dlp.extractor.extractors",   # 全量提取器清单
    "yt_dlp.utils",
    "yt_dlp.cookies",
    "requests",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
]

# ---- 体积优化：去掉用不到的 Qt 大模块 ----
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtWebView",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2",
    "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtQmlModels", "PySide6.QtQmlWorkerScript",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtSerialPort", "PySide6.QtSensors", "PySide6.QtTest",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools",
    "PySide6.QtVirtualKeyboard", "PySide6.QtNetworkAuth", "PySide6.QtRemoteObjects",
    "PySide6.QtScxml", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSql",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtPrintSupport",
    "PySide6.QtConcurrent", "PySide6.QtXml",
    "tkinter", "unittest", "pydoc", "doctest", "lib2to3",
    "PIL", "numpy", "scipy", "pandas", "matplotlib",
    "pytest", "setuptools", "pip", "wheel", "IPython", "notebook",
]

# ---- 图标：Windows/macOS 分别用 ico/icns，Linux 用 png ----
icon_file = ""
if sys.platform == "win32":
    candidate = os.path.join(ROOT, "assets", "icon.ico")
    icon_file = candidate if os.path.exists(candidate) else ""
elif sys.platform == "darwin":
    candidate = os.path.join(ROOT, "assets", "icon.icns")
    icon_file = candidate if os.path.exists(candidate) else os.path.join(ROOT, "assets", "icon.png")

# CONSOLE_MODE=1 时打出带控制台的调试版，方便看报错误；默认 0 为纯窗口版
CONSOLE_MODE = os.environ.get("CONSOLE_MODE", "0").strip() == "1"
# 产物名（Windows 下若担心中文路径，可改成英文 VideoDownloader）
APP_NAME = os.environ.get("APP_NAME", "视频去水印下载器").strip() or "视频去水印下载器"

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[(os.path.join(ROOT, "assets"), "assets")],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=CONSOLE_MODE,   # True 会额外弹出黑色控制台窗口，便于排查打包问题
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file or None,
)

# macOS 需要 .app 包，取消下方注释即可生成
# app = BUNDLE(
#     exe,
#     name="视频去水印下载器.app",
#     icon=icon_file or None,
#     bundle_identifier="com.local.videodownloader",
# )
