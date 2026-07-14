"""
会话概要信息（用于列表展示）

前端会话列表页面使用此模型展示每条会话的概要。
"""

from typing import Optional

from pydantic import BaseModel


class ConversationInfo(BaseModel):
    """
    会话概要信息（用于列表展示）

    前端会话列表页面使用此模型展示每条会话的概要。
    """
    id: str
    title: str = ""
    created_at: str   # ISO 格式时间字符串，如 "2024-06-17T14:30:00"
    updated_at: str
    pinned_at: Optional[str] = None  # 顶置时间（ISO 格式），None 表示未顶置
    message_count: int = 0  # 消息数量
