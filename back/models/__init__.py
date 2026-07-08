"""
数据模型定义

使用 Pydantic 定义 API 请求/响应的数据结构，
与 LangChain Message 体系对齐，同时兼容 OpenAI API 格式。

Pydantic BaseModel 是什么？
  - Python 的数据校验框架（类似 Java 的 POJO + Bean Validation）
  - 定义类属性时指定类型，Pydantic 会自动进行类型转换和校验
  - 与 FastAPI 深度集成：请求体自动解析、响应自动序列化、自动生成 API 文档

主要模型：
  - Message: 单条对话消息（对齐 LangChain 的 role/content/tool_calls 结构）
  - ChatRequest: 聊天请求（含消息、会话ID、选定工具）
  - ConversationInfo: 会话概要（列表展示）
  - ConversationDetail: 会话详情（含完整消息历史）
  - ToolInfo: 工具信息（前端展示）
"""

# typing 模块是 Python 的类型注解标准库
# Literal: 限定值只能是指定的几个选项之一（如 role 只能是 "system"/"user"/"assistant"/"tool"）
from typing import List, Optional, Dict, Any, Literal
# BaseModel: Pydantic 的模型基类，继承后获得自动校验和序列化能力
# Field: 定义字段的默认值、校验规则和描述信息（类似 Java 的 @NotNull/@Size）
from pydantic import BaseModel, Field


class Message(BaseModel):
    """
    单条对话消息

    对齐 LangChain / OpenAI 的消息格式，支持四种角色：
      - system: 系统提示词（设定 AI 的角色和行为规则）
      - user: 用户输入
      - assistant: AI 回复（可携带 tool_calls，表示 AI 请求调用工具）
      - tool: 工具执行结果（携带 tool_call_id 关联到对应的工具调用）

    Pydantic 特性：
      创建实例时会自动校验类型，如 role="invalid" 会直接报错
    """
    # Literal[...] 限定 role 只能是这四个字符串之一，其他值会校验失败
    # ... 是 Pydantic 的特殊标记，表示该字段为必填项（不能省略）
    role: Literal["system", "user", "assistant", "tool"] = Field(
        ..., description="消息角色"
    )
    content: str = Field(default="", description="消息文本内容")
    # Optional[...] 表示该字段可以为 None（即前端可以不传）
    # tool_calls 格式: [{"id": "call_xxx", "name": "工具名", "args": {"参数名": "值"}}]
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="LLM 发起的工具调用请求（OpenAI 格式）"
    )
    # tool_call_id: 将工具执行结果与之前的 tool_calls 关联起来
    # 类似数据库的外键引用关系
    tool_call_id: Optional[str] = Field(
        default=None, description="工具执行结果对应的调用 ID"
    )
    name: Optional[str] = Field(
        default=None, description="工具名称（tool 角色消息使用）"
    )


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


class ConversationInfo(BaseModel):
    """
    会话概要信息（用于列表展示）

    前端会话列表页面使用此模型展示每条会话的概要。
    """
    id: str
    title: str = ""
    created_at: str   # ISO 格式时间字符串，如 "2024-06-17T14:30:00"
    updated_at: str
    message_count: int = 0  # 消息数量


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


from models.tool_info import ToolInfo  # noqa: F401  # 重新导出，保持向后兼容


class Decision(BaseModel):
    """
    单个人工审批决策

    前端审批面板提交的用户决策，对应 HITL 中间件的四种决策类型：
      - approve: 同意按原参数执行工具
      - edit:    修改工具参数后执行（需附带 edited_action）
      - reject:  拒绝执行（可附带 message 说明原因）
      - respond: 人工消息直接作为工具返回值（需附带 message）
    """
    # 决策类型：approve / edit / reject / respond
    type: Literal["approve", "edit", "reject", "respond"] = Field(
        ..., description="决策类型"
    )
    # edit 类型时使用：修改后的工具调用
    # 格式: {"name": "工具名", "args": {"参数名": "新值"}}
    edited_action: Optional[Dict[str, Any]] = Field(
        default=None, description="编辑后的工具调用（仅 edit 类型使用）"
    )
    # reject / respond 类型时使用：拒绝原因或人工回复
    message: Optional[str] = Field(
        default=None, description="拒绝原因或人工回复（reject/respond 类型使用）"
    )


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


class RenameRequest(BaseModel):
    """
    会话重命名请求

    前端 PATCH /api/conversations/{id} 发送的数据结构。
    title 长度限制 255 字符，与数据库 VARCHAR(255) 对齐。
    """
    title: str = Field(
        ..., min_length=1, max_length=255,
        description="新的会话标题（1~255字符）",
    )
