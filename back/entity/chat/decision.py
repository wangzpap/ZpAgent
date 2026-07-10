"""
单个人工审批决策

前端审批面板提交的用户决策，对应 HITL 中间件的四种决策类型：
  - approve: 同意按原参数执行工具
  - edit:    修改工具参数后执行（需附带 edited_action）
  - reject:  拒绝执行（可附带 message 说明原因）
  - respond: 人工消息直接作为工具返回值（需附带 message）
"""

from typing import Optional, Dict, Any, Literal

from pydantic import BaseModel, Field


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
