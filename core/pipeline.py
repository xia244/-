"""下载执行流水线：解析 -> 命名 -> 下载 -> 落盘。"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional

from . import kuaishou, ytdlp_engine
from .http import download_file, human_size, now_stamp, sanitize_filename
from .models import DownloadOptions, MediaResult, TaskOutcome
from .router import detect, needs_custom

LogFn = Callable[[str], None]
CancelFn = Callable[[], bool]


class ProgressReporter:
    """界面侧实现这些方法来刷新进度；默认实现为空操作，方便命令行调用。"""

    def on_task_start(self, index: int, total: int, url: str, platform_name: str) -> None:  # noqa: D102
        pass

    def on_task_progress(self, index: int, done: int, total: int) -> None:  # noqa: D102
        pass

    def on_task_done(self, index: int, outcome: TaskOutcome) -> None:  # noqa: D102
        pass


class DownloadPipeline:
    def __init__(
        self,
        options: DownloadOptions,
        log: Optional[LogFn] = None,
        cancel: Optional[CancelFn] = None,
        reporter: Optional[ProgressReporter] = None,
    ) -> None:
        self.options = options
        self.log = log or (lambda msg: None)
        self.cancel = cancel or (lambda: False)
        self.reporter = reporter or ProgressReporter()

    # ---------- 解析 ----------
    def parse(self, url: str) -> MediaResult:
        code, name = detect(url)
        self.log(f"识别平台：{name}")
        if needs_custom(code) and not self.options.force_ytdlp:
            if code == "kuaishou":
                result = kuaishou.parse(url, cookie=self.options.cookie, proxy=self.options.proxy)
        else:
            result = ytdlp_engine.parse(url, cookie=self.options.cookie, proxy=self.options.proxy,
                                      quality=self.options.quality)
        # 平台名统一用自维护的中文名，展示更稳定
        _, display_name = detect(url)
        result.platform_name = display_name
        return result

    # ---------- 命名 ----------
    def build_filename(self, result: MediaResult) -> str:
        title = sanitize_filename(result.title, 60) or "未命名作品"
        author = sanitize_filename(result.author, 30)
        mode = self.options.naming
        if mode == "title":
            name = title
        elif mode == "author_title_date":
            name = f"{author}-{title}-{now_stamp()}" if author else f"{title}-{now_stamp()}"
        else:
            name = f"{author}-{title}" if author else title
        return sanitize_filename(name, 110)

    # ---------- 单个链接 ----------
    def handle(self, url: str, index: int, total: int) -> TaskOutcome:
        try:
            if self.cancel():
                return TaskOutcome(url, False, "已取消")
            result = self.parse(url)
            self.log(f"标题：{result.display_title()}" + (f"｜作者：{result.author}" if result.author else ""))
            base = self.build_filename(result)
            outdir = self.options.save_dir
            os.makedirs(outdir, exist_ok=True)

            files: List[str] = []
            if result.delegate_download:
                self.log("检测到分片流，交由 yt-dlp 下载并合并（需本机安装 ffmpeg）")
                path = ytdlp_engine.download(
                    url,
                    outdir,
                    base,
                    cookie=self.options.cookie,
                    proxy=self.options.proxy,
                    fmt=result.ydl_format,
                    progress_hook=lambda d: self._ydl_hook(d, index),
                    cancel=self.cancel,
                )
                files.append(path)
            elif result.kind == "images":
                files = self._download_images(result, base, index)
            else:
                if not result.video_url:
                    return TaskOutcome(url, False, "未解析到视频地址")
                path = download_file(
                    result.video_url,
                    outdir,
                    base,
                    ext="mp4",
                    headers=result.headers,
                    proxy=self.options.proxy,
                    progress=lambda done, total_size: self.reporter.on_task_progress(index, done, total_size),
                    cancel=self.cancel,
                )
                files.append(path)
                size = os.path.getsize(path)
                self.log(f"完成：{os.path.basename(path)}（{human_size(size)}）")

            if self.options.download_cover and result.cover:
                try:
                    cover = download_file(
                        result.cover, outdir, base + "_封面", ext="jpg",
                        headers=result.headers, proxy=self.options.proxy, cancel=self.cancel,
                    )
                    files.append(cover)
                except Exception as exc:  # noqa: BLE001
                    self.log(f"封面下载失败：{exc}")

            if self.options.save_desc and (result.title or result.author):
                desc_path = os.path.join(outdir, base + ".txt")
                with open(desc_path, "w", encoding="utf-8") as fp:
                    fp.write(
                        f"平台：{result.platform_name}\n作者：{result.author}\n"
                        f"文案：{result.title}\n链接：{url}\n"
                    )
                files.append(desc_path)

            return TaskOutcome(url, True, f"{result.platform_name}｜{result.display_title()}", files)
        except InterruptedError:
            return TaskOutcome(url, False, "已取消")
        except Exception as exc:  # noqa: BLE001
            self.log(f"失败：{exc}")
            return TaskOutcome(url, False, str(exc))

    def _ydl_hook(self, data: dict, index: int) -> None:
        if data.get("status") == "downloading":
            done = data.get("downloaded_bytes") or 0
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            self.reporter.on_task_progress(index, done, total)

    def _download_images(self, result: MediaResult, base: str, index: int) -> List[str]:
        outdir = os.path.join(self.options.save_dir, base)
        os.makedirs(outdir, exist_ok=True)
        total = len(result.image_urls)
        self.log(f"图集共 {total} 张，开始下载")
        paths: List[str] = []
        counter = {"done": 0}

        def fetch(item):
            if self.cancel():
                raise InterruptedError("已取消")
            order, img_url = item
            ext = "jpg"
            lowered = img_url.split("?")[0].lower()
            for candidate in ("png", "webp", "jpeg", "gif"):
                if lowered.endswith("." + candidate):
                    ext = candidate
                    break
            path = download_file(
                img_url, outdir, f"{order:02d}", ext=ext,
                headers=result.headers, proxy=self.options.proxy, cancel=self.cancel,
            )
            counter["done"] += 1
            self.reporter.on_task_progress(index, counter["done"], total)
            return path

        with ThreadPoolExecutor(max_workers=max(1, self.options.max_workers)) as pool:
            for path in pool.map(fetch, list(enumerate(result.image_urls, 1))):
                paths.append(path)
        self.log(f"图集完成：{outdir}")
        return paths

    # ---------- 批量 ----------
    def run(self, urls: List[str]) -> List[TaskOutcome]:
        outcomes: List[TaskOutcome] = []
        total = len(urls)
        for index, url in enumerate(urls, 1):
            if self.cancel():
                self.log("已停止后续任务")
                break
            _, name = detect(url)
            self.reporter.on_task_start(index, total, url, name)
            self.log(f"—— [{index}/{total}] {url}")
            outcome = self.handle(url, index, total)
            self.reporter.on_task_done(index, outcome)
            outcomes.append(outcome)
            time.sleep(0.2)  # 轻微间隔，降低触发风控的概率
        return outcomes
