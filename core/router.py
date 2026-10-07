"""平台识别与链接路由。"""
from __future__ import annotations

import re
from typing import List, Tuple

# 域名关键字 -> (平台代号, 中文名)
PLATFORM_RULES: List[Tuple[str, str, str]] = [
    ("douyin.com", "douyin", "抖音"),
    ("iesdouyin.com", "douyin", "抖音"),
    ("kuaishou.com", "kuaishou", "快手"),
    ("kuaishou.cn", "kuaishou", "快手"),
    ("chenzhongtech.com", "kuaishou", "快手"),
    ("xiaohongshu.com", "xiaohongshu", "小红书"),
    ("xhslink.com", "xiaohongshu", "小红书"),
    ("bilibili.com", "bilibili", "哔哩哔哩"),
    ("b23.tv", "bilibili", "哔哩哔哩"),
    ("weibo.com", "weibo", "微博"),
    ("ixigua.com", "ixigua", "西瓜视频"),
    ("youtube.com", "youtube", "YouTube"),
    ("youtu.be", "youtube", "YouTube"),
    ("instagram.com", "instagram", "Instagram"),
]

# 需要自研解析的平台（yt-dlp 未内置提取器）
CUSTOM_ENGINES = {"kuaishou"}

URL_PATTERN = re.compile(r"https?://[^\s，,、\"'）)】\]]+", re.I)


def extract_urls(text: str) -> List[str]:
    """从一段分享文案中抠出所有链接。"""
    urls: List[str] = []
    for match in URL_PATTERN.finditer(text or ""):
        url = match.group(0).rstrip("。.!！?？;；")
        if url not in urls:
            urls.append(url)
    return urls


def detect(url: str) -> Tuple[str, str]:
    """返回 (平台代号, 平台中文名)。"""
    lowered = (url or "").lower()
    for keyword, code, name in PLATFORM_RULES:
        if keyword in lowered:
            return code, name
    return "unknown", "未知平台"


def describe(urls: List[str]) -> str:
    """汇总一批链接的平台分布，用于界面提示。"""
    counter = {}
    for url in urls:
        _, name = detect(url)
        counter[name] = counter.get(name, 0) + 1
    return "、".join(f"{name}×{count}" for name, count in counter.items())


def needs_custom(code: str) -> bool:
    return code in CUSTOM_ENGINES
