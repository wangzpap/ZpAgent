"""
服务层（Service Layer）

封装业务逻辑，隔离路由层与底层存储/文件操作的细节。
每个 Service 类职责单一，提供清晰的公共接口供路由调用。
"""

from services.config_service import ConfigService

__all__ = ["ConfigService"]
