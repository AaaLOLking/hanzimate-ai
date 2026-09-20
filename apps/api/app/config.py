from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "hanzimate.sqlite3"
).as_posix()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    web_origin: str = "http://localhost:3000"
    app_name: str = "HanziMate API"
    app_version: str = "0.1.0"
    database_url: str = f"sqlite:///{DEFAULT_DATABASE_PATH}"
    database_auto_create: bool = True
    demo_user_id: str = "00000000-0000-4000-8000-000000000001"
    demo_user_email: str = "alex@demo.hanzimate.local"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_default_model: str = "deepseek-v4-flash"
    summary_timeout_seconds: int = 30
    model_daily_external_call_limit: int = Field(default=40, ge=0, le=10_000)
    model_daily_budget_yuan: float = Field(default=5.0, ge=0)
    deepseek_input_price_yuan_per_million_tokens: float = Field(default=0.0, ge=0)
    deepseek_output_price_yuan_per_million_tokens: float = Field(default=0.0, ge=0)
    dashscope_api_key: SecretStr | None = None
    dashscope_workspace_id: str | None = None
    dashscope_region: Literal["beijing", "singapore"] = "beijing"
    qwen_realtime_model: str = "qwen3.5-omni-flash-realtime"
    qwen_realtime_voice: str = "Tina"
    realtime_session_seconds: int = 480
    tavily_api_key: SecretStr | None = None
    tool_timeout_seconds: int = Field(default=15, ge=1, le=30)
    tool_external_session_limit: int = Field(default=20, ge=0, le=100)


@lru_cache
def get_settings() -> Settings:
    return Settings()
