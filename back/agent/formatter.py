"""
消息格式化工具

将 LangChain Message 对象转换为前端展示用的字典结构。
纯数据转换，不含业务逻辑。
"""

from typing import Dict, Any

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)


def format_message(msg) -> Dict[str, Any]:
    """
    将 LangChain Message 对象格式化为前端展示用的字典。

    支持的类型：
      HumanMessage  → {"role": "user", ...}
      AIMessage     → {"role": "assistant", ..., "tool_calls": [...]}
      ToolMessage   → {"role": "tool", ..., "tool_call_id": "..."}
      SystemMessage → {"role": "system", ...}
      其他          → 降级为 {"role": "user", ...}
    """
    if isinstance(msg, HumanMessage):
        return {"id": msg.id, "role": "user", "content": str(msg.content)}

    elif isinstance(msg, AIMessage):
        result: Dict[str, Any] = {
            "id": msg.id,
            "role": "assistant",
            "content": str(msg.content) if msg.content else "",
        }
        if msg.tool_calls:
            result["tool_calls"] = [
                {"id": tc["id"], "name": tc["name"], "args": tc["args"]}
                for tc in msg.tool_calls
            ]
        return result

    elif isinstance(msg, ToolMessage):
        return {
            "id": msg.id,
            "role": "tool",
            "content": str(msg.content),
            "tool_call_id": getattr(msg, "tool_call_id", ""),
        }

    elif isinstance(msg, SystemMessage):
        return {"id": msg.id, "role": "system", "content": str(msg.content)}

    else:
        return {"id": getattr(msg, "id", ""), "role": "user", "content": str(msg.content)}
