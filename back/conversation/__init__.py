"""
会话注册表模块

提供应用层的会话元数据管理（ConversationRegistry），
与 LangGraph checkpointer（InMemorySaver）协同工作。

双层架构：
  - LangGraph checkpointer（InMemorySaver）: 框架层，自动管理对话状态和消息历史
  - ConversationRegistry（本模块）: 应用层，管理会话元数据（标题、时间戳等）

对话消息的存取完全由 LangGraph checkpointer 负责，
本模块仅维护会话列表和标题等 UI 展示所需的元数据。
"""

# asyncio: Python 的异步 IO 库，提供 async/await 基础设施
# 本模块用到的 asyncio.Lock: 异步互斥锁，防止并发修改共享数据
import asyncio
# uuid: Python 标准库，用于生成唯一标识符（如 "550e8400-e29b-41d4-a716-446655440000"）
import uuid
# datetime: Python 的日期时间库
from datetime import datetime
from typing import Dict, List, Any, Optional


class ConversationRegistry:
    """
    会话注册表（应用层）

    仅管理会话元数据（标题、时间戳），不存储消息。
    消息历史由 LangGraph checkpointer 通过 thread_id 自动管理。

    数据结构:
        _conversations = {
            "uuid-string": {
                "id": str,           # 会话唯一标识
                "title": str,        # 会话标题（用于 UI 列表展示）
                "created_at": str,   # 创建时间（ISO 格式字符串）
                "updated_at": str,   # 最后更新时间（ISO 格式字符串）
            }
        }

    线程安全：
        使用 asyncio.Lock（异步互斥锁）保护 _conversations 字典，
        防止多个请求同时修改导致数据不一致。
        类似 Java 的 synchronized / ReentrantLock，但适配异步场景。
    """

    def __init__(self):
        """初始化空的会话字典和异步锁"""
        # 类型注解 Dict[str, Dict[str, Any]] 表示：
        #   外层 key 是会话 ID（str），value 是会话信息字典（Dict[str, Any]）
        self._conversations: Dict[str, Dict[str, Any]] = {}
        # asyncio.Lock: 异步互斥锁
        # 用法：async with self._lock: 进入临界区，同一时刻只有一个协程能进入
        # 为什么需要锁？asyncio 虽然是单线程的，但 await 会让出控制权，
        # 两个协程可能在 await 之间交错执行，导致数据不一致
        self._lock = asyncio.Lock()

    async def create_conversation(self) -> str:
        """
        创建新会话，返回会话 ID

        流程：
          1. 生成 UUID 作为会话唯一标识
          2. 获取当前时间作为创建/更新时间
          3. 在锁保护下将新会话写入字典

        Returns:
            新创建的会话 ID（UUID 格式字符串）
        """
        # uuid.uuid4() 生成随机 UUID，str() 转为字符串格式
        conv_id = str(uuid.uuid4())
        # datetime.now().isoformat() 获取当前时间并转为 ISO 格式字符串
        # 例如: "2024-06-17T14:30:00.123456"
        now = datetime.now().isoformat()
        # async with: Python 的异步上下文管理器
        # 作用：进入时获取锁，退出时自动释放锁（即使发生异常也会释放）
        # 类似 Java 的 synchronized 块或 Go 的 sync.Mutex + defer
        async with self._lock:
            self._conversations[conv_id] = {
                "id": conv_id,
                "title": "新对话",
                "created_at": now,
                "updated_at": now,
            }
        return conv_id

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """
        获取所有会话概要列表（按更新时间倒序）

        Returns:
            会话字典列表，每项包含 id、title、created_at、updated_at
            排序：updated_at 降序（最近更新的会话排在最前面）
        """
        async with self._lock:
            # 列表推导式：Python 的简洁写法，等价于 for 循环 + append
            # 这里只提取前端需要的字段，不暴露内部完整数据结构
            result = [
                {
                    "id": c["id"],
                    "title": c["title"],
                    "created_at": c["created_at"],
                    "updated_at": c["updated_at"],
                }
                for c in self._conversations.values()
            ]
        # sort(): 原地排序列表
        # key=lambda x: x["updated_at"]: 按 updated_at 字段排序
        # lambda: Python 的匿名函数（单行表达式函数），类似 Java 的 lambda 或 JS 的箭头函数
        # reverse=True: 降序排列（最新的在前）
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取单个会话的元数据

        Args:
            conversation_id: 会话 ID

        Returns:
            会话信息字典的拷贝（防止外部修改内部数据）；不存在返回 None
        """
        async with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                # dict(conv): 创建一份浅拷贝，防止外部代码意外修改内部数据
                # 这是防御性编程的常见做法
                return dict(conv)
        return None

    async def delete_conversation(self, conversation_id: str) -> bool:
        """
        删除指定会话

        Args:
            conversation_id: 要删除的会话 ID

        Returns:
            True 表示删除成功，False 表示会话不存在
        """
        async with self._lock:
            if conversation_id in self._conversations:
                # del: Python 的删除语句，从字典中移除指定 key
                del self._conversations[conversation_id]
                return True
        return False

    async def conversation_exists(self, conversation_id: str) -> bool:
        """
        检查会话是否存在

        in 运算符: 检查 key 是否在字典中，类似 Java 的 HashMap.containsKey()

        Args:
            conversation_id: 要检查的会话 ID

        Returns:
            True 表示存在，False 表示不存在
        """
        async with self._lock:
            return conversation_id in self._conversations

    async def update_title(self, conversation_id: str, title: str) -> None:
        """
        更新会话标题

        Args:
            conversation_id: 会话 ID
            title: 新的标题文本
        """
        async with self._lock:
            if conversation_id in self._conversations:
                self._conversations[conversation_id]["title"] = title

    async def touch(self, conversation_id: str) -> None:
        """
        更新会话的 updated_at 时间戳为当前时间

        用途：每次对话结束后调用，让该会话在列表中排到最前面。
        类似 Linux 的 touch 命令更新文件修改时间。

        Args:
            conversation_id: 会话 ID
        """
        async with self._lock:
            if conversation_id in self._conversations:
                self._conversations[conversation_id]["updated_at"] = (
                    datetime.now().isoformat()
                )
