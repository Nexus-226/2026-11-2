"""Agent 的错误类型（工具与 Provider）。

错误码对齐 docs/API.md 的统一错误结构；工具/Provider 层抛出，由 Runtime/编排
捕获并映射为 ``ToolResult(status="error")`` 或明确的错误回复，不编造成功结果。
"""

from __future__ import annotations


class DomainError(Exception):
    """业务层可识别错误，例如宠物不存在。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ToolNotFoundError(Exception):
    """请求了未注册的工具。"""

    def __init__(self, name: str) -> None:
        super().__init__(f"未注册的工具: {name}")
        self.name = name


class ProviderError(Exception):
    """LLM Provider 调用失败（模型不可用、超时、连接失败等）。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
