"""
工具模块入口

统一从 langchain.tools 导出 @tool 装饰器和 BaseTool 基类，
供项目内其他模块引用，避免直接依赖 langchain_core。

使用方式：
    from tools import tool, BaseTool
"""

from langchain.tools import tool, BaseTool

__all__ = ["tool", "BaseTool"]
