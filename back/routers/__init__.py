"""
路由模块入口

__init__.py 的作用：
  让 Python 将该目录识别为一个包（package）。
  其他模块可以通过 from routers import api 或 from routers.api import router 来引用。

所有 API 路由统一在 api.py 中定义，保持路由逻辑集中、易于管理。
"""
