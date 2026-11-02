"""LLM 配置读取（A 负责）。

从环境变量 / .env 读取模型供应商配置；真实密钥只放 .env，不提交到 Git。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # pragma: no cover - 仅本地加载 .env，生产用环境变量
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str


def load_llm_config() -> LLMConfig:
    return LLMConfig(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=os.getenv("LLM_MODEL", "qwen-plus"),
    )
