"""
批量删除消息请求

前端 POST /api/conversations/{id}/messages/batch-delete 发送的数据结构。
单条删除只需传单元素数组即可。
"""

from typing import List

from pydantic import BaseModel, Field


class BatchDeleteRequest(BaseModel):
    """
    批量删除消息请求

    传入要删除的消息 ID 列表，后端会删除最早匹配消息及其之后的所有消息。
    """
    message_ids: List[str] = Field(
        ..., min_length=1, max_length=100,
        description="要删除的消息 ID 列表（至少1条，最多100条）",
    )
