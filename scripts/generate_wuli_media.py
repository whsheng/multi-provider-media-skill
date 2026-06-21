#!/usr/bin/env python3
"""
Wuli 图片/视频生成脚本
支持文生图、图生图、文生视频、图生视频、首尾帧视频与自动视频模式
"""

import argparse
import os
import sys
from typing import Optional, Sequence

# 添加技能目录到 Python 路径
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, skill_dir)

from skill_runtime.http import RotatingAPIClient
from skill_runtime.media import download_file, download_files, sanitize_filename
from skill_runtime.providers import WULI_PROVIDER
from skill_runtime.wuli import (
    DEFAULT_WULI_IMAGE_ASPECT_RATIO,
    DEFAULT_WULI_IMAGE_COUNT,
    DEFAULT_WULI_IMAGE_MODEL,
    DEFAULT_WULI_IMAGE_RESOLUTION,
    DEFAULT_WULI_POLL_INTERVAL,
    DEFAULT_WULI_TIMEOUT,
    DEFAULT_WULI_VIDEO_ASPECT_RATIO,
    DEFAULT_WULI_VIDEO_MODEL,
    DEFAULT_WULI_VIDEO_RESOLUTION,
    DEFAULT_WULI_VIDEO_SECONDS,
    WULI_FAILED_STATUSES,
    collect_resource_ids,
    collect_result_urls,
    collect_task_ids,
    ensure_wuli_success,
    infer_mode_from_predict_type,
    request_no_watermark_urls,
    reserve_workflow_api_key,
    resolve_reference_images,
    resolve_reference_videos,
    wait_for_wuli_task,
    wuli_predict_type_for_mode,
)


