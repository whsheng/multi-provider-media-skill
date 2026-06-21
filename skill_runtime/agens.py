"""
Helpers for Agens-AI image and video payloads/responses.
"""

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .http import APIResponse, RotatingAPIClient

DEFAULT_AGENS_IMAGE_MODEL = "agnes-image-2.1-flash"
DEFAULT_AGENS_VIDEO_MODEL = "agnes-video-v2.0"
VIDEO_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def normalize_image_urls(image_urls: Optional[Sequence[str]]) -> List[str]:
    if not image_urls:
        return []
    return [url.strip() for url in image_urls if url and url.strip()]


def extract_image_urls(payload: Dict[str, Any]) -> List[str]:
    urls: List[str] = []

    for item in payload.get("data", []):
        if isinstance(item, dict):
            for key in ("url", "image_url"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    urls.append(value.strip())

    if urls:
        return urls

    for key in ("images", "image_urls"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    urls.append(item.strip())
                elif isinstance(item, dict):
                    for nested_key in ("url", "image_url"):
                        nested_value = item.get(nested_key)
                        if isinstance(nested_value, str) and nested_value.strip():
                            urls.append(nested_value.strip())

    if urls:
        return urls

    output = payload.get("output")
    if isinstance(output, dict):
        for key in ("images", "data"):
            value = output.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        urls.append(item.strip())
                    elif isinstance(item, dict):
                        for nested_key in ("url", "image_url"):
                            nested_value = item.get(nested_key)
                            if isinstance(nested_value, str) and nested_value.strip():
                                urls.append(nested_value.strip())

        for key in ("url", "image_url"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                urls.append(value.strip())

    if urls:
        return urls

    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("url", "image_url"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                urls.append(value.strip())

    return urls


def extract_video_url(payload: Dict[str, Any]) -> Optional[str]:
    candidates = [
        payload.get("video_url"),
        payload.get("url"),
        payload.get("remixed_from_video_id"),
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    output = payload.get("output")
    if isinstance(output, dict):
        for key in ("video_url", "url"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    result = payload.get("result")
    if isinstance(result, dict):
        for key in ("video_url", "url"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def extract_task_id(payload: Dict[str, Any]) -> Optional[str]:
    for key in ("task_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def wait_for_video_task(
    client: RotatingAPIClient,
    task_id: str,
    api_key_override: str,
    poll_interval: int,
    timeout: int,
) -> Tuple[APIResponse, List[Tuple[str, int]]]:
    started_at = time.time()
    status_updates: List[Tuple[str, int]] = []
    previous_marker: Optional[Tuple[str, int]] = None

    while True:
        result = client.request_json(
            method="GET",
            path="/videos/{task_id}".format(task_id=task_id),
            headers={"Content-Type": "application/json"},
            expected_statuses=(200,),
            api_key_override=api_key_override,
            timeout=60,
        )

        status = str(result.data.get("status", "unknown")).strip().lower()
        progress = _coerce_progress(result.data.get("progress"))
        marker = (status, progress)

        if marker != previous_marker:
            status_updates.append(marker)
            previous_marker = marker

        if status in VIDEO_TERMINAL_STATUSES:
            return result, status_updates

        if time.time() - started_at > timeout:
            raise TimeoutError(
                "视频任务等待超时: task_id={task_id}, timeout={timeout}s".format(
                    task_id=task_id,
                    timeout=timeout,
                )
            )

        time.sleep(max(1, poll_interval))


def _coerce_progress(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0
