"""
ReAct Agent 包（基于 LangGraph）

模块结构：
  - core.py       编排层：ReActAgent 类（生命周期 + run/resume + 会话 CRUD）
  - stream.py     流式适配：astream_events → 前端 SSE 事件
  - interrupt.py  HITL 中断：检测、提取、过期清理
  - formatter.py  消息格式化：LangChain Message → 前端字典
  - graph.py      图工厂：构建 LangGraph 状态图（含 HITL 中间件）

外部使用：
  from agent import ReActAgent
"""

from agent.core import ReActAgent

__all__ = ["ReActAgent"]