def generate_wuli_media(
    prompt: str,
    mode: str,
    api_key: Optional[str] = None,
    api_keys: Optional[Sequence[str]] = None,
    model: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    resolution: Optional[str] = None,
    n: int = DEFAULT_WULI_IMAGE_COUNT,
    image_urls: Optional[Sequence[str]] = None,
    image_paths: Optional[Sequence[str]] = None,
    video_urls: Optional[Sequence[str]] = None,
    video_paths: Optional[Sequence[str]] = None,
    video_seconds: int = DEFAULT_WULI_VIDEO_SECONDS,
    sound: Optional[bool] = None,
    negative_prompt: Optional[str] = None,
    seed: Optional[int] = None,
    optimize_prompt: bool = True,
    output_dir: str = "./generated_images",
    download: bool = True,
    no_watermark: bool = True,
    poll_interval: int = DEFAULT_WULI_POLL_INTERVAL,
    timeout: int = DEFAULT_WULI_TIMEOUT,
) -> dict:
    if not prompt or len(prompt.strip()) == 0:
        raise ValueError("提示词不能为空")
    if not 1 <= n <= 4:
        raise ValueError("Wuli 图片生成数量必须在 1-4 之间")
    if video_seconds <= 0:
        raise ValueError("video_seconds 必须大于 0")

    client = RotatingAPIClient(
        provider=WULI_PROVIDER,
        api_key=api_key,
        api_keys=api_keys,
        timeout=120,
    )

    predict_type = wuli_predict_type_for_mode(mode)
    media_type = "VIDEO" if "video" in mode else "IMAGE"
    default_model = DEFAULT_WULI_VIDEO_MODEL if media_type == "VIDEO" else DEFAULT_WULI_IMAGE_MODEL
    default_aspect_ratio = DEFAULT_WULI_VIDEO_ASPECT_RATIO if media_type == "VIDEO" else DEFAULT_WULI_IMAGE_ASPECT_RATIO
    default_resolution = DEFAULT_WULI_VIDEO_RESOLUTION if media_type == "VIDEO" else DEFAULT_WULI_IMAGE_RESOLUTION
    model = model or default_model
    aspect_ratio = aspect_ratio or default_aspect_ratio
    resolution = resolution or default_resolution

    print("🎨 正在调用 Wuli API..." if media_type == "IMAGE" else "🎬 正在调用 Wuli API...")
    print(f"   模型: {model}")
    print(f"   模式: {mode}")
    print(f"   画幅: {aspect_ratio}")
    print(f"   分辨率: {resolution}")
    if media_type == "IMAGE":
        print(f"   数量: {n}")
    else:
        print(f"   时长: {video_seconds} 秒")
    print(f"   提示词: {prompt[:80]}...")

    payload = {
        "modelName": model,
        "prompt": prompt,
        "mediaType": media_type,
        "predictType": predict_type,
        "aspectRatio": aspect_ratio,
        "resolution": resolution,
        "optimizePrompt": optimize_prompt,
    }

    if media_type == "IMAGE":
        payload["n"] = n
    else:
        payload["videoTotalSeconds"] = video_seconds
        if sound is not None:
            payload["sound"] = sound

    if negative_prompt:
        payload["negativePrompt"] = negative_prompt
    if seed is not None:
        payload["seed"] = seed
    last_error: Optional[Exception] = None
    input_images = []
    input_videos = []

    for attempt_index in range(len(client.keys)):
        workflow_api_key, workflow_api_key_index, workflow_api_key_mask = reserve_workflow_api_key(client)
        request_payload = dict(payload)

        try:
            input_images = resolve_reference_images(
                client=client,
                image_urls=image_urls,
                image_paths=image_paths,
                api_key_override=workflow_api_key,
            )
            if input_images:
                request_payload["inputImageList"] = input_images
                print(f"   参考图: {len(input_images)} 张")

            input_videos = resolve_reference_videos(
                client=client,
                video_urls=video_urls,
                video_paths=video_paths,
                api_key_override=workflow_api_key,
            )
            if input_videos:
                request_payload["inputVideoList"] = input_videos
                print(f"   参考视频: {len(input_videos)} 个")

            created = client.request_json(
                method="POST",
                path="/api/v1/platform/predict/submit",
                json_body=request_payload,
                headers={"Content-Type": "application/json"},
                expected_statuses=(200,),
                api_key_override=workflow_api_key,
                timeout=120,
            )
            created_payload = ensure_wuli_success(created)
            record_id = created_payload.get("recordId")
            if not isinstance(record_id, str) or not record_id.strip():
                raise Exception("Wuli 未返回 recordId")
            record_id = record_id.strip()
            api_key_override = workflow_api_key
            print(f"   任务ID: {record_id}")
            break
        except Exception as exc:
            last_error = exc
            if attempt_index == len(client.keys) - 1:
                raise
    else:  # pragma: no cover - defensive fallback
        raise last_error or RuntimeError("Wuli workflow failed without a captured error")

    final_result, status_updates = wait_for_wuli_task(
        client=client,
        record_id=record_id,
        api_key_override=api_key_override,
        poll_interval=poll_interval,
        timeout=timeout,
    )
    final_payload = ensure_wuli_success(final_result)
    client.key_pool.advance_after_success(client.keys, workflow_api_key_index)

    for status, progress in status_updates:
        print(f"   状态: {status} ({progress}%)")

    final_status = str(final_payload.get("recordStatus", "")).strip().upper()
    if final_status in WULI_FAILED_STATUSES:
        raise Exception(build_failure_message(final_payload, final_status))

    raw_urls = collect_result_urls(final_payload)
    task_ids = collect_task_ids(final_payload)
    resource_ids = collect_resource_ids(final_payload)
    urls = raw_urls
    if no_watermark:
        no_watermark_urls = request_no_watermark_urls(
            client=client,
            api_key_override=api_key_override,
            task_ids=task_ids,
            resource_ids=resource_ids,
        )
        if no_watermark_urls:
            urls = no_watermark_urls

    if not urls:
        raise Exception("Wuli 任务已完成，但未返回结果 URL")

    downloaded_files = []
    downloaded_file = None
    if download and media_type == "IMAGE":
        print(f"📥 正在下载 {len(urls)} 张图片...")
        downloaded_files = download_files(
            urls=urls,
            output_dir=output_dir,
            filename_prefix="wuli_{model}".format(model=sanitize_filename(model)),
            default_extension=".png",
            timeout=120,
        )
        for file_path in downloaded_files:
            print(f"   ✅ 保存到: {file_path}")
    elif download:
        filename = "{prefix}.mp4".format(
            prefix=sanitize_filename("wuli_{model}_{record_id}".format(model=model, record_id=record_id))
        )
        print("📥 正在下载视频...")
        downloaded_file = download_file(
            url=urls[0],
            output_dir=output_dir,
            filename=filename,
            default_extension=".mp4",
            timeout=120,
        )
        print(f"   ✅ 保存到: {downloaded_file}")

    gen_info = final_payload.get("genInfo") or {}
    inferred_mode = infer_mode_from_predict_type(
        predict_type=gen_info.get("predictType"),
        image_count=len(input_images),
        video_count=len(input_videos),
        media_type=final_payload.get("mediaType"),
    )

    return {
        "success": True,
        "provider": WULI_PROVIDER.name,
        "model": model,
        "prompt": prompt,
        "count": len(urls) if media_type == "IMAGE" else 1,
        "images": urls if media_type == "IMAGE" else [],
        "video_url": urls[0] if media_type == "VIDEO" else None,
        "downloaded": download,
        "downloaded_files": downloaded_files,
        "downloaded_file": downloaded_file,
        "output_dir": output_dir if download else None,
        "mode": inferred_mode,
        "task_id": record_id,
        "status": final_status.lower(),
        "progress": 100 if final_status == "SUCCEED" else None,
        "seconds": gen_info.get("videoTotalSeconds"),
        "size": "{width}x{height}".format(
            width=gen_info.get("width"),
            height=gen_info.get("height"),
        ) if gen_info.get("width") and gen_info.get("height") else None,
        "width": gen_info.get("width"),
        "height": gen_info.get("height"),
        "usage": created_payload.get("credit"),
        "api_key_index": workflow_api_key_index,
        "api_key_mask": workflow_api_key_mask,
        "raw_create": created.data,
        "raw_final": final_result.data,
        "status_updates": status_updates,
        "input_images": [item["imageUrl"] for item in input_images],
        "input_videos": [item["imageUrl"] for item in input_videos],
    }


