"""
API key resolution and persistent round-robin helpers.
"""

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

try:
    import fcntl
except ImportError:  # pragma: no cover - not expected on macOS/Linux
    fcntl = None

KeyInput = Union[str, Sequence[str], None]
STATE_DIR = Path(__file__).resolve().parent.parent / ".runtime"
STATE_PATH = STATE_DIR / "key_pool_state.json"


def _split_key_string(value: str) -> List[str]:
    normalized = value.replace("\r", "\n").replace(";", "\n").replace(",", "\n")
    return [item.strip() for item in normalized.split("\n") if item.strip()]


def _collect_keys(value: KeyInput) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return _split_key_string(value)

    keys: List[str] = []
    for item in value:
        if item is None:
            continue
        if isinstance(item, str):
            keys.extend(_split_key_string(item))
        else:
            keys.append(str(item).strip())
    return [item for item in keys if item]


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []

    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)

    return result


def resolve_api_keys(
    single_api_key: Optional[str] = None,
    multiple_api_keys: KeyInput = None,
    single_env_names: Sequence[str] = (),
    multi_env_names: Sequence[str] = (),
) -> List[str]:
    """
    Resolve API keys from explicit arguments first, then environment variables.
    """
    explicit_values = _collect_keys(single_api_key) + _collect_keys(multiple_api_keys)
    if explicit_values:
        keys = _dedupe_preserve_order(explicit_values)
    else:
        env_values: List[str] = []
        for env_name in multi_env_names:
            env_values.extend(_collect_keys(os.getenv(env_name)))
        for env_name in single_env_names:
            env_values.extend(_collect_keys(os.getenv(env_name)))
        keys = _dedupe_preserve_order(env_values)

    if keys:
        return keys

    env_names = list(multi_env_names) + list(single_env_names)
    if env_names:
        raise ValueError(
            "API Key 未提供。请通过 --api-key / --api-keys 传入，"
            "或设置环境变量: {}".format(", ".join(env_names))
        )

    raise ValueError("API Key 未提供。请通过 --api-key / --api-keys 传入。")


def mask_api_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return "{prefix}...{suffix}".format(prefix=api_key[:4], suffix=api_key[-4:])


class PersistentRoundRobin:
    """
    Persist provider cursor across separate script invocations.
    """

    def __init__(self, provider_name: str, state_path: Path = STATE_PATH):
        self.provider_name = provider_name
        self.state_path = state_path

    def reserve_start_index(self, keys: Sequence[str]) -> int:
        if len(keys) <= 1:
            return 0

        fingerprint = self._fingerprint(keys)

        with self._locked_state() as state:
            provider_state = state.get(self.provider_name, {})
            cursor = provider_state.get("cursor", 0)

            if provider_state.get("fingerprint") != fingerprint or not isinstance(cursor, int):
                cursor = 0

            start_index = cursor % len(keys)
            state[self.provider_name] = {
                "fingerprint": fingerprint,
                "cursor": (start_index + 1) % len(keys),
            }

        return start_index

    def advance_after_success(self, keys: Sequence[str], used_index: int) -> None:
        if len(keys) <= 1:
            return

        fingerprint = self._fingerprint(keys)

        with self._locked_state() as state:
            provider_state = state.get(self.provider_name, {})
            if provider_state.get("fingerprint") != fingerprint:
                return

            state[self.provider_name] = {
                "fingerprint": fingerprint,
                "cursor": (used_index + 1) % len(keys),
            }

    def _fingerprint(self, keys: Sequence[str]) -> str:
        joined = "\n".join(keys).encode("utf-8")
        return hashlib.sha256(joined).hexdigest()

    @contextmanager
    def _locked_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.state_path, "a+", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

            try:
                handle.seek(0)
                raw = handle.read().strip()
                state = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                state = {}

            yield state

            handle.seek(0)
            handle.truncate()
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())

            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
