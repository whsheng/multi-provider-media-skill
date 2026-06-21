#!/usr/bin/env python3
"""
Agens-AI 视频生成脚本
支持文生视频、图生视频、多图视频与任务轮询
"""

import argparse
import os
import sys
from typing import Optional, Sequence

# 添加技能目录到 Python 路径
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, skill_dir)

from skill_runtime.agens import (
    DEFAULT_AGENS_VIDEO_MODEL,
    extract_task_id,
    extract_video_url,
    normalize_image_urls,
    wait_for_video_task,
)
from skill_runtime.http import RotatingAPIClient
from skill_runtime.media import download_file, sanitize_filename
from skill_runtime.providers import AGENS_PROVIDER

DEFAULT_WIDTH = 1152
DEFAULT_HEIGHT = 768
DEFAULT_NUM_FRAMES = 121
DEFAULT_FRAME_RATE = 24
DEFAULT_POLL_INTERVAL = 5
DEFAULT_TIMEOUT = 600


def _validate_num_frames(num_frames: int) -> None:
    if num_frames > 441:
        raise ValueError("num_frames 必须小于或等于 441")
    if num_frames < 1:
        raise ValueError("num_frames 必须大于 0")
    if (num_frames - 1) % 8 != 0:
        raise ValueError("num_frames 必须满足 8n + 1，例如 81、121、161、241、441")


def generate_agens_video(
    prompt: str,
    api_key: Optional[str] = None,
    api_keys: Optional[Sequence[str]] = None,
    model: str = DEFAULT_AGENS_VIDEO_MODEL,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    num_frames: int = DEFAULT_NUM_FRAMES,
    frame_rate: int = DEFAULT_FRAME_RATE,
    image_urls: Optional[Sequence[str]] = None,
    keyframes: bool = False,
    output_dir: str = "./generated_images",
    download: bool = True,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    if not prompt or len(prompt.strip()) == 0:
        raise ValueError("提示词不能为空")
    if width <= 0 or height <= 0:
        raise ValueError("width 和 height 必须大于 0")
    if frame_rate <= 0:
        raise ValueError("frame_rate 必须大于 0")
    _validate_num_frames(num_frames)

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
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
    }

    mode = "text-to-video"
    if len(normalized_urls) == 1:
        payload["image"] = normalized_urls[0]
        mode = "image-to-video"
    elif len(normalized_urls) > 1:
        payload["extra_body"] = {"image": normalized_urls}
        mode = "multi-image-video"
        if keyframes:
            payload["extra_body"]["mode"] = "keyframes"
            mode = "keyframe-video"

    print("🎬 正在调用 Agens-AI 视频生成 API...")
    print(f"   模型: {model}")
    print(f"   提示词: {prompt[:80]}...")
    print(f"   尺寸: {width}x{height}")
    print(f"   帧数: {num_frames}")
    print(f"   帧率: {frame_rate}")
    print(f"   模式: {mode}")
    if normalized_urls:
        print(f"   参考图: {len(normalized_urls)} 张")

    created = client.request_json(
        method="POST",
        path="/videos",
        json_body=payload,
        headers={"Content-Type": "application/json"},
        expected_statuses=(200,),
        timeout=120,
    )

    task_id = extract_task_id(created.data)
    if not task_id:
        raise Exception("Agens-AI 未返回 task_id")

    print(f"   任务ID: {task_id}")
    final_result, status_updates = wait_for_video_task(
        client=client,
        task_id=task_id,
        api_key_override=created.api_key,
        poll_interval=poll_interval,
        timeout=timeout,
    )

    for status, progress in status_updates:
        print(f"   状态: {status} ({progress}%)")

    final_status = str(final_result.data.get("status", "")).strip().lower()
    if final_status != "completed":
        raise Exception(
            "视频生成失败: status={status}, error={error}".format(
                status=final_status or "unknown",
                error=final_result.data.get("error"),
            )
        )

    video_url = extract_video_url(final_result.data)
    if not video_url:
        raise Exception("任务已完成，但未返回视频 URL")

    downloaded_file = None
    if download:
        filename = "{prefix}.mp4".format(
            prefix=sanitize_filename(
                "agens_video_{model}_{task_id}".format(model=model, task_id=task_id)
            )
        )
        print("📥 正在下载视频...")
        downloaded_file = download_file(
            url=video_url,
            output_dir=output_dir,
            filename=filename,
            default_extension=".mp4",
            timeout=120,
        )
        print(f"   ✅ 保存到: {downloaded_file}")

    return {
        "success": True,
        "provider": AGENS_PROVIDER.name,
        "model": model,
        "prompt": prompt,
        "task_id": task_id,
        "status": final_status,
        "progress": final_result.data.get("progress"),
        "video_url": video_url,
        "downloaded": download,
        "downloaded_file": downloaded_file,
        "output_dir": output_dir if download else None,
        "mode": mode,
        "input_images": normalized_urls,
        "seconds": final_result.data.get("seconds"),
        "size": final_result.data.get("size"),
        "api_key_index": created.api_key_index,
        "api_key_mask": created.api_key_mask,
        "raw_create": created.data,
        "raw_final": final_result.data,
        "status_updates": status_updates,
    }


