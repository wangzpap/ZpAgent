"""
聊天请求模型

前端 POST /api/chat 发送的数据结构。
FastAPI 会自动将 JSON 请求体解析为这个 Pydantic 模型。

如果前端发送的数据不符合校验规则（如 message 为空或超长），
FastAPI 会自动返回 422 错误（参数校验失败），不需要手动处理。
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    聊天请求模型

    前端 POST /api/chat 发送的数据结构。
    FastAPI 会自动将 JSON 请求体解析为这个 Pydantic 模型。

    如果前端发送的数据不符合校验规则（如 message 为空或超长），
    FastAPI 会自动返回 422 错误（参数校验失败），不需要手动处理。
    """
    # min_length/max_length: 字符串长度限制
    message: str = Field(
        ..., min_length=1, max_length=10000,
        description="用户输入的消息（1~10000字符）",
    )
    # conversation_id 为 None 时表示新建会话
    conversation_id: Optional[str] = Field(
        default=None, description="会话 ID，为空则创建新会话"
    )
    # default_factory=list: 默认值为空列表（注意不能用 default=[]，这是 Python 经典陷阱）
    # 原因：Python 中可变对象作为默认参数会被所有调用共享，导致意外行为
    # default_factory 每次创建实例时调用 list()，确保每个实例有独立的列表
    selected_tools: List[str] = Field(
        default_factory=list, max_length=20,
        description="本次对话选用的工具名称列表（最多20个）",
    )
