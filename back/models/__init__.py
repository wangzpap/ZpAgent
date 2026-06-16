"""
数据模型定义

使用 Pydantic 定义 API 请求/响应的数据结构，
与 LangChain Message 体系对齐，同时兼容 OpenAI API 格式。

主要模型：
  - Message: 单条对话消息（对齐 LangChain 的 role/content/tool_calls 结构）
  - ChatRequest: 聊天请求（含消息、会话ID、选定工具）
  - ConversationInfo: 会话概要（列表展示）
  - ConversationDetail: 会话详情（含完整消息历史）
  - ToolInfo: 工具信息（前端展示）
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class Message(BaseModel):
    """
    单条对话消息

    对齐 LangChain / OpenAI 的消息格式，支持四种角色：
      - system: 系统提示词
      - user: 用户输入
      - assistant: AI 回复（可携带 tool_calls）
      - tool: 工具执行结果（携带 tool_call_id）
    """
    role: Literal["system", "user", "assistant", "tool"] = Field(
        ..., description="消息角色"
    )
    content: str = Field(default="", description="消息文本内容")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="LLM 发起的工具调用请求（OpenAI 格式）"
    )
    tool_call_id: Optional[str] = Field(
        default=None, description="工具执行结果对应的调用 ID"
    )
    name: Optional[str] = Field(
        default=None, description="工具名称（tool 角色消息使用）"
    )


class ChatRequest(BaseModel):
    """
    聊天请求模型

    前端发送的数据，包含用户消息、可选的会话 ID 和选定的工具列表。
    LangGraph Agent 根据 selected_tools 动态绑定工具子集。
    """
    message: str = Field(
        ..., min_length=1, max_length=10000,
        description="用户输入的消息（1~10000字符）",
    )
    conversation_id: Optional[str] = Field(
        default=None, description="会话 ID，为空则创建新会话"
    )
    selected_tools: List[str] = Field(
        default_factory=list, max_length=20,
        description="本次对话选用的工具名称列表（最多20个）",
    )


class ConversationInfo(BaseModel):
    """会话概要信息（用于列表展示）"""
    id: str
    title: str = ""
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetail(BaseModel):
    """会话详情（包含完整消息历史）"""
    id: str
    title: str
    messages: List[Message]
    created_at: str
    updated_at: str


class ToolInfo(BaseModel):
    """工具信息（返回给前端展示）"""
    name: str = Field(..., description="工具标识名")
    description: str = Field(..., description="工具功能描述")
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="工具参数的 JSON Schema"
    )
