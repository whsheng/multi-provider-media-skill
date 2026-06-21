#!/usr/bin/env python3
"""
图片下载工具
支持从 URL 下载单张或多张图片
"""

import os
import sys
import argparse
import requests
from urllib.parse import urlparse
from datetime import datetime


def download_image(url: str, output_path: str = None) -> str:
    """
    从 URL 下载单张图片

    Args:
        url: 图片 URL
        output_path: 输出路径,如果不提供则根据 URL 自动命名

    Returns:
        str: 下载后的文件路径
    """
    try:
        # 如果没有指定输出路径,从 URL 中提取文件名
        if not output_path:
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path) or f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

            # 确保有扩展名
            if not os.path.splitext(filename)[1]:
                filename += ".png"

            output_path = os.path.join(".", filename)

        # 创建目录(如果需要)
        dir_path = os.path.dirname(output_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        print(f"📥 正在下载: {url}")
        print(f"   保存到: {output_path}")

        # 下载图片
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # 保存图片
        with open(output_path, "wb") as f:
            f.write(response.content)

        print(f"   ✅ 下载成功!")
        return output_path

    except Exception as e:
        raise Exception(f"下载失败: {str(e)}")


def download_images(urls: list, output_dir: str = "./downloaded_images") -> list:
    """
    批量下载多张图片

    Args:
        urls: 图片 URL 列表
        output_dir: 输出目录

    Returns:
        list: 下载成功的文件路径列表
    """
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    successful = []
    failed = []

    print(f"\n📦 开始批量下载 {len(urls)} 张图片到 {output_dir}\n")

    for i, url in enumerate(urls, 1):
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}_{i}.png"
            filepath = os.path.join(output_dir, filename)

            # 下载图片
            result = download_image(url, filepath)
            successful.append(result)

        except Exception as e:
            print(f"   ❌ 失败: {str(e)}")
            failed.append((url, str(e)))

    # 打印汇总
    print(f"\n📊 下载完成:")
    print(f"   成功: {len(successful)}/{len(urls)}")
    print(f"   失败: {len(failed)}/{len(urls)}")

    if failed:
        print("\n❌ 失败列表:")
        for url, error in failed:
            print(f"   - {url}: {error}")

    return successful


def main():
    parser = argparse.ArgumentParser(description="图片下载工具")
    parser.add_argument("urls", nargs="+", help="图片 URL(可指定多个)")
    parser.add_argument("--output", "-o", help="输出文件路径(单张图片时有效)")
    parser.add_argument("--output-dir", "-d", default="./downloaded_images", help="输出目录(批量下载时有效,默认 ./downloaded_images)")

    args = parser.parse_args()

    if len(args.urls) == 1:
        # 单张图片
        try:
            result = download_image(args.urls[0], args.output)
            print(f"\n✅ 图片已保存: {result}")
        except Exception as e:
            print(f"\n❌ 错误: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        # 批量下载
        try:
            results = download_images(args.urls, args.output_dir)
            print(f"\n✅ 所有图片已保存到: {args.output_dir}")
        except Exception as e:
            print(f"\n❌ 错误: {str(e)}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
