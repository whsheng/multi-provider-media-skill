"""
HTTP client with provider-aware API key rotation.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import requests

from .key_pool import PersistentRoundRobin, mask_api_key, resolve_api_keys

DEFAULT_RETRYABLE_STATUS_CODES = (401, 403, 429, 500, 502, 503, 504)


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    single_key_envs: Tuple[str, ...]
    multi_key_envs: Tuple[str, ...]
    auth_header: str = "Authorization"
    auth_mode: str = "bearer"


@dataclass
class APIResponse:
    data: Any
    response: requests.Response
    api_key: str
    api_key_index: int
    api_key_mask: str


class APIRequestError(Exception):
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class RotatingAPIClient:
    def __init__(
        self,
        provider: ProviderConfig,
        api_key: Optional[str] = None,
        api_keys: Optional[Sequence[str]] = None,
        timeout: int = 60,
    ):
        self.provider = provider
        self.timeout = timeout
        self.keys = resolve_api_keys(
            single_api_key=api_key,
            multiple_api_keys=api_keys,
            single_env_names=provider.single_key_envs,
            multi_env_names=provider.multi_key_envs,
        )
        self.key_pool = PersistentRoundRobin(provider.name)

    def request_json(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        expected_statuses: Iterable[int] = (200,),
        retryable_statuses: Iterable[int] = DEFAULT_RETRYABLE_STATUS_CODES,
        api_key_override: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> APIResponse:
        expected_statuses = tuple(expected_statuses)
        retryable_statuses = tuple(retryable_statuses)

        if api_key_override:
            return self._request_once(
                method=method,
                path=path,
                api_key=api_key_override,
                api_key_index=self._api_key_index(api_key_override),
                json_body=json_body,
                params=params,
                headers=headers,
                expected_statuses=expected_statuses,
                timeout=timeout,
            )

        start_index = self.key_pool.reserve_start_index(self.keys)
        attempted_errors = []

        for offset in range(len(self.keys)):
            key_index = (start_index + offset) % len(self.keys)
            api_key = self.keys[key_index]

            try:
                result = self._request_once(
                    method=method,
                    path=path,
                    api_key=api_key,
                    api_key_index=key_index,
                    json_body=json_body,
                    params=params,
                    headers=headers,
                    expected_statuses=expected_statuses,
                    timeout=timeout,
                )
                self.key_pool.advance_after_success(self.keys, key_index)
                return result
            except requests.RequestException as exc:
                attempted_errors.append(
                    "Key {mask}: {error}".format(
                        mask=mask_api_key(api_key),
                        error=str(exc),
                    )
                )
                continue
            except APIRequestError as exc:
                if exc.status_code not in retryable_statuses or offset == len(self.keys) - 1:
                    raise exc

                attempted_errors.append(
                    "Key {mask}: HTTP {status} - {message}".format(
                        mask=mask_api_key(api_key),
                        status=exc.status_code,
                        message=str(exc),
                    )
                )

        raise APIRequestError(
            "{provider} 请求失败，已尝试 {count} 个 API Key: {details}".format(
                provider=self.provider.name,
                count=len(self.keys),
                details=" | ".join(attempted_errors) if attempted_errors else "未知错误",
            )
        )

    def _request_once(
        self,
        method: str,
        path: str,
        api_key: str,
        api_key_index: int,
        json_body: Optional[Dict[str, Any]],
        params: Optional[Dict[str, Any]],
        headers: Optional[Dict[str, str]],
        expected_statuses: Sequence[int],
        timeout: Optional[int],
    ) -> APIResponse:
        request_headers = dict(headers or {})
        request_headers.update(self._build_auth_headers(api_key))

        response = requests.request(
            method=method.upper(),
            url=self._make_url(path),
            headers=request_headers,
            json=json_body,
            params=params,
            timeout=timeout or self.timeout,
        )

        if response.status_code not in expected_statuses:
            raise APIRequestError(
                self._build_error_message(response),
                status_code=response.status_code,
                response_body=response.text,
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise APIRequestError(
                "API 返回了非 JSON 响应: {error}".format(error=str(exc)),
                status_code=response.status_code,
                response_body=response.text,
            )

        return APIResponse(
            data=data,
            response=response,
            api_key=api_key,
            api_key_index=api_key_index,
            api_key_mask=mask_api_key(api_key),
        )

    def _make_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return "{base}/{path}".format(
            base=self.provider.base_url.rstrip("/"),
            path=path.lstrip("/"),
        )

    def _build_auth_headers(self, api_key: str) -> Dict[str, str]:
        if self.provider.auth_mode == "bearer":
            return {self.provider.auth_header: "Bearer {key}".format(key=api_key)}
        if self.provider.auth_mode == "raw":
            return {self.provider.auth_header: api_key}
        raise ValueError("不支持的鉴权模式: {mode}".format(mode=self.provider.auth_mode))

    def _build_error_message(self, response: requests.Response) -> str:
        payload: Any = None

        try:
            payload = response.json()
        except ValueError:
            payload = response.text.strip()

        if isinstance(payload, dict):
            for key in ("message", "error_description", "detail", "error", "msg"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, dict):
                    nested_message = value.get("message") or value.get("detail")
                    if nested_message:
                        return str(nested_message)

            return json.dumps(payload, ensure_ascii=False)

        if payload:
            return str(payload)

        return "HTTP {status}".format(status=response.status_code)

    def _api_key_index(self, api_key: str) -> int:
        try:
            return self.keys.index(api_key)
        except ValueError:
            return -1
