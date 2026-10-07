"""解析结果与下载任务的数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class MediaResult:
    """一个作品链接解析后的结果。"""

    platform: str                 # 平台代号，如 douyin / kuaishou / xiaohongshu
    platform_name: str            # 平台中文名，用于界面展示
    kind: str                     # video（视频）或 images（图集）
    title: str = ""               # 作品标题/文案
    author: str = ""              # 作者昵称
    video_url: str = ""           # 视频直链（kind=video 时有效）
    image_urls: List[str] = field(default_factory=list)   # 图集直链列表
    cover: str = ""               # 封面地址
    headers: Dict[str, str] = field(default_factory=dict)  # 下载直链所需的额外请求头
    # True 表示该平台存在 DASH/分片流，需交给 yt-dlp 自行下载合并（如 B 站）
    delegate_download: bool = False
    # 交给 yt-dlp 下载时使用的格式选择器
    ydl_format: str = "bestvideo+bestaudio/best"

    def display_title(self) -> str:
        return self.title or self.author or "未命名作品"


@dataclass
class DownloadOptions:
    """界面上可调的下载选项。"""

    save_dir: str = ""
    naming: str = "author_title"      # title / author_title / author_title_date
    quality: str = "best"            # best / 1080 / 720 / 480
    download_cover: bool = False
    save_desc: bool = False
    proxy: str = ""
    cookie: str = ""
    max_workers: int = 3
    force_ytdlp: bool = False         # 兜底开关：一律交给 yt-dlp 处理


@dataclass
class TaskOutcome:
    """单个链接的执行结果，用于汇总统计。"""

    url: str
    ok: bool
    message: str
    files: List[str] = field(default_factory=list)
