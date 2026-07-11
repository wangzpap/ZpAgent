"""
LLM 配置相关的数据模型

定义大模型配置的请求和响应结构，支持前端自定义 LLM 的 API 地址和密钥。
"""

from pydantic import BaseModel, Field


class LlmConfigRequest(BaseModel):
    """
    保存 LLM 配置的请求体

    前端通过 POST /api/config/llm 提交新的 LLM 配置，
    后端将对应字段写入 .env 文件。
    """
    base_url: str = Field(
        default="https://api.deepseek.com",
        description="API 基础地址（兼容 OpenAI 格式的服务地址）",
    )
    api_key: str = Field(
        default="",
        description="API 密钥（空字符串表示不修改现有密钥）",
    )
    model_name: str = Field(
        default="deepseek-v4-flash",
        description="模型名称",
    )


class LlmConfigResponse(BaseModel):
    """
    读取 LLM 配置的响应体

    返回当前的 LLM 配置信息，API 密钥做脱敏处理（仅显示前4位和后4位）。
    has_api_key 字段告知前端是否已配置密钥，用于 UI 状态判断。
    """
    base_url: str = Field(description="API 基础地址")
    api_key_masked: str = Field(description="脱敏后的 API 密钥")
    model_name: str = Field(description="模型名称")
    has_api_key: bool = Field(description="是否已配置 API 密钥")
