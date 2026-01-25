"""資料模型定義"""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator


class PriceSource(str, Enum):
    """價格來源類型"""

    OFFICIAL_OPEN = "official_open"  # 官方開盤價
    FIRST_TRADE = "first_trade"  # 第一筆成交價
    MINUTE_BAR = "minute_bar"  # 分鐘 K 線


class IntradayDiffRequest(BaseModel):
    """盤中價差查詢請求"""

    symbols: Annotated[
        list[str],
        Field(
            min_length=1,
            max_length=200,
            description="股票代碼清單，支援 1-200 檔，例如 ['2330.TW', 'AAPL']",
        ),
    ]
    date: Annotated[date, Field(description="查詢日期，格式 YYYY-MM-DD")]
    exchange: Annotated[
        str,
        Field(
            default="auto",
            description="交易所代碼，預設 'auto' 由系統自動判斷",
        ),
    ]
    timezone: Annotated[
        str,
        Field(
            default="Asia/Taipei",
            description="時區，預設 'Asia/Taipei'",
        ),
    ]
    price_source: Annotated[
        PriceSource,
        Field(
            default=PriceSource.MINUTE_BAR,
            description="價格來源類型",
        ),
    ]

    @field_validator("symbols")
    @classmethod
    def validate_symbols_not_empty(cls, v: list[str]) -> list[str]:
        """驗證 symbols 不為空且每個元素不為空字串"""
        if not v:
            raise ValueError("symbols 不可為空")
        for symbol in v:
            if not symbol or not symbol.strip():
                raise ValueError("symbols 中不可包含空字串")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """驗證時區格式"""
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as e:
            raise ValueError(f"無效的時區: {v}") from e
        return v


class PricePoint(BaseModel):
    """價格時間點資料"""

    time: datetime | None = Field(description="時間戳記（含時區）")
    price: Decimal | None = Field(description="價格")
    source: str | None = Field(description="資料來源說明")


class StockResult(BaseModel):
    """單一股票查詢結果"""

    symbol: str = Field(description="股票代碼")
    t0900: PricePoint | None = Field(description="09:00 價格資訊")
    t0950: PricePoint | None = Field(description="09:50 價格資訊")
    diff: Decimal | None = Field(description="價差（t0950 - t0900）")
    currency: str = Field(description="幣別，例如 TWD、USD")
    notes: list[str] = Field(default_factory=list, description="備註訊息")


class IntradayDiffResponse(BaseModel):
    """盤中價差查詢回應"""

    date: str = Field(description="查詢日期")
    timezone: str = Field(description="時區")
    price_source: str = Field(description="價格來源")
    results: list[StockResult] = Field(description="查詢結果清單")
    warnings: list[str] = Field(default_factory=list, description="警告訊息")


class ErrorResponse(BaseModel):
    """錯誤回應"""

    detail: str | dict[str, Any] = Field(description="錯誤詳情")
