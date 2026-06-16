"""
LLM 客户端模块

使用 LangChain 的 ChatOpenAI 封装与大模型的交互。
ChatOpenAI 天然兼容 OpenAI API 格式，
可通过修改 BASE_URL 接入 DeepSeek、智谱、Moonshot 等第三方服务。

该工厂函数被 agent/graph.py 调用，用于构建 LangGraph Agent 时创建 LLM 实例。
"""

from langchain_openai import ChatOpenAI
from config import settings


def create_llm() -> ChatOpenAI:
    """创建 ChatOpenAI 实例，支持 async 调用和流式输出"""
    return ChatOpenAI(
        api_key=settings.API_KEY,
        base_url=settings.BASE_URL,
        model=settings.MODEL_NAME,
        temperature=settings.TEMPERATURE,
        max_completion_tokens=settings.MAX_COMPLETION_TOKENS,
        request_timeout=settings.REQUEST_TIMEOUT,
        max_retries=settings.MAX_RETRIES,
    )
