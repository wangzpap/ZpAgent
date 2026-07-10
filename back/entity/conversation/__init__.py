"""
会话管理相关数据模型

包含会话概要、会话详情、重命名请求等与会话 CRUD 相关的 Pydantic 模型。
"""

from entity.conversation.conversation_info import ConversationInfo
from entity.conversation.conversation_detail import ConversationDetail
from entity.conversation.rename_request import RenameRequest

__all__ = ["ConversationInfo", "ConversationDetail", "RenameRequest"]
