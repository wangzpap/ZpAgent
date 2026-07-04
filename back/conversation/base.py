"""
会话存储抽象基类（策略接口）

定义会话元数据存储的统一接口，所有具体实现（内存、MySQL 等）必须继承此类。
这是策略模式（Strategy Pattern）中的"抽象策略"角色。

设计意图：
  - 面向接口编程（Program to an interface, not an implementation）
  - 上层业务代码（Agent）只依赖抽象基类，不关心底层存储细节
  - 新增存储后端（如 Redis、PostgreSQL）只需继承 ConversationStore 并实现所有方法
  - 通过工厂函数 create_conversation_store() 根据配置创建具体实例

会话元数据模型：
  {
      "id": str,           # 会话唯一标识（UUID 格式）
      "title": str,        # 会话标题（用于 UI 列表展示）
      "created_at": str,   # 创建时间（ISO 格式字符串）
      "updated_at": str,   # 最后更新时间（ISO 格式字符串）
  }
"""

# abc: Python 的抽象基类（Abstract Base Classes）模块
# ABC: 抽象基类，不能被直接实例化，只能被继承
# abstractmethod: 装饰器，标记子类必须实现的方法（类似 Java 的 interface 或 abstract 方法）
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class ConversationStore(ABC):
    """
    会话存储抽象基类（策略接口）

    定义了会话元数据管理的全部操作：创建、查询、更新标题、删除、检查存在性、
    更新时间戳。所有具体存储后端都必须继承此类并实现全部抽象方法。

    使用方式：
        # 上层代码只依赖抽象类型，不关心具体实现
        store: ConversationStore = create_conversation_store()
        conv_id = await store.create_conversation()

    扩展方式：
        # 新增 Redis 后端只需：
        class RedisConversationStore(ConversationStore):
            async def create_conversation(self) -> str: ...
            async def get_conversations(self) -> List[Dict]: ...
            # ... 实现所有抽象方法 ...
    """

    # ---- 初始化 / 销毁 ----

    async def initialize(self) -> None:
        """
        异步初始化钩子（可选覆写）

        用于执行需要 await 的初始化操作，如创建数据库连接池、建表等。
        默认实现为空（no-op），内存后端无需覆写。

        在应用启动时（lifespan 阶段）调用。
        """
        pass

    async def close(self) -> None:
        """
        异步关闭钩子（可选覆写）

        用于清理资源，如关闭数据库连接池。
        默认实现为空（no-op），内存后端无需覆写。

        在应用关闭时（lifespan 阶段）调用。
        """
        pass

    # ---- 核心 CRUD 操作 ----

    @abstractmethod
    async def create_conversation(self) -> str:
        """
        创建新会话，返回会话 ID

        实现要求：
          1. 生成 UUID 作为会话唯一标识
          2. 设置初始标题为 "新对话"
          3. 记录创建时间和更新时间（ISO 格式字符串）

        Returns:
            新创建的会话 ID（UUID 格式字符串）
        """
        ...

    @abstractmethod
    async def get_conversations(self) -> List[Dict[str, Any]]:
        """
        获取所有会话概要列表（按更新时间倒序）

        实现要求：
          - 返回每个会话的 id、title、created_at、updated_at
          - 按 updated_at 降序排列（最近更新的会话排在最前面）

        Returns:
            会话概要字典列表
        """
        ...

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个会话的元数据

        实现要求：
          - 返回会话信息字典的拷贝（防止外部修改内部数据）
          - 会话不存在时返回 None

        Args:
            conversation_id: 会话 ID

        Returns:
            会话信息字典或 None
        """
        ...

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除指定会话

        Args:
            conversation_id: 要删除的会话 ID

        Returns:
            True 表示删除成功，False 表示会话不存在
        """
        ...

    @abstractmethod
    async def conversation_exists(self, conversation_id: str) -> bool:
        """
        检查会话是否存在

        Args:
            conversation_id: 要检查的会话 ID

        Returns:
            True 表示存在，False 表示不存在
        """
        ...

    @abstractmethod
    async def update_title(self, conversation_id: str, title: str) -> None:
        """
        更新会话标题

        Args:
            conversation_id: 会话 ID
            title: 新的标题文本
        """
        ...

    @abstractmethod
    async def touch(self, conversation_id: str) -> None:
        """
        更新会话的 updated_at 时间戳为当前时间

        用途：每次对话结束后调用，让该会话在列表中排到最前面。
        类似 Linux 的 touch 命令更新文件修改时间。

        Args:
            conversation_id: 会话 ID
        """
        ...
