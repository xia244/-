"""PySide6 图形界面：链接输入、选项设置、进度与日志。"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import List

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget, QSizePolicy,
    QApplication,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import DownloadOptions  # noqa: E402
from core.pipeline import DownloadPipeline, ProgressReporter  # noqa: E402
from core.router import detect, describe, extract_urls  # noqa: E402
from ui import theme  # noqa: E402

def app_base_dir() -> str:
    """源码运行时返回项目根目录；PyInstaller 打包后返回临时解压目录 _MEIPASS。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _icon_path() -> str:
    """依次尝试 ico / png / svg，保证打包后仍能显示图标。"""
    assets = os.path.join(app_base_dir(), "assets")
    for name in ("icon.ico", "icon.png", "icon.svg"):
        path = os.path.join(assets, name)
        if os.path.exists(path):
            return path
    return ""


DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "去水印下载")

QUALITY_ITEMS = [("最佳画质", "best"), ("1080P 及以下", "1080"), ("720P 及以下", "720"), ("480P 及以下", "480")]
NAMING_ITEMS = [("作者 - 标题", "author_title"), ("标题", "title"), ("作者 - 标题 - 日期", "author_title_date")]


class _Reporter(ProgressReporter):
    def __init__(self, thread: "DownloadThread") -> None:
        self.thread = thread

    def on_task_start(self, index: int, total: int, url: str, platform_name: str) -> None:
        self.thread.stage.emit(index, total, f"{platform_name}｜{url[:48]}")

    def on_task_progress(self, index: int, done: int, total: int) -> None:
        self.thread.progress.emit(done, total)

    def on_task_done(self, index: int, outcome) -> None:
        self.thread.log.emit(("完成 ✔ " if outcome.ok else "失败 ✘ ") + (outcome.message or ""))


