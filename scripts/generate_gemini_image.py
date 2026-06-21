#!/usr/bin/env python3
"""
Google Gemini Imagen 文生图生成脚本
支持多 API Key 轮询与本地图片保存
"""

import os
import sys
import argparse
import base64
from datetime import datetime
from typing import Optional, Sequence

# 添加技能目录到 Python 路径
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, skill_dir)

from skill_runtime.http import RotatingAPIClient
from skill_runtime.media import sanitize_filename
from skill_runtime.providers import GEMINI_PROVIDER

# 默认配置
DEFAULT_MODEL = "imagen-3.0-generate-002"
DEFAULT_SAMPLE_COUNT = 1


def generate_gemini_image(
    prompt: str,
    api_key: Optional[str] = None,
    api_keys: Optional[Sequence[str]] = None,
    model: str = DEFAULT_MODEL,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    output_dir: str = "./generated_images"
) -> dict:
    """
    调用 Google Gemini Imagen API 生成图片

    Args:
        prompt: 图片描述(支持英文)
        api_key: 单个 API Key
        api_keys: 多个 API Key,支持列表或逗号分隔字符串
        model: 模型名称,默认 imagen-3.0-generate-002
        sample_count: 生成图片数量(1-4)
        output_dir: 图片保存目录

    Returns:
        dict: 包含生成结果的字典,包括本地图片路径
    """
    # 验证参数
    if not prompt or len(prompt.strip()) == 0:
        raise ValueError("提示词不能为空")
    if not 1 <= sample_count <= 4:
        raise ValueError(f"生成数量必须在 1-4 之间,当前 {sample_count}")

    client = RotatingAPIClient(
        provider=GEMINI_PROVIDER,
        api_key=api_key,
        api_keys=api_keys,
        timeout=60,
    )

    # 请求体
    payload = {
        "instances": [
            {"prompt": prompt}
        ],
        "parameters": {
            "sampleCount": sample_count
        }
    }

    print(f"🎨 正在调用 Gemini Imagen API...")
    print(f"   模型: {model}")
    print(f"   提示词: {prompt[:50]}...")
    print(f"   数量: {sample_count}")

    result = client.request_json(
        method="POST",
        path="/models/{model}:predict".format(model=model),
        json_body=payload,
        headers={"Content-Type": "application/json"},
        expected_statuses=(200,),
    )

    # 提取图片数据(Base64)
    images = []
    predictions = result.data.get("predictions", [])

    if not predictions:
        raise Exception("API 返回结果中没有图片数据")

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 解码并保存图片
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i, prediction in enumerate(predictions):
        # Imagen 返回的格式可能是 bytesBase64String 或其他字段
        image_data = None

        # 尝试不同的可能字段名
        for field in ["bytesBase64String", "image_base64", "imageData"]:
            if field in prediction:
                image_data = prediction[field]
                break

        if not image_data:
            # 如果没有找到 Base64 字段,记录并跳过
            print(f"⚠️  第 {i+1} 张图片数据格式未知,响应内容: {prediction}")
            continue

        try:
            # 解码 Base64 数据
            image_bytes = base64.b64decode(image_data)

            # 保存图片
            filename = "imagen_{model}_{timestamp}_{index}.png".format(
                model=sanitize_filename(model),
                timestamp=timestamp,
                index=i + 1,
            )
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "wb") as f:
                f.write(image_bytes)

            images.append(filepath)
            print(f"📥 图片 {i+1}/{sample_count}: {filepath}")

        except Exception as e:
            print(f"⚠️  第 {i+1} 张图片保存失败: {str(e)}")

    return {
        "success": True,
        "model": model,
        "prompt": prompt,
        "count": len(images),
        "images": images,
        "output_dir": output_dir,
        "provider": GEMINI_PROVIDER.name,
        "api_key_index": result.api_key_index,
        "api_key_mask": result.api_key_mask,
    }


def main():
    parser = argparse.ArgumentParser(description="Google Gemini Imagen 文生图生成工具")
    parser.add_argument("--prompt", required=True, help="图片描述(推荐英文)")
    parser.add_argument("--api-key", help="单个 API Key(也可设置 GOOGLE_API_KEY / GEMINI_API_KEY)")
    parser.add_argument("--api-keys", nargs="*", help="多个 API Key，支持空格分隔；也支持环境变量 GOOGLE_API_KEYS / GEMINI_API_KEYS")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"模型名称,默认 {DEFAULT_MODEL}")
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT, help=f"生成数量(1-4),默认 {DEFAULT_SAMPLE_COUNT}")
    parser.add_argument("--output-dir", default="./generated_images", help="图片保存目录,默认 ./generated_images")

    args = parser.parse_args()

    try:
        result = generate_gemini_image(
            prompt=args.prompt,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            sample_count=args.sample_count,
            output_dir=args.output_dir
        )

        print("\n✅ 图片生成成功!")
        print(f"   模型: {result['model']}")
        print(f"   数量: {result['count']}")
        print(f"   保存目录: {result['output_dir']}")
        print(f"   API Key: {result['api_key_mask']} (index={result['api_key_index']})")

        print("\n💡 提示: Gemini Imagen 生成的图片包含 SynthID 数字水印")

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
