"""
Media file download helpers.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urlparse

import requests


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or "asset"


def timestamp_token() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def download_file(
    url: str,
    output_dir: str,
    filename: Optional[str] = None,
    default_extension: str = ".bin",
    timeout: int = 60,
) -> str:
    os.makedirs(output_dir, exist_ok=True)

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    if not filename:
        filename = _filename_from_response(url, response.headers.get("Content-Type"), default_extension)

    output_path = Path(output_dir) / filename
    with open(output_path, "wb") as handle:
        handle.write(response.content)

    return str(output_path)


def download_files(
    urls: Iterable[str],
    output_dir: str,
    filename_prefix: str,
    default_extension: str,
    timeout: int = 60,
) -> List[str]:
    saved_files = []

    for index, url in enumerate(urls, 1):
        filename = "{prefix}_{timestamp}_{index}{ext}".format(
            prefix=sanitize_filename(filename_prefix),
            timestamp=timestamp_token(),
            index=index,
            ext=default_extension,
        )
        saved_files.append(
            download_file(
                url=url,
                output_dir=output_dir,
                filename=filename,
                default_extension=default_extension,
                timeout=timeout,
            )
        )

    return saved_files


def _filename_from_response(url: str, content_type: Optional[str], default_extension: str) -> str:
    parsed = urlparse(url)
    path_name = os.path.basename(parsed.path)
    base_name, extension = os.path.splitext(path_name)

    if extension:
        return sanitize_filename(path_name)

    if content_type:
        guessed = _extension_from_content_type(content_type)
        if guessed:
            return "{name}{ext}".format(
                name=sanitize_filename(base_name or "asset"),
                ext=guessed,
            )

    return "{name}{ext}".format(
        name=sanitize_filename(base_name or "asset"),
        ext=default_extension,
    )


def _extension_from_content_type(content_type: str) -> Optional[str]:
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
    }
    return mapping.get(content_type.split(";")[0].strip().lower())
