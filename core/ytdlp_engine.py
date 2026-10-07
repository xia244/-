"""基于 yt-dlp 的通用解析引擎，覆盖抖音、小红书、B 站、微博、西瓜等平台。

职责：
1. 调用 yt-dlp 解析出作品元数据与格式列表；
2. 自动剔除带水印的格式，挑选最高画质；
3. 遇到 DASH/m3u8 分片流（如 B 站）时，交由 yt-dlp 自行下载合并。
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

from yt_dlp import YoutubeDL

from .http import build_headers
from .models import MediaResult

IMAGE_EXTS = ("jpg", "jpeg", "png", "webp", "bmp", "gif")
STREAM_PROTOCOLS = ("http_dash_segments", "m3u8_native", "m3u8", "ism", "f4m", "niconico_dmc")

# 这些标记通常意味着该地址带平台水印
WATERMARK_PATTERN = re.compile(r"playwm|watermark|_wm|wm_|download_addr|/logo|douyinwm", re.I)


def _is_watermarked(fmt: dict) -> bool:
    blob = " ".join(
        str(fmt.get(key, ""))
        for key in ("url", "format_id", "format_note", "format", "manifest_url")
    )
    return bool(WATERMARK_PATTERN.search(blob))


def _quality_score(fmt: dict) -> tuple:
    """排序依据：先按分辨率，再按码率与体积。"""
    height = fmt.get("height") or 0
    width = fmt.get("width") or 0
    tbr = fmt.get("tbr") or 0
    size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
    return (int(height), int(width), float(tbr or 0), int(size))


def format_selector(quality: str = "best") -> str:
    """按画质档位生成 yt-dlp 格式选择器。"""
    if quality and quality.isdigit():
        limit = int(quality)
        return f"bestvideo[height<={limit}]+bestaudio/best[height<={limit}]/best"
    return "bestvideo+bestaudio/best"


def _select_video_format(formats: List[dict], quality: str = "best") -> dict:
    """优先选择无水印的最高画质格式（受画质档位限制）。"""
    if not formats:
        raise RuntimeError("该作品没有可下载的格式")

    pool_source = formats
    if quality and quality.isdigit():
        limit = int(quality)
        limited = [f for f in formats if not (f.get("height") or 0) or int(f.get("height") or 0) <= limit]
        if limited:
            pool_source = limited

    candidates = [f for f in pool_source if f.get("url") and not f.get("acodec") == "none" or True]
    clean = [f for f in candidates if not _is_watermarked(f)]
    pool = clean or candidates
    # 只保留有真实地址的格式
    pool = [f for f in pool if f.get("url")]
    if not pool:
        pool = [f for f in pool_source if f.get("url")] or pool_source
    return max(pool, key=_quality_score)


def _collect_image_urls(info: dict) -> List[str]:
    urls: List[str] = []
    for fmt in info.get("formats") or []:
        if str(fmt.get("ext", "")).lower() in IMAGE_EXTS and fmt.get("url"):
            urls.append(fmt["url"])
    # 部分提取器会把图片放进 thumbnails
    for thumb in info.get("thumbnails") or []:
        url = thumb.get("url")
        if url and url not in urls and ".jpg" in url.lower():
            urls.append(url)
    return urls


def _base_opts(cookie: str = "", proxy: str = "", quiet: bool = True) -> dict:
    opts: Dict[str, object] = {"quiet": quiet, "no_warnings": quiet, "noplaylist": False}
    if cookie:
        opts["cookiefile"] = None
        opts["http_headers"] = {"Cookie": cookie}
    if proxy:
        opts["proxy"] = proxy
    return opts


def parse(url: str, cookie: str = "", proxy: str = "", quality: str = "best") -> MediaResult:
    """解析链接，返回统一的结果对象。"""
    opts = _base_opts(cookie, proxy)
    opts["format"] = None  # 只解析不下载，拿到全部格式
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise RuntimeError("解析失败：未获取到作品信息")

    # 合集/列表：取第一个条目继续处理
    if info.get("_type") == "playlist" and info.get("entries"):
        entries = [e for e in info["entries"] if e]
        if not entries:
            raise RuntimeError("列表为空")
        info = entries[0]
        if info.get("formats") is None and info.get("url"):
            with YoutubeDL(_base_opts(cookie, proxy)) as ydl:
                info = ydl.extract_info(info["url"], download=False) or info

    platform_name = str(info.get("extractor_key") or info.get("extractor") or "未知平台")
    title = str(info.get("title") or info.get("description") or "").strip()
    author = str(info.get("uploader") or info.get("channel") or info.get("creator") or "").strip()
    cover = ""
    thumbs = info.get("thumbnails") or []
    if thumbs:
        cover = thumbs[-1].get("url", "")

    image_urls = _collect_image_urls(info)
    formats = [f for f in (info.get("formats") or []) if f.get("url")]
    video_url = ""
    delegate = False
    kind = "video"

    if image_urls and not any(str(f.get("ext", "")).lower() not in IMAGE_EXTS for f in formats):
        kind = "images"
    elif formats:
        best = _select_video_format(formats, quality)
        video_url = best.get("url", "")
        protocol = str(best.get("protocol") or "")
        # 分片流无法用简单下载器拼接，交给 yt-dlp 处理（需要 ffmpeg）
        delegate = protocol in STREAM_PROTOCOLS or not video_url
    elif info.get("url"):
        video_url = info["url"]
        delegate = str(info.get("protocol") or "") in STREAM_PROTOCOLS
    else:
        raise RuntimeError("未解析到媒体地址，可能需要提供 Cookie 或该链接不受支持")

    return MediaResult(
        platform=str(info.get("extractor_key") or ""),
        platform_name=platform_name,
        kind=kind,
        title=title,
        author=author,
        video_url=video_url,
        image_urls=image_urls,
        cover=cover,
        headers=build_headers(mobile=True,
                              referer=str(info.get("webpage_url") or url)),
        delegate_download=delegate,
        ydl_format=format_selector(quality),
    )


def download(
    url: str,
    outdir: str,
    filename: str,
    cookie: str = "",
    proxy: str = "",
    fmt: str = "bestvideo+bestaudio/best",
    progress_hook=None,
    cancel=None,
) -> str:
    """交给 yt-dlp 完整下载（含合并音画），返回文件路径。"""
    os.makedirs(outdir, exist_ok=True)
    opts = _base_opts(cookie, proxy)
    opts.update(
        {
            "format": fmt,
            "outtmpl": os.path.join(outdir, filename + ".%(ext)s"),
            "merge_output_format": "mp4",
            "noprogress": True,
            "concurrent_fragment_downloads": 4,
        }
    )
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)