def main():
    parser = argparse.ArgumentParser(description="Agens-AI 视频生成工具")
    parser.add_argument("--prompt", required=True, help="视频描述(必选)")
    parser.add_argument("--api-key", help="单个 API Key(也可设置 AGENS_AI_API_KEY / AGENS_API_KEY)")
    parser.add_argument("--api-keys", nargs="*", help="多个 API Key，支持空格分隔；也支持环境变量 AGENS_AI_API_KEYS / AGENS_API_KEYS")
    parser.add_argument("--model", default=DEFAULT_AGENS_VIDEO_MODEL, help=f"模型名称，默认 {DEFAULT_AGENS_VIDEO_MODEL}")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help=f"视频宽度，默认 {DEFAULT_WIDTH}")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help=f"视频高度，默认 {DEFAULT_HEIGHT}")
    parser.add_argument("--num-frames", type=int, default=DEFAULT_NUM_FRAMES, help=f"总帧数，默认 {DEFAULT_NUM_FRAMES}")
    parser.add_argument("--frame-rate", type=int, default=DEFAULT_FRAME_RATE, help=f"帧率，默认 {DEFAULT_FRAME_RATE}")
    parser.add_argument("--image-url", dest="image_urls", action="append", help="图生视频输入图片 URL，可重复传入多次")
    parser.add_argument("--keyframes", action="store_true", help="多图输入时使用关键帧模式")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL, help=f"轮询间隔秒数，默认 {DEFAULT_POLL_INTERVAL}")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"任务等待超时秒数，默认 {DEFAULT_TIMEOUT}")
    parser.add_argument("--output-dir", default="./generated_images", help="视频保存目录，默认 ./generated_images")
    parser.add_argument("--no-download", action="store_false", dest="download", help="不自动下载视频，只返回 URL")

    args = parser.parse_args()

    try:
        result = generate_agens_video(
            prompt=args.prompt,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            width=args.width,
            height=args.height,
            num_frames=args.num_frames,
            frame_rate=args.frame_rate,
            image_urls=args.image_urls,
            keyframes=args.keyframes,
            output_dir=args.output_dir,
            download=args.download,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )

        print("\n✅ 视频生成成功!")
        print(f"   模型: {result['model']}")
        print(f"   模式: {result['mode']}")
        print(f"   Task ID: {result['task_id']}")
        print(f"   状态: {result['status']}")
        print(f"   时长: {result['seconds']} 秒")
        print(f"   尺寸: {result['size']}")
        print(f"   API Key: {result['api_key_mask']} (index={result['api_key_index']})")

        if not args.download:
            print(f"\n🎞️ 视频 URL:\n   {result['video_url']}")

    except Exception as exc:
        print(f"\n❌ 错误: {str(exc)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