class DownloadThread(QThread):
    log = Signal(str)
    stage = Signal(int, int, str)
    progress = Signal(int, int)
    finished_all = Signal(int, int)

    def __init__(self, urls: List[str], options: DownloadOptions, parent=None) -> None:
        super().__init__(parent)
        self.urls = urls
        self.options = options
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        pipeline = DownloadPipeline(
            self.options,
            log=self.log.emit,
            cancel=lambda: self._stop,
            reporter=_Reporter(self),
        )
        try:
            outcomes = pipeline.run(self.urls)
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"运行异常：{exc}")
            outcomes = []
        ok = sum(1 for o in outcomes if o.ok)
        self.finished_all.emit(ok, len(outcomes) - ok)


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return frame


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("视频去水印下载器")
        self.resize(940, 720)
        self.setMinimumSize(860, 640)
        icon_file = _icon_path()
        if icon_file:
            self.setWindowIcon(QIcon(icon_file))
        self.thread: DownloadThread | None = None

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(14)

        root.addLayout(self._build_header())
        root.addWidget(self._build_input_card())
        root.addWidget(self._build_option_card())
        root.addWidget(self._build_progress_card())
        root.addWidget(self._build_log_card(), 1)

    # ---------- 布局 ----------
    def _build_header(self):
        box = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel("视频去水印下载器")
        title.setObjectName("title")
        sub = QLabel("粘贴抖音 / 快手 / 小红书 / B站 等作品链接，一键保存无水印文件")
        sub.setObjectName("subtitle")
        left.addWidget(title)
        left.addWidget(sub)
        box.addLayout(left)
        box.addStretch(1)
        self.platform_chip = QLabel("等待链接")
        self.platform_chip.setObjectName("chip")
        box.addWidget(self.platform_chip)
        return box

    def _build_input_card(self):
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        head = QHBoxLayout()
        section = QLabel("① 作品链接")
        section.setObjectName("section")
        head.addWidget(section)
        head.addStretch(1)
        paste_btn = QPushButton("从剪贴板粘贴")
        paste_btn.clicked.connect(self._paste_from_clipboard)
        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(lambda: self.input.clear())
        head.addWidget(paste_btn)
        head.addWidget(clear_btn)
        layout.addLayout(head)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("粘贴视频或图集链接，支持主流短视频平台（每行一个，可一次粘贴多条）")
        self.input.setFixedHeight(110)
        self.input.textChanged.connect(self._refresh_chip)
        layout.addWidget(self.input)

        hint = QLabel("提示：抖音/快手分享短链会自动跳转还原；若平台要求验证，请在下方填入浏览器 Cookie。")
        hint.setObjectName("hint")
        layout.addWidget(hint)
        return card

    def _build_option_card(self):
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        section = QLabel("② 保存设置")
        section.setObjectName("section")
        layout.addWidget(section)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("保存路径"))
        self.dir_edit = QLineEdit(DEFAULT_DIR)
        row1.addWidget(self.dir_edit, 1)
        browse = QPushButton("浏览…")
        browse.clicked.connect(self._choose_dir)
        row1.addWidget(browse)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("命名方式"))
        self.naming = QComboBox()
        for text, data in NAMING_ITEMS:
            self.naming.addItem(text, data)
        row2.addWidget(self.naming)
        row2.addSpacing(16)
        row2.addWidget(QLabel("画质"))
        self.quality = QComboBox()
        for text, data in QUALITY_ITEMS:
            self.quality.addItem(text, data)
        row2.addWidget(self.quality)
        row2.addSpacing(16)
        row2.addWidget(QLabel("图集并发"))
        self.workers = QSpinBox()
        self.workers.setRange(1, 8)
        self.workers.setValue(3)
        self.workers.setFixedWidth(70)
        row2.addWidget(self.workers)
        row2.addStretch(1)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.cover_chk = QCheckBox("同时保存封面")
        self.desc_chk = QCheckBox("保存文案为 txt")
        self.desc_chk.setChecked(True)
        row3.addWidget(self.cover_chk)
        row3.addWidget(self.desc_chk)
        row3.addSpacing(16)
        row3.addWidget(QLabel("代理(可选)"))
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("http://127.0.0.1:7890")
        self.proxy_edit.setFixedWidth(190)
        row3.addWidget(self.proxy_edit)
        row3.addStretch(1)
        layout.addLayout(row3)

        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Cookie(可选)"))
        self.cookie_edit = QLineEdit()
        self.cookie_edit.setPlaceholderText("解析失败/提示验证时，粘贴浏览器复制的完整 Cookie")
        self.cookie_edit.setEchoMode(QLineEdit.Password)
        row4.addWidget(self.cookie_edit, 1)
        layout.addLayout(row4)
        return card

    def _build_progress_card(self):
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        row = QHBoxLayout()
        self.start_btn = QPushButton("开始下载")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        self.open_btn = QPushButton("打开文件夹")
        self.open_btn.clicked.connect(self._open_dir)
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addWidget(self.open_btn)
        row.addStretch(1)
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("hint")
        row.addWidget(self.status_label)
        layout.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setValue(0)
        layout.addWidget(self.bar)
        self.task_label = QLabel("")
        self.task_label.setObjectName("hint")
        layout.addWidget(self.task_label)
        return card

    def _build_log_card(self):
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        head = QHBoxLayout()
        section = QLabel("运行日志")
        section.setObjectName("section")
        head.addWidget(section)
        head.addStretch(1)
        clear = QPushButton("清空日志")
        clear.clicked.connect(lambda: self.log_view.clear())
        head.addWidget(clear)
        layout.addLayout(head)

        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)
        return card

    # ---------- 交互 ----------
    def _paste_from_clipboard(self) -> None:
        text = QApplication.clipboard().text().strip()
        if not text:
            self._log("剪贴板为空")
            return
        current = self.input.toPlainText().strip()
        self.input.setPlainText((current + "\n" + text).strip() if current else text)

    def _choose_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择保存文件夹", self.dir_edit.text() or DEFAULT_DIR)
        if path:
            self.dir_edit.setText(path)

    def _open_dir(self) -> None:
        path = self.dir_edit.text().strip() or DEFAULT_DIR
        os.makedirs(path, exist_ok=True)
        QDesktopServices.openUrl(f"file:///{path}" if os.name == "nt" else f"file://{path}")

    def _refresh_chip(self) -> None:
        urls = extract_urls(self.input.toPlainText())
        if not urls:
            self.platform_chip.setText("等待链接")
            return
        names = []
        for url in urls[:3]:
            _, name = detect(url)
            if name not in names:
                names.append(name)
        extra = f" 等 {len(urls)} 条" if len(urls) > 1 else ""
        self.platform_chip.setText("、".join(names) + extra)

    def _collect_options(self) -> DownloadOptions | None:
        urls = extract_urls(self.input.toPlainText())
        if not urls:
            QMessageBox.information(self, "提示", "请先粘贴至少一个作品链接")
            return None
        return DownloadOptions(
            save_dir=self.dir_edit.text().strip() or DEFAULT_DIR,
            naming=self.naming.currentData(),
            quality=self.quality.currentData(),
            download_cover=self.cover_chk.isChecked(),
            save_desc=self.desc_chk.isChecked(),
            max_workers=self.workers.value(),
            proxy=self.proxy_edit.text().strip(),
            cookie=self.cookie_edit.text().strip(),
        ), urls

    def _start(self) -> None:
        collected = self._collect_options()
        if not collected:
            return
        options, urls = collected
        os.makedirs(options.save_dir, exist_ok=True)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(f"下载中 0/{len(urls)}")
        self._log(f"开始处理 {len(urls)} 条链接 → {options.save_dir}")

        self.thread = DownloadThread(urls, options, self)
        self.thread.log.connect(self._log)
        self.thread.stage.connect(self._on_stage)
        self.thread.progress.connect(self._on_progress)
        self.thread.finished_all.connect(self._on_finished)
        self.thread.start()

    def _stop(self) -> None:
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.status_label.setText("正在停止…")
            self._log("收到停止指令，等待当前任务退出")

    def _on_stage(self, index: int, total: int, text: str) -> None:
        self.bar.setValue(0)
        self.status_label.setText(f"下载中 {index}/{total}")
        self.task_label.setText(text)

    def _on_progress(self, done: int, total: int) -> None:
        if total and total > 0:
            self.bar.setValue(min(100, int(done * 100 / total)))
        elif done:
            self.bar.setValue(min(99, (self.bar.value() + 3) % 100))

    def _on_finished(self, ok: int, fail: int) -> None:
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.bar.setValue(100)
        self.status_label.setText(f"完成：成功 {ok} 条，失败 {fail} 条")
        self.task_label.setText("")
        self._log(f"全部结束｜成功 {ok}｜失败 {fail}")
        if fail == 0 and ok > 0:
            QMessageBox.information(self, "完成", f"{ok} 个作品已保存到：\n{self.dir_edit.text()}")

    def _log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{stamp}] {message}")
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())


def run_app() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    icon_file = _icon_path()
    if icon_file:
        app.setWindowIcon(QIcon(icon_file))
    app.setStyleSheet(theme.QSS)
    if sys.platform == "win32":
        # 让 Windows 任务栏显示自己的图标，而不是 Python 的
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VideoDownloader.NoWatermark")
        except Exception:  # noqa: BLE001
            pass
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
