"""
工具注册表

管理所有 LangChain 工具的注册与查询，是工具系统的核心枢纽。

注册表模式（Registry Pattern）是什么？
  - 用一个中央对象统一管理同类资源（这里是工具）
  - 提供注册、查找、删除等标准接口
  - 好处：解耦工具的注册方和使用方，便于动态增删工具

支持：手动注册、批量加载内置工具、按名称查找、获取前端展示信息，
     以及 Human-in-the-Loop 审批策略配置。
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
      - get_tool_info_list: 获取前端展示用的工具信息
      - get_interrupt_on_map: 获取 HITL 中间件的审批策略配置

    数据结构：
      _tools: 字典，key=工具名称, value=BaseTool 对象
      _builtin_names: 集合，记录内置工具的名称，用于区分内置和 MCP 工具
      _approval_config: 字典，key=工具名称, value=审批策略
    """

    def __init__(self):
        """初始化工具注册表"""
        self._tools: Dict[str, BaseTool] = {}
        self._builtin_names: set = set()
        # ---- 工具中文显示名称 ----
        # key=工具标识名, value=前端展示的中文名称
        # 由 register_builtin_tools() 和 register_mcp_tools() 设置
        self._display_names: Dict[str, str] = {}
        # ---- HITL 审批策略配置 ----
        # key=工具名称, value=审批策略，支持以下格式：
        #   False: 自动执行，无需人工干预（适合只读查询类工具）
        #   True:  需要人工审批，支持全部决策类型（approve/edit/reject/respond）
        #   dict:  精细配置，如 {"allowed_decisions": ["approve", "reject"]}
        #
        # 默认行为：
        #   - 内置工具 → False（自动执行）
        #   - MCP 工具 → True（需审批，因为外部工具能力未知）
        #   - 未在配置中的工具 → 中间件视为自动通过
        self._approval_config: Dict[str, Any] = {}

    def register(self, tool: BaseTool) -> None:
        """
        注册一个工具到注册表

        如果同名工具已存在，会被覆盖并记录警告日志。

        Args:
            tool: BaseTool 实例（@tool 装饰器创建或 MCP 加载的工具）
        """
        if tool.name in self._tools:
            logger.warning("工具 '%s' 已存在，将被覆盖", tool.name)
        self._tools[tool.name] = tool

    def register_builtin_tools(self) -> None:
        """
        批量注册所有内置工具

        内置工具（get_datetime, base64_tool）默认自动执行。
        get_datetime 设为需要审批，用于演示 HITL 流程。
        """
        # 需要人工审批的内置工具（演示用：查询时间需要审批确认）
        require_approval_tools = {"get_datetime"}

        # 内置工具的中文显示名称（前端展示用）
        builtin_display_names = {
            "get_datetime": "当前时间",
            "base64_tool": "Base64编解码",
        }

        for t in BUILTIN_TOOLS:
            self.register(t)
            self._builtin_names.add(t.name)
            # 设置中文显示名称
            if t.name in builtin_display_names:
                self._display_names[t.name] = builtin_display_names[t.name]
            if t.name in require_approval_tools:
                # True = 需要审批，支持全部决策类型（approve/edit/reject/respond）
                self._approval_config[t.name] = True
            else:
                # False = 自动执行，无需人工干预
                self._approval_config[t.name] = False

    def register_mcp_tools(self, tools: List[BaseTool]) -> None:
        """
        批量注册 MCP 工具（来自外部 MCP 服务器）

        MCP 工具的能力未知（可能包含写操作），默认需要人工审批。
        可通过 set_approval() 方法覆盖特定工具的审批策略。

        Args:
            tools: 从 MCP 服务器加载的 BaseTool 列表
        """
        for t in tools:
            self.register(t)
            # MCP 工具默认需要人工审批
            # True = HumanInTheLoopMiddleware 允许全部决策类型
            if t.name not in self._approval_config:
                self._approval_config[t.name] = True

    def set_approval(self, tool_name: str, policy) -> None:
        """
        设置单个工具的审批策略（覆盖默认值）

        用法示例：
          registry.set_approval("some_mcp_tool", False)   # 改为自动执行
          registry.set_approval("dangerous_tool", True)    # 全部决策类型
          registry.set_approval("sql_tool", {              # 精细配置
              "allowed_decisions": ["approve", "reject"]
          })

        Args:
            tool_name: 工具名称
            policy: 审批策略（False=自动 / True=全审批 / dict=精细配置）
        """
        self._approval_config[tool_name] = policy

    def clear_mcp_tools(self) -> int:
        """
        清除所有 MCP 工具（保留内置工具），用于热重载

        Returns:
            被清除的工具数量
        """
        mcp_names = [name for name in self._tools if name not in self._builtin_names]
        for name in mcp_names:
            del self._tools[name]
            # 同步清除审批配置和显示名称
            self._approval_config.pop(name, None)
            self._display_names.pop(name, None)
        return len(mcp_names)

    def get_interrupt_on_map(self, selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        构建 HumanInTheLoopMiddleware 所需的 interrupt_on 配置字典

        interrupt_on 是 HITL 中间件的核心配置，决定了每个工具的审批行为：
          - 不在字典中的工具 → 自动执行（中间件的默认行为）
          - False → 自动执行（等价于不在字典中）
          - True  → 需要审批，支持全部决策类型
          - dict  → 精细控制，如 {"allowed_decisions": ["approve", "reject"]}

        本方法只返回需要审批的工具（policy 不为 False 的），
        自动执行的工具不需要出现在 interrupt_on 中。

        Args:
            selected_tools: 前端选用的工具名称列表。
                如果指定，只返回这些工具中需要审批的条目。

        Returns:
            interrupt_on 字典，可直接传给 HumanInTheLoopMiddleware
        """
        if selected_tools is not None:
            tool_names = selected_tools
        else:
            tool_names = list(self._tools.keys())

        result = {}
        for name in tool_names:
            policy = self._approval_config.get(name, False)
            # 只把需要审批的工具加入 interrupt_on
            if policy is not False:
                result[name] = policy

        return result

    def get_langchain_tools(self, names: Optional[List[str]] = None) -> List[BaseTool]:
        """
        获取 LangChain Tool 对象列表，用于传递给 Agent / bind_tools()

        Args:
            names: 指定的工具名称列表

        Returns:
            BaseTool 对象列表
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

        将 BaseTool 对象转换为前端友好的字典格式，
        包含工具名称、描述、参数 JSON Schema 和审批标记。

        Returns:
            工具信息字典列表
        """
        result = []
        for t in self._tools.values():
            try:
                schema = None
                if t.args_schema is not None:
                    if hasattr(t.args_schema, "model_json_schema"):
                        schema = t.args_schema.model_json_schema()
                    elif isinstance(t.args_schema, dict):
                        schema = t.args_schema
                    else:
                        schema = None
            except Exception as e:
                logger.warning("无法获取工具 '%s' 的参数 Schema: %s", t.name, e)
                schema = None

            # 审批策略：转为前端可理解的布尔值
            policy = self._approval_config.get(t.name, False)
            requires_approval = policy is not False

            # 中文显示名称：优先使用注册时设置的名称，否则回退到工具标识名
            display_name = self._display_names.get(t.name, t.name)

            result.append({
                "name": t.name,
                "display_name": display_name,
                "description": t.description,
                "parameters": schema,
                "requires_approval": requires_approval,
            })
        return result