def build_failure_message(final_payload: dict, final_status: str) -> str:
    errors = []
    for item in final_payload.get("results", []):
        if not isinstance(item, dict):
            continue
        error_msg = item.get("errorMsg")
        if isinstance(error_msg, str) and error_msg.strip():
            errors.append(error_msg.strip())

    if errors:
        return "Wuli 生成失败: status={status}, error={error}".format(
            status=final_status,
            error=" | ".join(errors),
        )

    return "Wuli 生成失败: status={status}".format(status=final_status)


def main():
    parser = argparse.ArgumentParser(description="Wuli 图片/视频生成工具")
    parser.add_argument("--prompt", required=True, help="提示词")
    parser.add_argument("--mode", required=True, help="模式，如 text-to-image / image-to-video")
    parser.add_argument("--api-key", help="单个 API Key(也可设置 WULI_API_KEY / WULI_API_TOKEN)")
    parser.add_argument("--api-keys", nargs="*", help="多个 API Key，也支持环境变量 WULI_API_KEYS / WULI_API_TOKENS")
    parser.add_argument("--model", help="模型名称；不传则按图片/视频使用默认模型")
    parser.add_argument("--aspect-ratio", help="画面比例，如 1:1 / 16:9 / 9:16")
    parser.add_argument("--resolution", help="分辨率，如 2K / 4K / 720P / 1080P")
    parser.add_argument("--n", type=int, default=DEFAULT_WULI_IMAGE_COUNT, help="图片生成数量(1-4)")
    parser.add_argument("--image-url", dest="image_urls", action="append", help="参考图片 URL，可重复传入")
    parser.add_argument("--image-path", dest="image_paths", action="append", help="参考图片本地路径，可重复传入")
    parser.add_argument("--video-url", dest="video_urls", action="append", help="参考视频 URL，可重复传入")
    parser.add_argument("--video-path", dest="video_paths", action="append", help="参考视频本地路径，可重复传入")
    parser.add_argument("--video-seconds", type=int, default=DEFAULT_WULI_VIDEO_SECONDS, help="视频时长(秒)")
    parser.add_argument("--sound", dest="sound", action="store_true", help="视频任务显式开启声音")
    parser.add_argument("--no-sound", dest="sound", action="store_false", help="视频任务显式关闭声音")
    parser.add_argument("--negative-prompt", help="反向提示词")
    parser.add_argument("--seed", type=int, help="随机种子")
    parser.add_argument("--no-optimize-prompt", action="store_false", dest="optimize_prompt", help="关闭提示词优化")
    parser.add_argument("--output-dir", default="./generated_images", help="输出目录")
    parser.add_argument("--no-download", action="store_false", dest="download", help="不自动下载媒体，只返回 URL")
    parser.add_argument("--keep-watermark", action="store_false", dest="no_watermark", help="不请求无水印结果")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_WULI_POLL_INTERVAL, help="轮询间隔秒数")
    parser.add_argument("--timeout", type=int, default=DEFAULT_WULI_TIMEOUT, help="任务等待超时秒数")
    parser.set_defaults(download=True, optimize_prompt=True, no_watermark=True, sound=None)

    args = parser.parse_args()

    try:
        result = generate_wuli_media(
            prompt=args.prompt,
            mode=args.mode,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            n=args.n,
            image_urls=args.image_urls,
            image_paths=args.image_paths,
            video_urls=args.video_urls,
            video_paths=args.video_paths,
            video_seconds=args.video_seconds,
            sound=args.sound,
            negative_prompt=args.negative_prompt,
            seed=args.seed,
            optimize_prompt=args.optimize_prompt,
            output_dir=args.output_dir,
            download=args.download,
            no_watermark=args.no_watermark,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )

        print("\n✅ Wuli 生成成功!")
        print(f"   模型: {result['model']}")
        print(f"   模式: {result['mode']}")
        print(f"   任务ID: {result['task_id']}")
        print(f"   状态: {result['status']}")
        print(f"   API Key: {result['api_key_mask']} (index={result['api_key_index']})")

        if not args.download and result["images"]:
            print("\n📸 图片 URL:")
            for index, url in enumerate(result["images"], 1):
                print(f"   {index}. {url}")
        if not args.download and result["video_url"]:
            print(f"\n🎞️ 视频 URL:\n   {result['video_url']}")

    except Exception as exc:
        print(f"\n❌ 错误: {str(exc)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
