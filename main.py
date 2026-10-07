"""入口：默认启动图形界面，带 --cli 时走命令行批量下载。"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import DownloadOptions  # noqa: E402
from core.pipeline import DownloadPipeline  # noqa: E402
from core.router import extract_urls  # noqa: E402

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "去水印下载")


def run_cli(args) -> int:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fp:
            text = fp.read()
    else:
        text = " ".join(args.urls)
    urls = extract_urls(text)
    if not urls:
        print("未识别到有效链接")
        return 1
    options = DownloadOptions(
        save_dir=args.output or DEFAULT_DIR,
        naming=args.naming,
        quality=args.quality,
        download_cover=args.cover,
        save_desc=args.desc,
        max_workers=args.workers,
        proxy=args.proxy or "",
        cookie=args.cookie or "",
    )
    os.makedirs(options.save_dir, exist_ok=True)
    outcomes = DownloadPipeline(options, log=print).run(urls)
    ok = sum(1 for o in outcomes if o.ok)
    print(f"\n完成：成功 {ok}｜失败 {len(outcomes) - ok}｜目录：{options.save_dir}")
    return 0 if ok else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="视频去水印下载器")
    parser.add_argument("urls", nargs="*", help="作品链接（可多个）")
    parser.add_argument("-o", "--output", help="保存目录")
    parser.add_argument("-f", "--file", help="从文件读取链接，每行一个")
    parser.add_argument("--naming", default="author_title", choices=["title", "author_title", "author_title_date"])
    parser.add_argument("--quality", default="best", choices=["best", "1080", "720", "480"])
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--proxy", help="代理地址")
    parser.add_argument("--cookie", help="浏览器 Cookie")
    parser.add_argument("--cover", action="store_true", help="保存封面")
    parser.add_argument("--desc", action="store_true", help="保存文案")
    parser.add_argument("--cli", action="store_true", help="命令行模式（不启动界面）")
    args = parser.parse_args()

    if args.cli or args.urls or args.file:
        return run_cli(args)

    from ui.app import run_app

    run_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
