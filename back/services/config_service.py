"""
配置服务模块

提供 .env 文件的读写能力，支持前端通过 API 动态修改 LLM 配置。

设计要点：
  - 读取时解析 .env 为字典，支持注释行和空行
  - 写入时保留原有行的顺序和注释，仅更新目标键值
  - API 密钥在返回给前端时做脱敏处理（前4后4）
  - .env 文件不存在时返回明确错误，不自动创建

.env 文件格式示例：
  # 这是注释
  API_KEY=sk-xxxx
  BASE_URL=https://api.deepseek.com
  MODEL_NAME=deepseek-v4-flash
"""

import os
import logging

from entity.common.llm_config import LlmConfigResponse
from config import reload_settings

logger = logging.getLogger(__name__)

# .env 文件路径：与 config.py 同目录（back/ 下）
_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


class ConfigService:
    """
    配置服务：封装 .env 文件的读写逻辑

    所有方法均为静态方法（无需实例化，直接 ConfigService.xxx() 调用），
    因为配置操作本质上是无状态的文件 IO。
    """

    @staticmethod
    def get_llm_config() -> LlmConfigResponse:
        """
        读取当前 LLM 配置

        从 .env 文件中提取 BASE_URL、API_KEY、MODEL_NAME 三个字段，
        API 密钥做脱敏处理后返回。

        Returns:
            LlmConfigResponse 实例

        Raises:
            FileNotFoundError: .env 文件不存在时抛出
        """
        env_dict = ConfigService._read_env_file()

        base_url = env_dict.get("BASE_URL", "https://api.deepseek.com")
        api_key = env_dict.get("API_KEY", "")
        model_name = env_dict.get("MODEL_NAME", "deepseek-v4-flash")

        return LlmConfigResponse(
            base_url=base_url,
            api_key_masked=ConfigService._mask_api_key(api_key),
            model_name=model_name,
            has_api_key=bool(api_key and api_key != "your-api-key-here"),
        )

    @staticmethod
    def save_llm_config(base_url: str, api_key: str, model_name: str) -> None:
        """
        保存 LLM 配置到 .env 文件

        更新策略：
          - 已有键 → 原地替换值（保留注释和行顺序）
          - 新键   → 追加到文件末尾
          - api_key 为空字符串时跳过（不覆盖现有密钥）

        Args:
            base_url:   API 基础地址
            api_key:    API 密钥（空字符串表示不修改）
            model_name: 模型名称

        Raises:
            FileNotFoundError: .env 文件不存在时抛出
        """
        # 需要更新的键值对（过滤掉空的 api_key）
        updates = {
            "BASE_URL": base_url,
            "MODEL_NAME": model_name,
        }
        # api_key 为空时不修改，保留原值
        if api_key:
            updates["API_KEY"] = api_key

        lines = ConfigService._read_env_lines()
        updated_keys = set()
        new_lines = []

        for line in lines:
            stripped = line.strip()
            # 跳过注释行和空行，原样保留
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            # 解析 KEY=VALUE 格式
            eq_idx = stripped.find("=")
            if eq_idx == -1:
                new_lines.append(line)
                continue

            key = stripped[:eq_idx].strip()

            # 如果该键在更新列表中，替换值
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)

        # 追加未被替换的新键
        for key, value in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")

        # 写回文件
        with open(_ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        logger.info("LLM 配置已更新: BASE_URL=%s, MODEL_NAME=%s, API_KEY=%s",
                     base_url, model_name, "已更新" if api_key else "未修改")

        # 热重载：写入 .env 后立即刷新内存中的 settings 单例
        # 这样下一次 build_agent_graph() → create_llm() 就会读到新配置，无需重启服务
        reload_settings()

    # ============================================
    # 内部工具方法
    # ============================================

    @staticmethod
    def _read_env_file() -> dict:
        """
        解析 .env 文件为字典

        跳过注释行（# 开头）和空行，按 KEY=VALUE 格式解析。
        值中的引号会被自动去除（支持 KEY="value" 写法）。

        Returns:
            键值对字典

        Raises:
            FileNotFoundError: .env 文件不存在
        """
        lines = ConfigService._read_env_lines()
        result = {}

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            eq_idx = stripped.find("=")
            if eq_idx == -1:
                continue

            key = stripped[:eq_idx].strip()
            value = stripped[eq_idx + 1:].strip()

            # 去除包裹的引号（支持 "value" 和 'value' 写法）
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]

            result[key] = value

        return result

    @staticmethod
    def _read_env_lines() -> list:
        """
        读取 .env 文件的所有行

        Returns:
            行列表（每行保留末尾换行符）

        Raises:
            FileNotFoundError: .env 文件不存在
        """
        if not os.path.exists(_ENV_PATH):
            raise FileNotFoundError(
                f".env 文件不存在: {_ENV_PATH}。"
                f"请先在 back/ 目录下创建 .env 文件（可参考 .env.example）。"
            )

        with open(_ENV_PATH, "r", encoding="utf-8") as f:
            return f.readlines()

    @staticmethod
    def _mask_api_key(api_key: str) -> str:
        """
        脱敏 API 密钥

        规则：
          - 长度 ≤ 8 → 全部替换为 ****
          - 长度 > 8 → 显示前4位 + **** + 后4位
          - 空字符串 → 返回空

        示例：
          sk-2c8e...f8df → sk-2****f8df
          short          → ****
        """
        if not api_key or api_key == "your-api-key-here":
            return ""
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:4]}****{api_key[-4:]}"
