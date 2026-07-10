"""
会话重命名请求

前端 POST /api/conversations/{id}/rename 发送的数据结构。
title 长度限制 255 字符，与数据库 VARCHAR(255) 对齐。
"""

from pydantic import BaseModel, Field


class RenameRequest(BaseModel):
    """
    会话重命名请求

    前端 POST /api/conversations/{id}/rename 发送的数据结构。
    title 长度限制 255 字符，与数据库 VARCHAR(255) 对齐。
    """
    title: str = Field(
        ..., min_length=1, max_length=255,
        description="新的会话标题（1~255字符）",
    )
