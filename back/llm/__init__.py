"""
LLM 客户端模块（基于 LangChain 1.2）

使用 LangChain 的 ChatOpenAI 封装与大模型的交互，
支持同步调用和流式输出两种模式。
ChatOpenAI 天然兼容 OpenAI API 格式，
可通过修改 BASE_URL 接入 DeepSeek、智谱、Moonshot 等第三方服务。

LangChain 1.2 变更点：
  - max_tokens → max_completion_tokens
  - 新增 request_timeout / max_retries 参数
"""

from langchain_openai import ChatOpenAI
from config import settings


def create_llm() -> ChatOpenAI:
    """
    创建 ChatOpenAI 实例

    Returns:
        ChatOpenAI: 配置好的 LLM 客户端，支持 async 调用和流式输出
    """
    return ChatOpenAI(
        api_key=settings.API_KEY,
        base_url=settings.BASE_URL,
        model=settings.MODEL_NAME,
        temperature=settings.TEMPERATURE,
        max_completion_tokens=settings.MAX_COMPLETION_TOKENS,  # LangChain 1.2: 替代 max_tokens
        request_timeout=settings.REQUEST_TIMEOUT,              # 请求超时（秒）
        max_retries=settings.MAX_RETRIES,                      # 自动重试次数
    )
