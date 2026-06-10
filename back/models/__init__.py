"""
数据模型定义

使用 Pydantic 定义所有 API 请求/响应的数据结构，
确保前后端数据交互的类型安全和输入校验。

LangChain 1.2 适配说明：
  - Message role 使用 Literal 类型约束
  - ChatRequest 增加消息长度校验
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


# ============================================
# 消息模型
# ============================================
class Message(BaseModel):
    """
    单条对话消息
    与 LangChain 的 Message 类型对应，同时兼容 OpenAI API 格式
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


# ============================================
# 聊天请求/响应
# ============================================
class ChatRequest(BaseModel):
    """聊天请求 - 前端发送的数据"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="用户输入的消息（1~10000字符）",
    )
    conversation_id: Optional[str] = Field(
        default=None, description="会话 ID，为空则创建新会话"
    )
    selected_tools: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="本次对话选用的工具名称列表（多选，最多20个）",
    )


class ChatResponse(BaseModel):
    """聊天响应 - 非流式场景使用"""
    conversation_id: str
    reply: str


# ============================================
# 会话模型
# ============================================
class ConversationInfo(BaseModel):
    """会话概要信息（列表展示）"""
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


# ============================================
# 工具信息
# ============================================
class ToolInfo(BaseModel):
    """工具信息 - 返回给前端展示"""
    name: str = Field(..., description="工具标识名")
    description: str = Field(..., description="工具功能描述")
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="工具参数的 JSON Schema"
    )
