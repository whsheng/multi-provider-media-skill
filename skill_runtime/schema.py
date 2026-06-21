"""
Standard result schema for unified media generation output.
"""

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA_NAME = "multi-provider-media-skill.media-result.v1"


def infer_media_type(mode: str) -> str:
    return "video" if "video" in mode else "image"


def build_request_schema(
    provider: str,
    mode: str,
    args: Any,
) -> Dict[str, Any]:
    image_urls = list(getattr(args, "image_urls", None) or [])

    return {
        "provider": provider,
        "mode": mode,
        "media_type": infer_media_type(mode),
        "model": getattr(args, "model", None),
        "prompt": getattr(args, "prompt", None),
        "download": getattr(args, "download", None),
        "output_dir": getattr(args, "output_dir", None),
        "input_urls": image_urls,
        "options": {
            "size": getattr(args, "size", None),
            "n": getattr(args, "n", None),
            "sample_count": getattr(args, "sample_count", None),
            "negative_prompt": getattr(args, "negative_prompt", None),
            "prompt_extend": getattr(args, "prompt_extend", None),
            "watermark": getattr(args, "watermark", None),
            "seed": getattr(args, "seed", None),
            "response_format": getattr(args, "response_format", None),
            "width": getattr(args, "width", None),
            "height": getattr(args, "height", None),
            "num_frames": getattr(args, "num_frames", None),
            "frame_rate": getattr(args, "frame_rate", None),
            "poll_interval": getattr(args, "poll_interval", None),
            "timeout": getattr(args, "timeout", None),
        },
    }


def normalize_success_result(
    provider: str,
    mode: str,
    request: Dict[str, Any],
    provider_result: Dict[str, Any],
    logs: Sequence[str],
    include_provider_raw: bool = False,
) -> Dict[str, Any]:
    artifacts = _build_artifacts(provider, mode, provider_result)
    primary_artifact = artifacts[0] if artifacts else None

    task = None
    if infer_media_type(mode) == "video":
        task = {
            "task_id": provider_result.get("task_id"),
            "status": provider_result.get("status"),
            "progress": provider_result.get("progress"),
            "status_updates": provider_result.get("status_updates", []),
        }

    usage = provider_result.get("usage")

    return {
        "schema": SCHEMA_NAME,
        "success": True,
        "provider": provider,
        "mode": mode,
        "media_type": infer_media_type(mode),
        "request": request,
        "result": {
            "status": provider_result.get("status", "completed"),
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
            "primary_artifact": primary_artifact,
            "task": task,
            "usage": usage if isinstance(usage, dict) else None,
            "provider_meta": {
                "provider_name": provider_result.get("provider"),
                "api_key_index": provider_result.get("api_key_index"),
                "api_key_mask": provider_result.get("api_key_mask"),
            },
            "provider_result": _build_provider_result(provider_result, include_provider_raw),
        },
        "error": None,
        "logs": list(logs),
    }


def normalize_error_result(
    provider: str,
    mode: str,
    request: Dict[str, Any],
    error: Exception,
    logs: Sequence[str],
) -> Dict[str, Any]:
    return {
        "schema": SCHEMA_NAME,
        "success": False,
        "provider": provider,
        "mode": mode,
        "media_type": infer_media_type(mode),
        "request": request,
        "result": None,
        "error": {
            "type": error.__class__.__name__,
            "message": str(error),
        },
        "logs": list(logs),
    }


def _build_artifacts(provider: str, mode: str, provider_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    media_type = infer_media_type(mode)

    if media_type == "video":
        artifact = {
            "index": 1,
            "media_type": "video",
            "url": provider_result.get("video_url"),
            "local_path": provider_result.get("downloaded_file"),
            "file_name": _artifact_name(
                provider_result.get("downloaded_file"),
                provider_result.get("video_url"),
            ),
            "width": _extract_video_dimensions(provider_result)[0],
            "height": _extract_video_dimensions(provider_result)[1],
            "duration_seconds": _coerce_float(provider_result.get("seconds")),
        }
        return [artifact]

    return _build_image_artifacts(provider, provider_result)


def _build_image_artifacts(provider: str, provider_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    urls: List[Optional[str]] = []
    local_paths: List[Optional[str]] = []

    if provider == "Gemini":
        local_paths = list(provider_result.get("images", []))
        urls = [None] * len(local_paths)
    else:
        urls = list(provider_result.get("images", []))
        downloaded_files = list(provider_result.get("downloaded_files", []))
        local_paths = downloaded_files + [None] * max(0, len(urls) - len(downloaded_files))

    width, height = _extract_image_dimensions(provider_result)
    artifacts = []

    for index, (url, local_path) in enumerate(_zip_with_padding(urls, local_paths), 1):
        artifacts.append(
            {
                "index": index,
                "media_type": "image",
                "url": url,
                "local_path": local_path,
                "file_name": _artifact_name(local_path, url),
                "width": width,
                "height": height,
                "duration_seconds": None,
            }
        )

    return artifacts


def _build_provider_result(
    provider_result: Dict[str, Any],
    include_provider_raw: bool,
) -> Dict[str, Any]:
    raw_payload = None

    if include_provider_raw:
        raw_payload = {
            key: value
            for key, value in provider_result.items()
            if key.startswith("raw")
        } or None

    return {
        "model": provider_result.get("model"),
        "prompt": provider_result.get("prompt"),
        "count": provider_result.get("count"),
        "mode": provider_result.get("mode"),
        "output_dir": provider_result.get("output_dir"),
        "raw": raw_payload,
    }


def _extract_image_dimensions(provider_result: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    usage = provider_result.get("usage")
    if isinstance(usage, dict):
        width = _coerce_int(usage.get("width"))
        height = _coerce_int(usage.get("height"))
        if width and height:
            return width, height

    size = provider_result.get("size")
    if isinstance(size, str):
        return _parse_size(size)

    raw = provider_result.get("raw")
    if isinstance(raw, dict):
        raw_size = raw.get("size")
        if isinstance(raw_size, str):
            return _parse_size(raw_size)

    return None, None


def _extract_video_dimensions(provider_result: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    size = provider_result.get("size")
    if isinstance(size, str):
        return _parse_size(size)

    width = _coerce_int(provider_result.get("width"))
    height = _coerce_int(provider_result.get("height"))
    if width and height:
        return width, height

    return None, None


def _parse_size(size: str) -> Tuple[Optional[int], Optional[int]]:
    normalized = size.strip().lower().replace("*", "x")
    if "x" not in normalized:
        return None, None

    left, right = normalized.split("x", 1)
    return _coerce_int(left), _coerce_int(right)


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _artifact_name(local_path: Optional[str], url: Optional[str]) -> Optional[str]:
    source = local_path or url
    if not source:
        return None
    return os.path.basename(source.split("?", 1)[0]) or None


def _zip_with_padding(left: Sequence[Optional[str]], right: Sequence[Optional[str]]) -> List[Tuple[Optional[str], Optional[str]]]:
    length = max(len(left), len(right))
    rows = []
    for index in range(length):
        rows.append(
            (
                left[index] if index < len(left) else None,
                right[index] if index < len(right) else None,
            )
        )
    return rows
