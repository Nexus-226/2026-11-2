"""Provider 工厂：按配置构建默认 Provider（有 key 用 Qwen，否则用 Mock）。"""

from __future__ import annotations

from app.agent.config import load_llm_config
from app.agent.providers.base import LLMProvider
from app.agent.providers.mock import MockProvider
from app.agent.providers.qwen import QwenProvider


def build_default_provider() -> LLMProvider:
    config = load_llm_config()
    if config.api_key:
        return QwenProvider(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
        )
    return MockProvider()
