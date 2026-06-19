"""
工具注册表

管理所有 LangChain 工具的注册与查询，是工具系统的核心枢纽。

注册表模式（Registry Pattern）是什么？
  - 用一个中央对象统一管理同类资源（这里是工具）
  - 提供注册、查找、删除等标准接口
  - 好处：解耦工具的注册方和使用方，便于动态增删工具

支持：手动注册、批量加载内置工具、按名称查找、以及获取前端展示信息。
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
      - register_mcp_tools: 批量注册 MCP 外部工具
      - clear_mcp_tools: 清除 MCP 工具（保留内置），用于热重载
      - get_langchain_tools: 获取用于 Agent bind_tools() 的工具列表
      - get_tool_info_list: 获取前端展示用的工具信息（兼容 Pydantic / dict Schema）

    数据结构：
      _tools: 字典，key=工具名称, value=BaseTool 对象
      _builtin_names: 集合，记录内置工具的名称，用于区分内置和 MCP 工具
    """

    def __init__(self):
        """初始化工具注册表"""
        # 以工具名称为 key 的字典，用于 O(1) 时间复杂度的快速查找
        # O(1): 不管有多少工具，查找时间都是常数（字典/哈希表的优势）
        self._tools: Dict[str, BaseTool] = {}
        # set: Python 集合类型，元素唯一且查找速度极快
        # 记录内置工具名称，clear_mcp_tools 时用此区分内置和 MCP 工具
        self._builtin_names: set = set()

    def register(self, tool: BaseTool) -> None:
        """
        注册一个工具到注册表

        如果同名工具已存在，会被覆盖并记录警告日志。
        覆盖策略：后注册的优先（方便调试时临时替换工具）。

        Args:
            tool: BaseTool 实例（@tool 装饰器创建或 MCP 加载的工具）
        """
        if tool.name in self._tools:
            logger.warning("工具 '%s' 已存在，将被覆盖", tool.name)
        self._tools[tool.name] = tool

    def register_builtin_tools(self) -> None:
        """
        批量注册所有内置工具

        从 builtin_tools.py 导入的 BUILTIN_TOOLS 列表中逐个注册。
        同时将工具名记录到 _builtin_names 集合，用于后续区分。
        """
        for t in BUILTIN_TOOLS:
            self.register(t)
            # add(): 集合的添加方法，类似 Java Set.add()
            self._builtin_names.add(t.name)

    def register_mcp_tools(self, tools: List[BaseTool]) -> None:
        """
        批量注册 MCP 工具（来自外部 MCP 服务器）

        MCP 工具不加入 _builtin_names，这样 clear_mcp_tools 时只清除 MCP 工具。

        Args:
            tools: 从 MCP 服务器加载的 BaseTool 列表
        """
        for t in tools:
            self.register(t)

    def clear_mcp_tools(self) -> int:
        """
        清除所有 MCP 工具（保留内置工具），用于热重载

        工作原理：
          1. 遍历 _tools 中所有工具名
          2. 不在 _builtin_names 中的 → 是 MCP 工具 → 删除
          3. 在 _builtin_names 中的 → 是内置工具 → 保留

        这是"热重载"的关键步骤：先清除旧的，再加载新的。

        Returns:
            被清除的工具数量
        """
        # 列表推导式：筛选出所有 MCP 工具的名称
        mcp_names = [name for name in self._tools if name not in self._builtin_names]
        for name in mcp_names:
            del self._tools[name]
        return len(mcp_names)

    def get_langchain_tools(self, names: Optional[List[str]] = None) -> List[BaseTool]:
        """
        获取 LangChain Tool 对象列表，用于传递给 Agent / bind_tools()

        三种模式：
          - names=None → 返回所有已注册工具（兼容未传参的场景）
          - names=[]   → 用户未选择任何工具，返回空列表
          - names=["get_weather", ...] → 按名称查找，未找到的记录警告

        Args:
            names: 指定的工具名称列表

        Returns:
            BaseTool 对象列表
        """
        # None 表示参数未传入（前端没传 selected_tools 字段）
        if names is None:
            return list(self._tools.values())  # .values() 返回所有值，list() 转为列表
        tools = []
        for name in names:
            # .get(key): 字典安全取值，key 不存在时返回 None（不会报错）
            tool = self._tools.get(name)
            if tool:
                tools.append(tool)
            else:
                logger.warning("请求的工具 '%s' 未注册，已跳过", name)
        return tools

    def get_all_tools(self) -> List[BaseTool]:
        """
        获取所有已注册的工具

        Returns:
            所有 BaseTool 对象的列表
        """
        return list(self._tools.values())

    def get_tool_info_list(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的前端展示信息

        将 BaseTool 对象转换为前端友好的字典格式，
        包含工具名称、描述和参数的 JSON Schema。

        Schema 兼容处理：
          - Pydantic Model（内置工具）→ 调用 model_json_schema() 获取
          - 字典格式（MCP 工具）→ 直接使用
          - 其他格式 → 设为 None（前端不展示参数）

        Returns:
            工具信息字典列表，每项包含 name、description、parameters (JSON Schema)
        """
        result = []
        for t in self._tools.values():
            try:
                schema = None
                # args_schema: BaseTool 的属性，描述工具的参数结构
                if t.args_schema is not None:
                    if hasattr(t.args_schema, "model_json_schema"):
                        # hasattr: 检查对象是否有指定属性/方法
                        # model_json_schema(): Pydantic v2 方法，生成 JSON Schema
                        # 这是 @tool 装饰器创建的工具的 Schema 获取方式
                        schema = t.args_schema.model_json_schema()
                    elif isinstance(t.args_schema, dict):
                        # isinstance(x, dict): 检查 x 是否为字典类型
                        # MCP 工具的 Schema 通常已经是字典格式
                        schema = t.args_schema
                    else:
                        schema = None
            except Exception as e:
                # Schema 获取失败不影响其他工具，记录警告继续
                logger.warning("无法获取工具 '%s' 的参数 Schema: %s", t.name, e)
                schema = None

            result.append({
                "name": t.name,
                "description": t.description,
                "parameters": schema,
            })
        return result
