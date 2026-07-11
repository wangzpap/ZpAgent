"""
公共数据模型

包含跨模块共享的通用数据模型，如统一 API 响应格式和 LLM 配置模型。
"""

from entity.common.api_response import ApiResponse
from entity.common.llm_config import LlmConfigRequest, LlmConfigResponse

__all__ = ["ApiResponse", "LlmConfigRequest", "LlmConfigResponse"]
