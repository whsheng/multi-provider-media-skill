#!/usr/bin/env python3
"""
通义千问 Qwen-Image 文生图生成脚本
支持多 API Key 轮询与同步图片下载
"""

import os
import sys
import argparse
from typing import Optional, Sequence

# 添加技能目录到 Python 路径
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, skill_dir)

from skill_runtime.http import RotatingAPIClient
from skill_runtime.media import download_files, sanitize_filename
from skill_runtime.providers import QWEN_PROVIDER

# 默认配置
DEFAULT_MODEL = "qwen-image-2.0-pro"
DEFAULT_SIZE = "2048*2048"
DEFAULT_N = 1


def generate_qwen_image(
    prompt: str,
    api_key: Optional[str] = None,
    api_keys: Optional[Sequence[str]] = None,
    model: str = DEFAULT_MODEL,
    size: str = DEFAULT_SIZE,
    n: int = DEFAULT_N,
    negative_prompt: Optional[str] = None,
    prompt_extend: bool = True,
    watermark: bool = False,
    seed: Optional[int] = None,
    output_dir: str = "./generated_images",
    download: bool = True
) -> dict:
    """
    调用通义千问 Qwen-Image API 生成图片

    Args:
        prompt: 正向提示词,描述生成图像的内容
        api_key: 单个 API Key
        api_keys: 多个 API Key,支持列表或逗号分隔字符串
        model: 模型名称,默认 qwen-image-2.0-pro
        size: 图片尺寸,如 "2048*2048"
        n: 生成图片数量(1-6)
        negative_prompt: 负向提示词,排除不希望出现的内容
        prompt_extend: 是否开启提示词智能改写
        watermark: 是否添加 "Qwen-Image" 水印
        seed: 随机种子,用于控制生成结果
        output_dir: 图片保存目录(当 download=True 时生效)
        download: 是否自动下载生成的图片

    Returns:
        dict: 包含生成结果的字典,包括图片 URL 和可能的本地路径
    """
    # 验证参数
    if not prompt or len(prompt.strip()) == 0:
        raise ValueError("提示词不能为空")
    if len(prompt) > 800:
        raise ValueError(f"提示词过长,最多 800 字符,当前 {len(prompt)} 字符")
    if negative_prompt and len(negative_prompt) > 500:
        raise ValueError(f"负向提示词过长,最多 500 字符,当前 {len(negative_prompt)} 字符")
    if not 1 <= n <= 6:
        raise ValueError(f"生成数量必须在 1-6 之间,当前 {n}")

    client = RotatingAPIClient(
        provider=QWEN_PROVIDER,
        api_key=api_key,
        api_keys=api_keys,
        timeout=60,
    )

    # 请求体
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ]
        },
        "parameters": {
            "size": size,
            "n": n,
            "prompt_extend": prompt_extend,
            "watermark": watermark
        }
    }

    # 添加可选参数
    if negative_prompt:
        payload["parameters"]["negative_prompt"] = negative_prompt
    if seed is not None:
        payload["parameters"]["seed"] = seed

    print(f"🎨 正在调用 Qwen-Image API...")
    print(f"   模型: {model}")
    print(f"   提示词: {prompt[:50]}...")
    print(f"   尺寸: {size}")
    print(f"   数量: {n}")

    result = client.request_json(
        method="POST",
        path="/services/aigc/multimodal-generation/generation",
        json_body=payload,
        headers={"Content-Type": "application/json"},
        expected_statuses=(200,),
    )

    # 提取图片 URL
    images = []
    choices = result.data.get("output", {}).get("choices", [])

    for choice in choices:
        image_url = choice.get("message", {}).get("content", [{}])[0].get("image", "")
        if image_url:
            images.append(image_url)

    downloaded_files = []
    if download and images:
        print(f"📥 正在下载 {len(images)} 张图片...")
        downloaded_files = download_files(
            urls=images,
            output_dir=output_dir,
            filename_prefix="qwen_{model}".format(model=sanitize_filename(model)),
            default_extension=".png",
            timeout=30,
        )
        for file_path in downloaded_files:
            print(f"   ✅ 保存到: {file_path}")

    return {
        "success": True,
        "model": model,
        "prompt": prompt,
        "count": len(images),
        "images": images,
        "usage": result.data.get("usage", {}),
        "downloaded": download,
        "downloaded_files": downloaded_files,
        "output_dir": output_dir if download else None,
        "provider": QWEN_PROVIDER.name,
        "api_key_index": result.api_key_index,
        "api_key_mask": result.api_key_mask,
    }


def main():
    parser = argparse.ArgumentParser(description="通义千问 Qwen-Image 文生图生成工具")
    parser.add_argument("--prompt", required=True, help="图片描述(必选)")
    parser.add_argument("--api-key", help="单个 API Key(也可设置 DASHSCOPE_API_KEY / QWEN_API_KEY)")
    parser.add_argument("--api-keys", nargs="*", help="多个 API Key，支持空格分隔；也支持环境变量 DASHSCOPE_API_KEYS / QWEN_API_KEYS")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名称,默认 {DEFAULT_MODEL}")
    parser.add_argument("--size", default=DEFAULT_SIZE, help=f"图片尺寸,默认 {DEFAULT_SIZE}")
    parser.add_argument("--n", type=int, default=DEFAULT_N, help=f"生成数量(1-6),默认 {DEFAULT_N}")
    parser.add_argument("--negative-prompt", help="负向提示词,排除不希望出现的内容")
    parser.add_argument("--no-prompt-extend", action="store_false", dest="prompt_extend", help="关闭提示词智能改写")
    parser.add_argument("--watermark", action="store_true", help="添加 Qwen-Image 水印")
    parser.add_argument("--seed", type=int, help="随机种子,用于控制生成结果")
    parser.add_argument("--output-dir", default="./generated_images", help="图片保存目录,默认 ./generated_images")
    parser.add_argument("--no-download", action="store_false", dest="download", help="不自动下载图片,只返回 URL")

    args = parser.parse_args()

    try:
        result = generate_qwen_image(
            prompt=args.prompt,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            size=args.size,
            n=args.n,
            negative_prompt=args.negative_prompt,
            prompt_extend=args.prompt_extend,
            watermark=args.watermark,
            seed=args.seed,
            output_dir=args.output_dir,
            download=args.download
        )

        print("\n✅ 图片生成成功!")
        print(f"   模型: {result['model']}")
        print(f"   数量: {result['count']}")
        print(f"   用量: {result['usage']}")
        print(f"   API Key: {result['api_key_mask']} (index={result['api_key_index']})")

        if not args.download:
            print("\n📸 图片 URL (24小时内有效):")
            for i, url in enumerate(result['images'], 1):
                print(f"   {i}. {url}")

        print("\n💡 提示: Qwen-Image 生成的图片 URL 24小时后失效,请及时下载保存!")

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
