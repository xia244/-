"""统一的网络请求工具：UA 伪装、短链展开、带进度的分块下载。"""
from __future__ import annotations

import os
import random
import re
import string
import time
import unicodedata
from typing import Callable, Dict, Optional

import requests

# 桌面端浏览器 UA（用于请求页面）
DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# 移动端 UA（用于请求手机版接口，快手/抖音对移动端返回的数据更完整）
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

DEFAULT_TIMEOUT = 20


def random_did() -> str:
    """生成快手/抖音常用的设备标识 did，降低触发风控的概率。"""
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
    return f"web_{rand}"


def build_headers(mobile: bool = False, referer: str = "", cookie: str = "") -> Dict[str, str]:
    ua = MOBILE_UA if mobile else DESKTOP_UA
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    if cookie:
        headers["Cookie"] = cookie
    return headers


def make_session(proxy: str = "", cookie: str = "", mobile: bool = False) -> requests.Session:
    """构造一个复用的会话，统一注入代理与 Cookie。"""
    session = requests.Session()
    session.headers.update(build_headers(mobile=mobile, cookie=cookie))
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})
    return session


def expand_url(url: str, session: Optional[requests.Session] = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    """把 v.douyin.com / v.kuaishou.com / xhslink.com 这类短链展开成真实链接。

    展开失败时原样返回，交给各引擎继续处理。
    """
    sess = session or requests.Session()
    try:
        resp = sess.get(url, headers=build_headers(mobile=True), timeout=timeout, allow_redirects=True)
        final = resp.url
        # 有些平台会把无效链接跳转到首页，这种情况视为展开失败
        if final and "passport" not in final:
            return final
    except Exception:
        pass
    return url


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """清洗成合法文件名：去掉非法字符、控制符，压缩空白。"""
    if not name:
        return "untitled"
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]", " ", name)
    name = re.sub(r"\s+", " ", name).strip().strip(".")
    # 去掉首尾可能出现的连续分隔符
    name = re.sub(r"^[.\-_ ]+|[.\-_ ]+$", "", name)
    if not name:
        name = "untitled"
    return name[:max_length]


def unique_path(path: str) -> str:
    """若目标文件已存在，自动追加 (1)、(2)…… 避免覆盖。"""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    index = 1
    while True:
        candidate = f"{base}({index}){ext}"
        if not os.path.exists(candidate):
            return candidate
        index += 1


ProgressCallback = Callable[[int, int], None]  # (已下载字节, 总字节)


def download_file(
    url: str,
    dest_dir: str,
    filename: str,
    ext: str = "mp4",
    headers: Optional[Dict[str, str]] = None,
    proxy: str = "",
    timeout: int = 30,
    chunk_size: int = 1024 * 256,
    progress: Optional[ProgressCallback] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> str:
    """分块下载单个文件，支持进度回调与中途取消，返回最终文件路径。"""
    os.makedirs(dest_dir, exist_ok=True)
    if not ext.startswith("."):
        ext = "." + ext
    target = unique_path(os.path.join(dest_dir, sanitize_filename(filename) + ext))

    req_headers = build_headers(mobile=True)
    if headers:
        req_headers.update(headers)

    proxies = {"http": proxy, "https": proxy} if proxy else None
    with requests.get(url, headers=req_headers, stream=True, timeout=timeout, proxies=proxies) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(target, "wb") as fp:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    fp.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
                if cancel and cancel():
                    fp.close()
                    # 清理未完成的文件，避免留下损坏文件
                    try:
                        os.remove(target)
                    except OSError:
                        pass
                    raise InterruptedError("下载已取消")
    return target


def human_size(num: float) -> str:
    """字节数转人类可读字符串。"""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}TB"


def now_stamp() -> str:
    return time.strftime("%Y%m%d")
