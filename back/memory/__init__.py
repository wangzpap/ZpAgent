"""
会话记忆模块

提供对话历史的存储与管理，采用抽象基类 + 内存实现的分层设计。
后续可扩展为 Redis、PostgreSQL、MongoDB 等持久化存储。

扩展方式：
    继承 BaseMemory，实现所有抽象方法，然后在 Agent 初始化时
    替换 InMemoryStore 为你的实现即可。
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from datetime import datetime
import uuid


# ============================================
# 抽象基类（定义存储接口）
# ============================================
class BaseMemory(ABC):
    """
    会话记忆抽象基类

    定义所有记忆存储实现必须遵循的接口规范。
    扩展新存储后端时，继承此类并实现所有抽象方法即可。
    """

    @abstractmethod
    async def create_conversation(self) -> str:
        """创建新会话，返回会话 ID"""
        ...

    @abstractmethod
    async def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的所有消息（返回副本，不影响内部状态）"""
        ...

    @abstractmethod
    async def add_message(self, conversation_id: str, message: Dict[str, Any]) -> None:
        """向指定会话追加一条消息"""
        ...

    @abstractmethod
    async def get_conversations(self) -> List[Dict[str, Any]]:
        """获取所有会话的概要信息列表"""
        ...

    @abstractmethod
    async def get_conversation(self, conversation_id: str) -> Dict[str, Any] | None:
        """获取单个会话的详细信息，不存在返回 None"""
        ...

    @abstractmethod
    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除指定会话，返回是否成功"""
        ...

    @abstractmethod
    async def conversation_exists(self, conversation_id: str) -> bool:
        """检查会话是否存在"""
        ...

    @abstractmethod
    async def update_title(self, conversation_id: str, title: str) -> None:
        """更新会话标题"""
        ...


# ============================================
# 内存实现（当前默认方案）
# ============================================
class InMemoryStore(BaseMemory):
    """
    内存会话存储

    使用 Python 字典存储所有会话数据，适用于开发和单机场景。
    使用 asyncio.Lock 保证并发安全。

    数据结构:
        _conversations = {
            "conv_id": {
                "id": str,
                "title": str,
                "messages": [ {role, content, ...}, ... ],
                "created_at": str (ISO 格式),
                "updated_at": str (ISO 格式),
            }
        }
    """

    def __init__(self):
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_conversation(self) -> str:
        """创建新会话"""
        conv_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        async with self._lock:
            self._conversations[conv_id] = {
                "id": conv_id,
                "title": "新对话",
                "messages": [],
                "created_at": now,
                "updated_at": now,
            }
        return conv_id

    async def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        """获取会话消息历史（返回副本）"""
        async with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                return list(conv["messages"])  # 返回副本，防止外部修改
        return []

    async def add_message(self, conversation_id: str, message: Dict[str, Any]) -> None:
        """添加消息到会话"""
        async with self._lock:
            if conversation_id in self._conversations:
                self._conversations[conversation_id]["messages"].append(message)
                self._conversations[conversation_id]["updated_at"] = (
                    datetime.now().isoformat()
                )

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """获取所有会话概要（按更新时间倒序）"""
        async with self._lock:
            result = [
                {
                    "id": conv["id"],
                    "title": conv["title"],
                    "created_at": conv["created_at"],
                    "updated_at": conv["updated_at"],
                    "message_count": len(conv["messages"]),
                }
                for conv in self._conversations.values()
            ]
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    async def get_conversation(self, conversation_id: str) -> Dict[str, Any] | None:
        """获取单个会话的详细信息"""
        async with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                return {
                    "id": conv["id"],
                    "title": conv["title"],
                    "messages": list(conv["messages"]),
                    "created_at": conv["created_at"],
                    "updated_at": conv["updated_at"],
                }
        return None

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除会话"""
        async with self._lock:
            if conversation_id in self._conversations:
                del self._conversations[conversation_id]
                return True
        return False

    async def conversation_exists(self, conversation_id: str) -> bool:
        """检查会话是否存在"""
        async with self._lock:
            return conversation_id in self._conversations

    async def update_title(self, conversation_id: str, title: str) -> None:
        """更新会话标题"""
        async with self._lock:
            if conversation_id in self._conversations:
                self._conversations[conversation_id]["title"] = title
