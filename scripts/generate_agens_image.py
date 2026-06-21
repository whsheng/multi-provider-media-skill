#!/usr/bin/env python3
"""
Agens-AI 图片生成脚本
支持文生图、图生图与多 API Key 轮询
"""

import argparse
import os
import sys
from typing import Optional, Sequence

# 添加技能目录到 Python 路径
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, skill_dir)

from skill_runtime.agens import (
    DEFAULT_AGENS_IMAGE_MODEL,
    extract_image_urls,
    normalize_image_urls,
)
from skill_runtime.http import RotatingAPIClient
from skill_runtime.media import download_files, sanitize_filename
from skill_runtime.providers import AGENS_PROVIDER

DEFAULT_SIZE = "1024x1024"
DEFAULT_RESPONSE_FORMAT = "url"


def generate_agens_image(
    prompt: str,
    api_key: Optional[str] = None,
    api_keys: Optional[Sequence[str]] = None,
    model: str = DEFAULT_AGENS_IMAGE_MODEL,
    size: str = DEFAULT_SIZE,
    image_urls: Optional[Sequence[str]] = None,
    response_format: str = DEFAULT_RESPONSE_FORMAT,
    output_dir: str = "./generated_images",
    download: bool = True,
) -> dict:
    if not prompt or len(prompt.strip()) == 0:
        raise ValueError("提示词不能为空")

    client = RotatingAPIClient(
        provider=AGENS_PROVIDER,
        api_key=api_key,
        api_keys=api_keys,
        timeout=120,
    )

    normalized_urls = normalize_image_urls(image_urls)
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
    }

    if normalized_urls:
        payload["extra_body"] = {
            "image": normalized_urls,
            "response_format": response_format,
        }

    print("🎨 正在调用 Agens-AI 图片生成 API...")
    print(f"   模型: {model}")
    print(f"   提示词: {prompt[:80]}...")
    print(f"   尺寸: {size}")
    print(f"   模式: {'图生图' if normalized_urls else '文生图'}")
    if normalized_urls:
        print(f"   参考图: {len(normalized_urls)} 张")

    result = client.request_json(
        method="POST",
        path="/images/generations",
        json_body=payload,
        headers={"Content-Type": "application/json"},
        expected_statuses=(200,),
        timeout=120,
    )

    images = extract_image_urls(result.data)
    if not images:
        raise Exception("Agens-AI 未返回图片 URL")

    downloaded_files = []
    if download:
        print(f"📥 正在下载 {len(images)} 张图片...")
        downloaded_files = download_files(
            urls=images,
            output_dir=output_dir,
            filename_prefix="agens_image_{model}".format(model=sanitize_filename(model)),
            default_extension=".png",
            timeout=60,
        )
        for file_path in downloaded_files:
            print(f"   ✅ 保存到: {file_path}")

    return {
        "success": True,
        "provider": AGENS_PROVIDER.name,
        "model": model,
        "prompt": prompt,
        "count": len(images),
        "images": images,
        "downloaded": download,
        "downloaded_files": downloaded_files,
        "output_dir": output_dir if download else None,
        "mode": "image-to-image" if normalized_urls else "text-to-image",
        "input_images": normalized_urls,
        "api_key_index": result.api_key_index,
        "api_key_mask": result.api_key_mask,
        "raw": result.data,
    }


def main():
    parser = argparse.ArgumentParser(description="Agens-AI 图片生成工具")
    parser.add_argument("--prompt", required=True, help="图片描述(必选)")
    parser.add_argument("--api-key", help="单个 API Key(也可设置 AGENS_AI_API_KEY / AGENS_API_KEY)")
    parser.add_argument("--api-keys", nargs="*", help="多个 API Key，支持空格分隔；也支持环境变量 AGENS_AI_API_KEYS / AGENS_API_KEYS")
    parser.add_argument("--model", default=DEFAULT_AGENS_IMAGE_MODEL, help=f"模型名称，默认 {DEFAULT_AGENS_IMAGE_MODEL}")
    parser.add_argument("--size", default=DEFAULT_SIZE, help=f"图片尺寸，默认 {DEFAULT_SIZE}")
    parser.add_argument("--image-url", dest="image_urls", action="append", help="图生图输入图片 URL，可重复传入多次")
    parser.add_argument("--response-format", default=DEFAULT_RESPONSE_FORMAT, choices=["url"], help="Agens-AI 当前推荐返回格式，默认 url")
    parser.add_argument("--output-dir", default="./generated_images", help="图片保存目录，默认 ./generated_images")
    parser.add_argument("--no-download", action="store_false", dest="download", help="不自动下载图片，只返回 URL")

    args = parser.parse_args()

    try:
        result = generate_agens_image(
            prompt=args.prompt,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            size=args.size,
            image_urls=args.image_urls,
            response_format=args.response_format,
            output_dir=args.output_dir,
            download=args.download,
        )

        print("\n✅ 图片生成成功!")
        print(f"   模型: {result['model']}")
        print(f"   模式: {result['mode']}")
        print(f"   数量: {result['count']}")
        print(f"   API Key: {result['api_key_mask']} (index={result['api_key_index']})")

        if not args.download:
            print("\n📸 图片 URL:")
            for index, url in enumerate(result["images"], 1):
                print(f"   {index}. {url}")

    except Exception as exc:
        print(f"\n❌ 错误: {str(exc)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
