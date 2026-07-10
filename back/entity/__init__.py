"""
数据模型定义（entity 包）

使用 Pydantic 定义 API 请求/响应的数据结构，
与 LangChain Message 体系对齐，同时兼容 OpenAI API 格式。

目录结构：
  chat/        — 聊天相关（Message、ChatRequest、Decision、DecideRequest）
  conversation/ — 会话管理（ConversationInfo、ConversationDetail、RenameRequest）
  tool/        — 工具相关（ToolInfo）
  common/      — 公共模型（ApiResponse）
"""

# ---- 聊天相关 ----
from entity.chat.message import Message
from entity.chat.chat_request import ChatRequest
from entity.chat.decision import Decision
from entity.chat.decide_request import DecideRequest

# ---- 会话管理 ----
from entity.conversation.conversation_info import ConversationInfo
from entity.conversation.conversation_detail import ConversationDetail
from entity.conversation.rename_request import RenameRequest

# ---- 工具 ----
from entity.tool.tool_info import ToolInfo

# ---- 公共 ----
from entity.common.api_response import ApiResponse

__all__ = [
    # chat
    "Message",
    "ChatRequest",
    "Decision",
    "DecideRequest",
    # conversation
    "ConversationInfo",
    "ConversationDetail",
    "RenameRequest",
    # tool
    "ToolInfo",
    # common
    "ApiResponse",
]
