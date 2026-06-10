"""
工具注册表

管理所有 LangChain 工具的注册、查询和格式转换，是工具系统的核心枢纽。
支持手动注册、批量加载、按名称查找、以及获取前端展示信息。
"""

import logging
from typing import Dict, List, Optional, Any

from langchain_core.tools import BaseTool

from tools.builtin_tools import BUILTIN_TOOLS

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表

    集中管理所有 LangChain 工具实例，支持：
      1. 手动注册单个工具（@tool 装饰器创建的对象）
      2. 批量加载内置工具
      3. 按名称查找工具
      4. 获取 bind_tools() 所需的 LangChain Tool 列表
      5. 获取前端展示用的工具信息
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具到注册表"""
        if tool.name in self._tools:
            logger.warning("工具 '%s' 已存在，将被覆盖", tool.name)
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """
        取消注册一个工具

        Returns:
            是否成功移除
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def register_builtin_tools(self) -> None:
        """批量注册所有内置示例工具"""
        for t in BUILTIN_TOOLS:
            self.register(t)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """根据名称获取工具实例，未找到返回 None"""
        return self._tools.get(name)

    def get_tools_by_names(self, names: List[str]) -> List[BaseTool]:
        """
        根据名称列表获取多个工具

        未找到的工具名称会记录警告日志，不会中断流程。
        """
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

    def get_langchain_tools(self, names: Optional[List[str]] = None) -> List[BaseTool]:
        """
        获取 LangChain Tool 对象列表，用于传递给 llm.bind_tools()

        Args:
            names: 指定的工具名称列表，为 None 则返回所有

        Returns:
            LangChain BaseTool 列表
        """
        if names:
            return self.get_tools_by_names(names)
        return self.get_all_tools()

    def get_tool_info_list(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的前端展示信息

        Returns:
            工具信息字典列表，每项包含 name、description、parameters
        """
        result = []
        for t in self.get_all_tools():
            # 从 LangChain Tool 的 args_schema 提取参数 JSON Schema
            try:
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
