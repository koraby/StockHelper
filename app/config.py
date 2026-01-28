"""應用程式配置設定"""
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


# 全域設定實例
settings = Settings()
