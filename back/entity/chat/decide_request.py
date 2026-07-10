"""
审批决策请求

前端 POST /api/chat/decide 发送的数据结构。
包含会话 ID 和对每个待审批工具的决策。
decisions 列表的顺序必须与 approval_required 事件中 actions 列表的顺序一致。
"""

from typing import List

from pydantic import BaseModel, Field

from entity.chat.decision import Decision


class DecideRequest(BaseModel):
    """
    审批决策请求

    前端 POST /api/chat/decide 发送的数据结构。
    包含会话 ID 和对每个待审批工具的决策。
    decisions 列表的顺序必须与 approval_required 事件中 actions 列表的顺序一致。
    """
    conversation_id: str = Field(
        ..., description="会话 ID（对应 checkpointer 中的 thread_id）"
    )
    decisions: List[Decision] = Field(
        ..., min_length=1, description="决策列表，顺序必须与 actions 列表一致"
    )
