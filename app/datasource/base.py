"""資料源抽象基礎類別"""
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Any


class MinuteBar:
    """分鐘 K 線資料"""

    def __init__(
        self,
        timestamp: datetime,
        open_price: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: int,
    ) -> None:
        self.timestamp = timestamp
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume


class TradingDayInfo:
    """交易日資訊"""

    def __init__(
        self,
        is_trading_day: bool,
        reason: str | None = None,
        early_close_time: datetime | None = None,
    ) -> None:
        self.is_trading_day = is_trading_day
        self.reason = reason  # 例如："Holiday", "Weekend", "Halted"
        self.early_close_time = early_close_time


class StockDataSource(ABC):
    """股票資料源抽象介面"""

    @abstractmethod
    async def get_minute_bars(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> list[MinuteBar]:
        """
        取得指定日期的分鐘 K 線資料

        Args:
            symbol: 股票代碼（如 "2330.TW", "AAPL"）
            target_date: 目標日期
            timezone: 時區

        Returns:
            分鐘 K 線清單，按時間排序
        """
        pass

    @abstractmethod
    async def get_official_open_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """
        取得官方開盤價

        Args:
            symbol: 股票代碼
            target_date: 目標日期
            timezone: 時區

        Returns:
            (開盤時間, 開盤價) 或 None（若無資料）
        """
        pass

    @abstractmethod
    async def get_first_trade_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """
        取得當日第一筆成交價

        Args:
            symbol: 股票代碼
            target_date: 目標日期
            timezone: 時區

        Returns:
            (成交時間, 成交價) 或 None（若無資料）
        """
        pass

    @abstractmethod
    async def check_trading_day(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> TradingDayInfo:
        """
        檢查是否為交易日

        Args:
            symbol: 股票代碼
            target_date: 目標日期
            timezone: 時區

        Returns:
            交易日資訊
        """
        pass

    @abstractmethod
    def get_currency(self, symbol: str) -> str:
        """
        取得股票的計價幣別

        Args:
            symbol: 股票代碼

        Returns:
            幣別代碼（如 "TWD", "USD"）
        """
        pass

    def parse_exchange_from_symbol(self, symbol: str) -> str:
        """
        從股票代碼解析交易所

        Args:
            symbol: 股票代碼

        Returns:
            交易所代碼（如 "TW", "US", "JP"）
        """
        if ".TW" in symbol.upper():
            return "TW"
        if ".TWO" in symbol.upper():
            return "TW"
        if ".US" in symbol.upper():
            return "US"
        if ".JP" in symbol.upper():
            return "JP"
        # 預設美股（無後綴通常為美股）
        return "US"
