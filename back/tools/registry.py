"""
工具注册表

管理所有 LangChain 工具的注册与查询，是工具系统的核心枢纽。
支持手动注册、批量加载内置工具、按名称查找、以及获取前端展示信息。
"""

import logging
from typing import Dict, List, Optional, Any

from langchain.tools import BaseTool
from tools.builtin_tools import BUILTIN_TOOLS

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表

    集中管理所有 LangChain 工具实例（@tool 装饰器创建的对象），支持：
      - register: 手动注册单个工具
      - register_builtin_tools: 批量加载内置工具
      - get_langchain_tools: 获取用于 Agent bind_tools() 的工具列表
      - get_tool_info_list: 获取前端展示用的工具信息
    """

    def __init__(self):
        # 以工具名称为 key 的字典，快速查找
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具，同名工具会被覆盖并记录警告"""
        if tool.name in self._tools:
            logger.warning("工具 '%s' 已存在，将被覆盖", tool.name)
        self._tools[tool.name] = tool

    def register_builtin_tools(self) -> None:
        """批量注册所有内置工具"""
        for t in BUILTIN_TOOLS:
            self.register(t)

    def get_langchain_tools(self, names: Optional[List[str]] = None) -> List[BaseTool]:
        """
        获取 LangChain Tool 对象列表，用于传递给 Agent / bind_tools()

        Args:
            names: 指定的工具名称列表。
                   - None: 返回所有已注册工具（兼容未传参的场景）。
                   - 空列表 []: 表示用户未选择任何工具，返回空列表。
                   - 非空列表: 按名称查找，未找到的工具名会记录警告日志。
        """
        if names is None:
            return list(self._tools.values())
        tools = []
        for name in names:
            tool = self._tools.get(name)
            if tool:
                tools.append(tool)
            else:
                logger.warning("请求的工具 '%s' 未注册，已跳过", name)
        return tools

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有已注册的工具"""
        return list(self._tools.values())

    def get_tool_info_list(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的前端展示信息

        Returns:
            工具信息字典列表，每项包含 name、description、parameters (JSON Schema)
        """
        result = []
        for t in self._tools.values():
            try:
                # 从 LangChain Tool 的 args_schema 提取参数 JSON Schema
                schema = t.args_schema.model_json_schema() if t.args_schema else None
            except Exception as e:
                logger.warning("无法获取工具 '%s' 的参数 Schema: %s", t.name, e)
                schema = None

            result.append({
                "name": t.name,
                "description": t.description,
                "parameters": schema,
            })
        return result
