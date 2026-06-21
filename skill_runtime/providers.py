"""
Provider configuration constants.
"""

from .http import ProviderConfig

QWEN_PROVIDER = ProviderConfig(
    name="Qwen",
    base_url="https://dashscope.aliyuncs.com/api/v1",
    single_key_envs=("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
    multi_key_envs=("DASHSCOPE_API_KEYS", "QWEN_API_KEYS"),
)

GEMINI_PROVIDER = ProviderConfig(
    name="Gemini",
    base_url="https://generativelanguage.googleapis.com/v1beta",
    single_key_envs=("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    multi_key_envs=("GOOGLE_API_KEYS", "GEMINI_API_KEYS"),
    auth_header="x-goog-api-key",
    auth_mode="raw",
)

AGENS_PROVIDER = ProviderConfig(
    name="Agens-AI",
    base_url="https://apihub.agnes-ai.com/v1",
    single_key_envs=("AGENS_AI_API_KEY", "AGENS_API_KEY"),
    multi_key_envs=("AGENS_AI_API_KEYS", "AGENS_API_KEYS"),
)
