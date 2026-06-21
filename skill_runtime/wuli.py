"""
Helpers for Wuli media generation, upload flow, and async task polling.
"""

import os
import struct
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse, urlunparse

import requests

from .http import APIResponse, APIRequestError, RotatingAPIClient
from .key_pool import mask_api_key
from .media import sanitize_filename

DEFAULT_WULI_IMAGE_MODEL = "Qwen Image Turbo"
DEFAULT_WULI_VIDEO_MODEL = "通义万相 2.2 Turbo"
DEFAULT_WULI_IMAGE_ASPECT_RATIO = "1:1"
DEFAULT_WULI_IMAGE_RESOLUTION = "2K"
DEFAULT_WULI_VIDEO_ASPECT_RATIO = "16:9"
DEFAULT_WULI_VIDEO_RESOLUTION = "720P"
DEFAULT_WULI_VIDEO_SECONDS = 5
DEFAULT_WULI_IMAGE_COUNT = 1
DEFAULT_WULI_POLL_INTERVAL = 4
DEFAULT_WULI_TIMEOUT = 600
WULI_TERMINAL_STATUSES = {"SUCCEED", "FAILED", "REVIEWFAILED", "TIMEOUT", "CANCELLED"}
WULI_FAILED_STATUSES = {"FAILED", "REVIEWFAILED", "TIMEOUT", "CANCELLED"}
REMOTE_DOWNLOAD_TIMEOUT = 120
UPLOAD_TIMEOUT = 300


def reserve_workflow_api_key(client: RotatingAPIClient) -> Tuple[str, int, str]:
    start_index = client.key_pool.reserve_start_index(client.keys)
    api_key = client.keys[start_index]
    return api_key, start_index, mask_api_key(api_key)


def mark_workflow_api_key_success(client: RotatingAPIClient, api_key_index: int) -> None:
    client.key_pool.advance_after_success(client.keys, api_key_index)


def wuli_predict_type_for_mode(mode: str) -> str:
    mapping = {
        "text-to-image": "TXT_2_IMG",
        "image-to-image": "REF_2_IMG",
        "text-to-video": "TXT_2_VIDEO",
        "image-to-video": "FF_2_VIDEO",
        "multi-image-video": "AUTO_VIDEO",
        "keyframe-video": "FLF_2_VIDEO",
    }
    try:
        return mapping[mode]
    except KeyError as exc:
        raise ValueError("Wuli 不支持的 mode: {mode}".format(mode=mode)) from exc


def normalize_urls(values: Optional[Sequence[str]]) -> List[str]:
    if not values:
        return []
    return [value.strip() for value in values if value and value.strip()]


def wait_for_wuli_task(
    client: RotatingAPIClient,
    record_id: str,
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
            path="/api/v1/platform/predict/query",
            params={"recordId": record_id},
            expected_statuses=(200,),
            api_key_override=api_key_override,
            timeout=60,
        )

        payload = ensure_wuli_success(result)
        status = str(payload.get("recordStatus", "")).strip().upper() or "UNKNOWN"
        progress = max_progress(payload.get("results"))
        marker = (status, progress)

        if marker != previous_marker:
            status_updates.append(marker)
            previous_marker = marker

        if status in WULI_TERMINAL_STATUSES:
            return result, status_updates

        if time.time() - started_at > timeout:
            raise TimeoutError(
                "Wuli 任务等待超时: recordId={record_id}, timeout={timeout}s".format(
                    record_id=record_id,
                    timeout=timeout,
                )
            )

        time.sleep(max(1, poll_interval))


