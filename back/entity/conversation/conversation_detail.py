"""
会话详情（包含完整消息历史）

点击某条会话后加载此模型，展示完整的对话内容。
messages 字段是 Message 对象的列表（Pydantic 支持嵌套模型）。
"""

from typing import List

from pydantic import BaseModel

from entity.chat.message import Message


class ConversationDetail(BaseModel):
    """
    会话详情（包含完整消息历史）

    点击某条会话后加载此模型，展示完整的对话内容。
    messages 字段是 Message 对象的列表（Pydantic 支持嵌套模型）。
    """
    id: str
    title: str
    # List[Message]: 嵌套的 Pydantic 模型列表
    # FastAPI 会自动将每个 Message 对象序列化为 JSON
    messages: List[Message]
    created_at: str
    updated_at: str
