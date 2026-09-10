"""本机配置（从 .env 读取）。

密钥只放在你电脑上的 Python 程序里，网页不能传密钥。
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.shared.constants import MAX_INPUT_CHARS

# 优先读项目根目录 .env，其次 backend-python/.env
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
_LOCAL_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), str(_LOCAL_ENV)),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "crusher-api"
    mock_mode: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 只允许服务端配置；H5 禁止覆盖
    llm_api_key: str = ""
    llm_provider: str = "deepseek"
    # 真实模式必须显式配置 LLM_MODEL；默认空串，避免 Settings 默认值掩盖未配置
    llm_model: str = ""

    llm_base_url: str = ""
    llm_temperature: float = 0.2
    llm_max_tokens: int = 2048

    # 输入上限：契约固定为 MAX_INPUT_CHARS
    max_input_chars: int = MAX_INPUT_CHARS

    def has_api_key(self) -> bool:
        return bool(self.llm_api_key.strip()) and self.llm_api_key.strip() != "sk-your-api-key-here"

    def public_info(self) -> dict[str, object]:
        """可返回给前端的非敏感信息（绝不含 api_key）。"""
        return {
            "mock_mode": self.mock_mode,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "max_input_chars": MAX_INPUT_CHARS,
            "has_api_key": self.has_api_key(),
        }


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Demo 契约：无论 .env 如何写，公开上限与 Schema maxLength 保持一致
    settings.max_input_chars = MAX_INPUT_CHARS
    return settings
