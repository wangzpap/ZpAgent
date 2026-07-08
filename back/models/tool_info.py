"""
工具信息模型

定义 GET /api/tools 接口返回的单个工具数据结构。
前端工具选择面板使用此模型展示可用工具列表，
通过 tool_type 和 server_name 区分内置工具与 MCP 外部工具。
"""

from typing import Optional, Dict, Any, Literal

from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    """
    工具信息（返回给前端展示）

    每个工具对应一个 ToolInfo 实例，包含工具的基本信息、
    参数 Schema、审批策略以及来源类型。

    字段说明：
      - name:            工具唯一标识，用于 selected_tools 匹配
      - display_name:    前端展示的中文名称
      - description:     工具功能描述
      - parameters:      工具参数的 JSON Schema（可选）
      - requires_approval: 是否需要人工审批
      - tool_type:       工具类型，inner_tool（内置）或 mcp（外部）
      - server_name:     MCP 服务器名称（仅 mcp 类型有值，内置工具为 null）
    """
    name: str = Field(..., description="工具标识名（唯一标识，用于 selected_tools 匹配）")
    display_name: str = Field(..., description="前端展示的中文名称")
    description: str = Field(..., description="工具功能描述（展示给用户看）")
    # parameters 是工具的参数 JSON Schema
    # 例如: {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}
    # 前端可以根据 Schema 动态生成参数输入表单
    parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="工具参数的 JSON Schema"
    )
    requires_approval: bool = Field(
        ..., description="是否需要人工审批（True=需审批，False=自动执行）"
    )
    tool_type: Literal["inner_tool", "mcp"] = Field(
        ..., description="工具类型：inner_tool（内置工具）或 mcp（MCP 外部工具）"
    )
    server_name: Optional[str] = Field(
        default=None, description="MCP 服务器名称（仅 mcp 类型有值，内置工具为 null）"
    )
