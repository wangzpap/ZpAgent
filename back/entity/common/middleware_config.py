"""
中间件配置相关的数据模型

定义摘要压缩等中间件配置的请求和响应结构。
前端通过 /api/config/middleware 接口读写这些配置。
"""

from pydantic import BaseModel, Field


class MiddlewareConfigRequest(BaseModel):
    """
    保存中间件配置的请求体

    前端通过 POST /api/config/middleware 提交新的中间件配置，
    后端将对应字段写入 .env 文件并热重载。
    """
    summary_enabled: bool = Field(
        default=False,
        description="是否启用摘要压缩中间件",
    )
    summary_model: str = Field(
        default="",
        description="摘要专用模型名称（空字符串表示复用主模型）",
    )
    summary_max_tokens: int = Field(
        default=4000, gt=0,
        description="触发摘要的 token 阈值",
    )
    summary_messages_to_keep: int = Field(
        default=20, gt=0,
        description="摘要后保留最近的消息条数",
    )


class MiddlewareConfigResponse(BaseModel):
    """
    读取中间件配置的响应体

    返回当前所有中间件的配置状态。
    未来新增中间件时在此扩展对应字段即可。
    """
    summary_enabled: bool = Field(description="摘要压缩是否启用")
    summary_model: str = Field(description="摘要专用模型（空=复用主模型）")
    summary_max_tokens: int = Field(description="触发摘要的 token 阈值")
    summary_messages_to_keep: int = Field(description="摘要后保留最近消息数")
