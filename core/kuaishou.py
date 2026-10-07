"""快手解析引擎。

yt-dlp 官方并未内置快手提取器，因此这里自行实现：
1. 展开 v.kuaishou.com 短链；
2. 抓取作品页 HTML（带移动端 UA 与随机 did）；
3. 从页面内联数据中取 `srcNoMark`（快手服务端标记的无水印视频地址）与图集地址。
"""
from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional

from .http import MOBILE_UA, expand_url, make_session, random_did
from .models import MediaResult

PLATFORM = "kuaishou"
PLATFORM_NAME = "快手"

# 无水印字段按优先级排列
VIDEO_FIELDS = ("srcNoMark", "photoUrl", "photoH265Url", "srcNoMarkH265", "playUrl", "src")
IMAGE_FIELD_HINT = ("images", "imgUrls", "imageCDN")


def _unescape(text: str) -> str:
    """快手内联数据里 URL 的 / 常被写成 \\u002F，这里还原。"""
    if not text:
        return ""
    text = text.replace("\\u002F", "/").replace("\\/", "/")
    text = text.replace("\\u0026", "&").replace("\\&", "&")
    return text


def _decode_caption(text: str) -> str:
    """还原 \\uXXXX 形式的中文标题。"""
    if not text:
        return ""
    try:
        return json.loads('"' + text.replace('"', '\\"') + '"')
    except Exception:
        return text.encode().decode("unicode_escape", errors="ignore")


def _balanced_json(html: str, marker: str) -> Optional[dict]:
    """从 HTML 中截取 marker 之后的第一个完整 JSON 对象。"""
    pos = html.find(marker)
    if pos < 0:
        return None
    start = html.find("{", pos)
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(html)):
        ch = html[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                raw = html[start:i + 1]
                try:
                    return json.loads(raw)
                except Exception:
                    return None
    return None


def _walk(obj, key: str):
    """深度优先查找 JSON 中第一个匹配 key 的值。"""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = _walk(value, key)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _walk(item, key)
            if found:
                return found
    return None


def _pick_video_url(html: str) -> str:
    """按优先级从 HTML 里挑一条无水印视频直链。"""
    for field in VIDEO_FIELDS:
        match = re.search(r'"%s"\s*:\s*"([^"]+)"' % field, html)
        if match:
            url = _unescape(match.group(1))
            if url.startswith("http"):
                return url
    return ""


def _pick_images(html: str) -> List[str]:
    """提取图集地址，兼容 images / imgUrls 两种结构。"""
    urls: List[str] = []
    for field in IMAGE_FIELD_HINT:
        for match in re.finditer(r'"%s"\s*:\s*\[(.*?)\]' % field, html, re.S):
            block = match.group(1)
            for item in re.finditer(r'"(?:url|path|imageUrl)"\s*:\s*"([^"]+)"', block):
                url = _unescape(item.group(1))
                if url.startswith("http") and url not in urls:
                    urls.append(url)
        if urls:
            break
    return urls


def _pick_text(html: str, keys) -> str:
    for key in keys:
        match = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, html)
        if match:
            value = _decode_caption(match.group(1)).strip()
            if value:
                return value
    return ""


def extract_photo_id(url: str, html: str = "") -> str:
    """从链接或页面中取出作品 ID，用于拼详情页地址。"""
    patterns = [
        r"/short-video/([0-9a-zA-Z_-]{6,})",
        r"/f/([0-9a-zA-Z_-]{6,})",
        r"[?&]photoId=([0-9a-zA-Z_-]{6,})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    if html:
        match = re.search(r'"photoId"\s*:\s*"([^"]+)"', html)
        if match:
            return match.group(1)
    return ""


def parse(url: str, cookie: str = "", proxy: str = "") -> MediaResult:
    session = make_session(proxy=proxy, cookie=cookie, mobile=True)
    # 未登录时快手依赖 did 做设备标识，缺失会返回验证页
    if "did=" not in cookie:
        session.cookies.set("did", random_did(), domain=".kuaishou.com")
        session.cookies.set("didv", str(int(time.time() * 1000)), domain=".kuaishou.com")

    final_url = expand_url(url, session=session)
    html = ""
    last_error = ""
    # 依次尝试：短链展开后的地址 → 详情页地址
    candidates = [final_url]
    photo_id = extract_photo_id(final_url)
    if photo_id:
        candidates.append(f"https://www.kuaishou.com/short-video/{photo_id}")

    for candidate in dict.fromkeys(candidates):
        try:
            resp = session.get(
                candidate,
                headers={"User-Agent": MOBILE_UA, "Referer": "https://www.kuaishou.com/"},
                timeout=20,
            )
            resp.raise_for_status()
            if resp.text and ("srcNoMark" in resp.text or "photoUrl" in resp.text or "images" in resp.text):
                html = resp.text
                final_url = candidate
                break
            html = html or resp.text
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    if not html:
        raise RuntimeError(f"无法获取快手作品页面：{last_error or '响应为空'}")

    if any(token in html for token in ("验证", "滑块", "captcha", "风控")) and "srcNoMark" not in html:
        raise RuntimeError("快手返回了验证页，请在「Cookie 设置」中填入浏览器 Cookie 后重试")

    video_url = _pick_video_url(html)
    image_urls = _pick_images(html)

    if not video_url and not image_urls:
        raise RuntimeError("未能从页面中解析出作品地址，该作品可能已删除、仅好友可见，或需要 Cookie")

    title = _pick_text(html, ("caption", "description", "title"))
    author = _pick_text(html, ("userName", "authorName", "user_name", "nickname"))
    cover_match = re.search(r'"coverUrl"\s*:\s*"([^"]+)"', html)
    cover = _unescape(cover_match.group(1)) if cover_match else ""

    return MediaResult(
        platform=PLATFORM,
        platform_name=PLATFORM_NAME,
        kind="images" if image_urls and not video_url else "video",
        title=title,
        author=author,
        video_url=video_url,
        image_urls=image_urls,
        cover=cover,
        headers={"Referer": "https://www.kuaishou.com/", "User-Agent": MOBILE_UA},
    )


def build_cookie_hint() -> str:
    return "打开快手网页版并登录后，从浏览器开发者工具复制 Cookie 粘贴到此处（可选）"
