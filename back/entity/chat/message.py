"""
单条对话消息

对齐 LangChain / OpenAI 的消息格式，支持四种角色：
  - system: 系统提示词（设定 AI 的角色和行为规则）
  - user: 用户输入
  - assistant: AI 回复（可携带 tool_calls，表示 AI 请求调用工具）
  - tool: 工具执行结果（携带 tool_call_id 关联到对应的工具调用）
"""

from typing import List, Optional, Dict, Any, Literal

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
