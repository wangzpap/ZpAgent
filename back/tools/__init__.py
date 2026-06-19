"""
工具模块入口

统一从 langchain.tools 导出 @tool 装饰器和 BaseTool 基类，
供项目内其他模块引用，避免直接依赖 langchain_core。

为什么要有这个中间层？
  这是一个"重导出"模式：
    - 其他模块只需 from tools import tool, BaseTool
    - 不需要知道底层来自哪个包
    - 如果将来换框架，只改这一处 import 就行

使用方式：
    from tools import tool, BaseTool
"""

# __all__: Python 的特殊变量，定义模块的公开接口
# 当其他地方使用 from tools import * 时，只会导入这里列出的名称
# 类似 Java 包中的 public 导出
from langchain.tools import tool, BaseTool

__all__ = ["tool", "BaseTool"]
