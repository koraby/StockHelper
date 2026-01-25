"""應用程式配置設定"""
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """應用程式設定"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 應用程式設定
    app_name: str = "Stock Intraday Diff Service"
    debug: bool = False
    log_level: str = "INFO"

    # 資料源設定
    datasource_type: Literal["mock", "real", "yfinance"] = "mock"
    cache_ttl_seconds: int = 600  # 10 分鐘
    max_concurrent_requests: int = 10

    # 真實資料源 API 金鑰（請使用環境變數設定）
    yahoo_finance_enabled: bool = True
    polygon_api_key: str = ""
    tiingo_api_key: str = ""
    twse_api_enabled: bool = True

    # 時間對齊容忍度（分鐘）
    time_alignment_tolerance_minutes: int = 2


# 全域設定實例
settings = Settings()
