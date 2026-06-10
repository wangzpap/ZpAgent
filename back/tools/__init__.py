"""
工具基类模块

统一导出 LangChain 的 @tool 装饰器和 BaseTool 类型，
方便其他模块引用。所有内置工具在 builtin_tools.py 中定义。
"""

from langchain_core.tools import tool, BaseTool

__all__ = ["tool", "BaseTool"]
