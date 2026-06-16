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

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional


class ConversationRegistry:
    """
    会话注册表（应用层）

    仅管理会话元数据（标题、时间戳），不存储消息。
    消息历史由 LangGraph checkpointer 通过 thread_id 自动管理。

    数据结构:
        _conversations = {
            "uuid": {
                "id": str,
                "title": str,
                "created_at": str (ISO 格式),
                "updated_at": str (ISO 格式),
            }
        }
    """

    def __init__(self):
        self._conversations: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_conversation(self) -> str:
        """创建新会话，返回会话 ID"""
        conv_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        async with self._lock:
            self._conversations[conv_id] = {
                "id": conv_id,
                "title": "新对话",
                "created_at": now,
                "updated_at": now,
            }
        return conv_id

    async def get_conversations(self) -> List[Dict[str, Any]]:
        """获取所有会话概要列表（按更新时间倒序）"""
        async with self._lock:
            result = [
                {
                    "id": c["id"],
                    "title": c["title"],
                    "created_at": c["created_at"],
                    "updated_at": c["updated_at"],
                }
                for c in self._conversations.values()
            ]
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    async def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取单个会话的元数据，不存在返回 None"""
        async with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv:
                return dict(conv)
        return None

    async def delete_conversation(self, conversation_id: str) -> bool:
        """删除指定会话，返回是否成功"""
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

    async def touch(self, conversation_id: str) -> None:
        """更新会话的 updated_at 时间戳"""
        async with self._lock:
            if conversation_id in self._conversations:
                self._conversations[conversation_id]["updated_at"] = (
                    datetime.now().isoformat()
                )
