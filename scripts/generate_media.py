#!/usr/bin/env python3
"""
统一媒体生成入口
按 provider + mode 路由到具体实现
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List

# 添加技能目录到 Python 路径
skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, skill_dir)

from scripts.generate_agens_image import generate_agens_image
from scripts.generate_agens_video import generate_agens_video
from scripts.generate_gemini_image import generate_gemini_image
from scripts.generate_qwen_image import generate_qwen_image
from scripts.generate_wuli_media import generate_wuli_media

PROVIDER_CHOICES = ("qwen", "gemini", "agens", "wuli")
MODE_ALIASES = {
    "t2i": "text-to-image",
    "i2i": "image-to-image",
    "t2v": "text-to-video",
    "i2v": "image-to-video",
    "m2v": "multi-image-video",
    "kfv": "keyframe-video",
}


def canonical_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    return MODE_ALIASES.get(normalized, normalized)


def validate_provider_mode(provider: str, mode: str) -> None:
    supported = {
        "qwen": {"text-to-image"},
        "gemini": {"text-to-image"},
        "agens": {
            "text-to-image",
            "image-to-image",
            "text-to-video",
            "image-to-video",
            "multi-image-video",
            "keyframe-video",
        },
        "wuli": {
            "text-to-image",
            "image-to-image",
            "text-to-video",
            "image-to-video",
            "multi-image-video",
            "keyframe-video",
        },
    }

    if provider not in supported:
        raise ValueError("不支持的 provider: {provider}".format(provider=provider))
    if mode not in supported[provider]:
        raise ValueError(
            "provider={provider} 不支持 mode={mode}。支持: {modes}".format(
                provider=provider,
                mode=mode,
                modes=", ".join(sorted(supported[provider])),
            )
        )


def validate_provider_inputs(args: argparse.Namespace, provider: str, mode: str) -> None:
    image_urls = list(args.image_urls or [])
    image_paths = list(args.image_paths or [])
    video_urls = list(args.video_urls or [])
    video_paths = list(args.video_paths or [])

    image_ref_count = len(image_urls) + len(image_paths)
    video_ref_count = len(video_urls) + len(video_paths)
    total_ref_count = image_ref_count + video_ref_count

    if provider == "wuli":
        if mode == "text-to-image" and total_ref_count > 0:
            raise ValueError("provider=wuli, mode=text-to-image 不接受参考图片或视频")
        if mode == "image-to-image":
            if image_ref_count < 1:
                raise ValueError("provider=wuli, mode=image-to-image 至少需要 1 个 --image-url 或 --image-path")
            if video_ref_count > 0:
                raise ValueError("provider=wuli, mode=image-to-image 不接受 --video-url 或 --video-path")
        if mode == "text-to-video" and total_ref_count > 0:
            raise ValueError("provider=wuli, mode=text-to-video 不接受参考图片或视频")
        if mode == "image-to-video":
            if image_ref_count != 1:
                raise ValueError("provider=wuli, mode=image-to-video 需要且仅需要 1 个 --image-url 或 --image-path")
            if video_ref_count > 0:
                raise ValueError("provider=wuli, mode=image-to-video 不接受 --video-url 或 --video-path")
        if mode == "keyframe-video":
            if image_ref_count != 2:
                raise ValueError("provider=wuli, mode=keyframe-video 需要且仅需要 2 个 --image-url 或 --image-path")
            if video_ref_count > 0:
                raise ValueError("provider=wuli, mode=keyframe-video 不接受 --video-url 或 --video-path")
        if mode == "multi-image-video" and total_ref_count < 1:
            raise ValueError(
                "provider=wuli, mode=multi-image-video 至少需要 1 个参考素材："
                "--image-url / --image-path / --video-url / --video-path"
            )
        return

    if mode in {"image-to-image", "image-to-video"} and len(image_urls) < 1:
        raise ValueError("mode={mode} 至少需要 1 个 --image-url".format(mode=mode))
    if mode in {"multi-image-video", "keyframe-video"} and len(image_urls) < 2:
        raise ValueError("mode={mode} 至少需要 2 个 --image-url".format(mode=mode))


def dispatch(args: argparse.Namespace) -> Dict[str, Any]:
    provider = args.provider.strip().lower()
    mode = canonical_mode(args.mode)
    image_urls = args.image_urls or []

    validate_provider_mode(provider, mode)
    validate_provider_inputs(args, provider, mode)

    if provider == "gemini" and not args.download:
        raise ValueError("Gemini 当前只支持保存本地文件，不支持 --no-download")

    if provider == "qwen":
        return generate_qwen_image(
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
            download=args.download,
        )

    if provider == "gemini":
        return generate_gemini_image(
            prompt=args.prompt,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            sample_count=args.sample_count,
            output_dir=args.output_dir,
        )

    if provider == "agens" and mode in {"text-to-image", "image-to-image"}:
        return generate_agens_image(
            prompt=args.prompt,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            size=args.size,
            image_urls=image_urls if mode == "image-to-image" else None,
            response_format=args.response_format,
            output_dir=args.output_dir,
            download=args.download,
        )

    if provider == "agens" and mode in {
        "text-to-video",
        "image-to-video",
        "multi-image-video",
        "keyframe-video",
    }:
        return generate_agens_video(
            prompt=args.prompt,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            width=args.width,
            height=args.height,
            num_frames=args.num_frames,
            frame_rate=args.frame_rate,
            image_urls=image_urls if mode != "text-to-video" else None,
            keyframes=(mode == "keyframe-video"),
            output_dir=args.output_dir,
            download=args.download,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )

    if provider == "wuli":
        return generate_wuli_media(
            prompt=args.prompt,
            mode=mode,
            api_key=args.api_key,
            api_keys=args.api_keys,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            resolution=args.resolution,
            n=args.n,
            image_urls=image_urls,
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

    raise ValueError(
        "无法路由 provider={provider}, mode={mode}".format(
            provider=provider,
            mode=mode,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="统一媒体生成工具，按 provider + mode 调用 Qwen / Gemini / Agens-AI / Wuli"
    )
    parser.add_argument("--provider", required=True, choices=PROVIDER_CHOICES, help="服务商: qwen / gemini / agens / wuli")
    parser.add_argument("--mode", required=True, help="调用模式，如 text-to-image / image-to-video，也支持别名 t2i / i2v")
    parser.add_argument("--prompt", required=True, help="提示词")
    parser.add_argument("--api-key", help="单个 API Key")
    parser.add_argument("--api-keys", nargs="*", help="多个 API Key，支持空格分隔")
    parser.add_argument("--model", help="模型名称；不传则按 provider 使用默认模型")
    parser.add_argument("--output-dir", default="./generated_images", help="输出目录，默认 ./generated_images")
    parser.add_argument("--no-download", action="store_false", dest="download", help="不自动下载媒体，只返回 URL")
    parser.add_argument("--json", action="store_true", help="额外输出标准化 JSON 结果")

    # image / common
    parser.add_argument("--size", default="1024x1024", help="图片尺寸；Qwen 使用 2048*2048 这类格式，Agens 使用 1024x1024 / 1024x768 这类格式")
    parser.add_argument("--aspect-ratio", help="Wuli 画面比例，如 1:1 / 16:9 / 9:16")
    parser.add_argument("--resolution", help="Wuli 分辨率，如 2K / 4K / 720P / 1080P")
    parser.add_argument("--image-url", dest="image_urls", action="append", help="输入图片 URL，可重复传入")
    parser.add_argument("--image-path", dest="image_paths", action="append", help="Wuli 输入图片本地路径，可重复传入")
    parser.add_argument("--video-url", dest="video_urls", action="append", help="Wuli 输入视频 URL，可重复传入")
    parser.add_argument("--video-path", dest="video_paths", action="append", help="Wuli 输入视频本地路径，可重复传入")
    parser.add_argument("--response-format", default="url", choices=["url"], help="Agens 图片返回格式")

    # qwen
    parser.add_argument("--n", type=int, default=1, help="Qwen 生成数量")
    parser.add_argument("--negative-prompt", help="Qwen 负向提示词")
    parser.add_argument("--no-prompt-extend", action="store_false", dest="prompt_extend", help="Qwen: 关闭提示词智能改写")
    parser.add_argument("--watermark", action="store_true", help="Qwen: 添加水印")
    parser.add_argument("--seed", type=int, help="Qwen: 随机种子")

    # gemini
    parser.add_argument("--sample-count", type=int, default=1, help="Gemini 生成数量")

    # agens video
    parser.add_argument("--width", type=int, default=1152, help="Agens 视频宽度")
    parser.add_argument("--height", type=int, default=768, help="Agens 视频高度")
    parser.add_argument("--num-frames", type=int, default=121, help="Agens 视频总帧数")
    parser.add_argument("--frame-rate", type=int, default=24, help="Agens 视频帧率")
    parser.add_argument("--video-seconds", type=int, default=5, help="Wuli 视频时长秒数")
    parser.add_argument("--sound", dest="sound", action="store_true", help="Wuli 视频任务显式开启声音")
    parser.add_argument("--no-sound", dest="sound", action="store_false", help="Wuli 视频任务显式关闭声音")
    parser.add_argument("--poll-interval", type=int, default=5, help="Agens/Wuli 轮询间隔秒数")
    parser.add_argument("--timeout", type=int, default=600, help="Agens/Wuli 等待超时秒数")
    parser.add_argument("--no-optimize-prompt", action="store_false", dest="optimize_prompt", help="Wuli: 关闭提示词优化")
    parser.add_argument("--keep-watermark", action="store_false", dest="no_watermark", help="Wuli: 保留默认带水印结果 URL")

    parser.set_defaults(prompt_extend=True, download=True, optimize_prompt=True, no_watermark=True, sound=None)
    return parser


def apply_provider_defaults(args: argparse.Namespace) -> None:
    if args.model:
        return

    if args.provider == "qwen":
        args.model = "qwen-image-2.0-pro"
        if args.size == "1024x1024":
            args.size = "2048*2048"
    elif args.provider == "gemini":
        args.model = "imagen-3.0-generate-002"
    elif args.provider == "agens":
        mode = canonical_mode(args.mode)
        args.model = (
            "agnes-video-v2.0"
            if mode in {"text-to-video", "image-to-video", "multi-image-video", "keyframe-video"}
            else "agnes-image-2.1-flash"
        )
    elif args.provider == "wuli":
        mode = canonical_mode(args.mode)
        args.model = (
            "通义万相 2.2 Turbo"
            if mode in {"text-to-video", "image-to-video", "multi-image-video", "keyframe-video"}
            else "Qwen Image Turbo"
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    args.mode = canonical_mode(args.mode)
    apply_provider_defaults(args)

    try:
        result = dispatch(args)
        if args.json:
            print("\n📦 标准化结果(JSON):")
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print("\n❌ 错误: {message}".format(message=str(exc)), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