def ensure_wuli_success(result: APIResponse) -> Dict[str, Any]:
    payload = result.data
    if not isinstance(payload, dict):
        raise APIRequestError("Wuli API 返回格式异常")

    code = payload.get("code")
    success = payload.get("success")
    if success is False or (code is not None and int(code) != 200):
        raise APIRequestError(
            payload.get("msg") or payload.get("message") or "Wuli API 请求失败",
            status_code=result.response.status_code,
            response_body=result.response.text,
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise APIRequestError("Wuli API 未返回 data 对象")

    return data


def collect_result_urls(payload: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        value = item.get("imageUrl")
        if isinstance(value, str) and value.strip():
            urls.append(value.strip())
    return urls


def collect_task_ids(payload: Dict[str, Any]) -> List[str]:
    task_ids: List[str] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        value = item.get("taskId")
        if isinstance(value, str) and value.strip():
            task_ids.append(value.strip())
    return task_ids


def collect_resource_ids(payload: Dict[str, Any]) -> List[str]:
    resource_ids: List[str] = []
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        value = item.get("imageId")
        if isinstance(value, str) and value.strip():
            resource_ids.append(value.strip())
    return resource_ids


def request_no_watermark_urls(
    client: RotatingAPIClient,
    api_key_override: str,
    task_ids: Sequence[str],
    resource_ids: Sequence[str],
) -> List[str]:
    body: Dict[str, Any]
    if resource_ids:
        body = {"resourceIdList": list(resource_ids)}
    elif task_ids:
        body = {"taskId": task_ids[0]}
    else:
        return []

    result = client.request_json(
        method="POST",
        path="/api/v1/platform/predict/noWatermarkImage",
        json_body=body,
        headers={"Content-Type": "application/json"},
        expected_statuses=(200,),
        api_key_override=api_key_override,
        timeout=60,
    )
    payload = ensure_wuli_success(result)

    url_list = payload.get("urlList")
    if isinstance(url_list, list):
        urls = [item.strip() for item in url_list if isinstance(item, str) and item.strip()]
        if urls:
            return urls

    single_url = payload.get("url")
    if isinstance(single_url, str) and single_url.strip():
        return [single_url.strip()]

    return []


def resolve_reference_images(
    client: RotatingAPIClient,
    image_urls: Optional[Sequence[str]],
    image_paths: Optional[Sequence[str]],
    api_key_override: Optional[str] = None,
) -> List[Dict[str, Any]]:
    references = []
    for image_url in normalize_urls(image_urls):
        public_url, width, height = upload_remote_asset(
            client=client,
            source_url=image_url,
            api_key_override=api_key_override,
        )
        references.append({"imageUrl": public_url, "width": width, "height": height})

    for image_path in normalize_paths(image_paths):
        public_url, width, height = upload_local_image(
            client=client,
            image_path=image_path,
            api_key_override=api_key_override,
        )
        references.append({"imageUrl": public_url, "width": width, "height": height})

    return references


def resolve_reference_videos(
    client: RotatingAPIClient,
    video_urls: Optional[Sequence[str]],
    video_paths: Optional[Sequence[str]],
    api_key_override: Optional[str] = None,
) -> List[Dict[str, str]]:
    references = []
    for video_url in normalize_urls(video_urls):
        public_url = upload_remote_video(
            client=client,
            source_url=video_url,
            api_key_override=api_key_override,
        )
        references.append({"imageUrl": public_url})

    for video_path in normalize_paths(video_paths):
        public_url = upload_local_video(
            client=client,
            video_path=video_path,
            api_key_override=api_key_override,
        )
        references.append({"imageUrl": public_url})

    return references


def upload_remote_asset(
    client: RotatingAPIClient,
    source_url: str,
    api_key_override: Optional[str] = None,
) -> Tuple[str, int, int]:
    response = requests.get(source_url, timeout=REMOTE_DOWNLOAD_TIMEOUT)
    response.raise_for_status()
    content = response.content

    width, height = image_dimensions_from_bytes(content)
    filename = build_remote_filename(
        source_url=source_url,
        content_type=response.headers.get("Content-Type"),
        data=content,
        fallback_stem="upload",
        default_extension=".png",
        media_kind="image",
    )
    public_url = upload_bytes(
        client=client,
        filename=filename,
        data=content,
        api_key_override=api_key_override,
    )
    return public_url, width, height


def upload_remote_video(
    client: RotatingAPIClient,
    source_url: str,
    api_key_override: Optional[str] = None,
) -> str:
    response = requests.get(source_url, timeout=REMOTE_DOWNLOAD_TIMEOUT)
    response.raise_for_status()
    filename = build_remote_filename(
        source_url=source_url,
        content_type=response.headers.get("Content-Type"),
        data=response.content,
        fallback_stem="upload",
        default_extension=".mp4",
        media_kind="video",
    )
    return upload_bytes(
        client=client,
        filename=filename,
        data=response.content,
        api_key_override=api_key_override,
    )


def upload_local_image(
    client: RotatingAPIClient,
    image_path: str,
    api_key_override: Optional[str] = None,
) -> Tuple[str, int, int]:
    with open(image_path, "rb") as handle:
        content = handle.read()

    width, height = image_dimensions_from_bytes(content)
    filename = ensure_filename_extension(
        os.path.basename(image_path) or "upload",
        detect_image_extension(content) or ".png",
    )
    public_url = upload_bytes(
        client=client,
        filename=filename,
        data=content,
        api_key_override=api_key_override,
    )
    return public_url, width, height


def upload_local_video(
    client: RotatingAPIClient,
    video_path: str,
    api_key_override: Optional[str] = None,
) -> str:
    with open(video_path, "rb") as handle:
        content = handle.read()

    filename = ensure_filename_extension(os.path.basename(video_path) or "upload", ".mp4")
    return upload_bytes(
        client=client,
        filename=filename,
        data=content,
        api_key_override=api_key_override,
    )


def upload_bytes(
    client: RotatingAPIClient,
    filename: str,
    data: bytes,
    api_key_override: Optional[str] = None,
) -> str:
    upload_url = request_upload_url(
        client=client,
        filename=filename,
        api_key_override=api_key_override,
    )

    response = requests.put(
        upload_url,
        data=data,
        headers={"Content-Type": "application/octet-stream"},
        timeout=UPLOAD_TIMEOUT,
    )
    response.raise_for_status()

    return strip_url_query(upload_url)


def request_upload_url(
    client: RotatingAPIClient,
    filename: str,
    api_key_override: Optional[str] = None,
) -> str:
    result = client.request_json(
        method="GET",
        path="/api/v1/platform/image/getUploadUrl",
        params={"filename": filename},
        expected_statuses=(200,),
        api_key_override=api_key_override,
        timeout=60,
    )
    payload = ensure_wuli_success(result)

    upload_url = payload.get("uploadUrl")
    if not isinstance(upload_url, str) or not upload_url.strip():
        raise APIRequestError("Wuli 未返回 uploadUrl")

    return upload_url.strip()


def strip_url_query(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def filename_from_url(url: str, fallback: str) -> str:
    path = urlparse(url).path
    base = os.path.basename(path)
    if base:
        return sanitize_filename(base)
    return fallback


def build_remote_filename(
    source_url: str,
    content_type: Optional[str],
    data: bytes,
    fallback_stem: str,
    default_extension: str,
    media_kind: str,
) -> str:
    base = filename_from_url(source_url, fallback=fallback_stem)
    extension = os.path.splitext(base)[1].lower()
    if extension:
        return base

    if media_kind == "image":
        detected_extension = detect_image_extension(data)
    else:
        detected_extension = detect_video_extension(content_type, source_url)

    return ensure_filename_extension(base, detected_extension or default_extension)


def ensure_filename_extension(filename: str, extension: str) -> str:
    safe_name = sanitize_filename(filename) or "upload"
    if os.path.splitext(safe_name)[1]:
        return safe_name
    normalized_extension = extension if extension.startswith(".") else ".{ext}".format(ext=extension)
    return "{name}{ext}".format(name=safe_name, ext=normalized_extension)


def image_dimensions_from_bytes(data: bytes) -> Tuple[int, int]:
    try:
        width, height = _image_dimensions_from_bytes(data)
    except Exception as exc:
        raise ValueError("无法解析参考图片尺寸: {error}".format(error=str(exc))) from exc

    if width <= 0 or height <= 0:
        raise ValueError("参考图片尺寸无效")

    return width, height


def detect_image_extension(data: bytes) -> Optional[str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return None


def detect_video_extension(content_type: Optional[str], source_url: str) -> Optional[str]:
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    content_type_mapping = {
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/x-msvideo": ".avi",
        "video/webm": ".webm",
    }
    if normalized_type in content_type_mapping:
        return content_type_mapping[normalized_type]

    extension = os.path.splitext(urlparse(source_url).path)[1].lower()
    if extension in {".mp4", ".mov", ".avi", ".webm"}:
        return extension

    return None


def _image_dimensions_from_bytes(data: bytes) -> Tuple[int, int]:
    if len(data) < 10:
        raise ValueError("图片数据过短")

    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height)

    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return int(width), int(height)

    if data.startswith(b"\xff\xd8"):
        return _jpeg_dimensions(data)

    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return _webp_dimensions(data)

    raise ValueError("暂不支持的图片格式")


def _jpeg_dimensions(data: bytes) -> Tuple[int, int]:
    index = 2
    length = len(data)

    while index + 1 < length:
        if data[index] != 0xFF:
            index += 1
            continue

        while index < length and data[index] == 0xFF:
            index += 1
        if index >= length:
            break

        marker = data[index]
        index += 1

        if marker in (0xD8, 0xD9):
            continue
        if index + 2 > length:
            break

        block_length = struct.unpack(">H", data[index : index + 2])[0]
        if block_length < 2 or index + block_length > length:
            break

        if marker in {
            0xC0, 0xC1, 0xC2, 0xC3,
            0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB,
            0xCD, 0xCE, 0xCF,
        }:
            if index + 7 > length:
                break
            height, width = struct.unpack(">HH", data[index + 3 : index + 7])
            return int(width), int(height)

        index += block_length

    raise ValueError("无法解析 JPEG 尺寸")


def _webp_dimensions(data: bytes) -> Tuple[int, int]:
    chunk_type = data[12:16]

    if chunk_type == b"VP8 " and len(data) >= 30:
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return int(width), int(height)

    if chunk_type == b"VP8L" and len(data) >= 25:
        bits = struct.unpack("<I", data[21:25])[0]
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return int(width), int(height)

    if chunk_type == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height

    raise ValueError("无法解析 WebP 尺寸")


def max_progress(results: Any) -> int:
    if not isinstance(results, list):
        return 0

    progress_values = []
    for item in results:
        if not isinstance(item, dict):
            continue
        progress = item.get("progress")
        if isinstance(progress, int):
            progress_values.append(progress)
        elif isinstance(progress, float):
            progress_values.append(int(progress))
        elif isinstance(progress, str):
            try:
                progress_values.append(int(float(progress)))
            except ValueError:
                continue

    return max(progress_values) if progress_values else 0


def infer_mode_from_predict_type(predict_type: Optional[str], image_count: int, video_count: int, media_type: Optional[str]) -> str:
    normalized = (predict_type or "").strip().upper()
    mapping = {
        "TXT_2_IMG": "text-to-image",
        "REF_2_IMG": "image-to-image",
        "TXT_2_VIDEO": "text-to-video",
        "FF_2_VIDEO": "image-to-video",
        "FLF_2_VIDEO": "keyframe-video",
        "AUTO_VIDEO": "multi-image-video" if image_count > 1 or video_count > 0 else "image-to-video",
    }
    if normalized in mapping:
        return mapping[normalized]

    if (media_type or "").strip().upper() == "VIDEO":
        return "text-to-video"
    return "text-to-image"


def normalize_paths(values: Optional[Sequence[str]]) -> List[str]:
    if not values:
        return []
    return [value.strip() for value in values if value and value.strip()]
