"""核心服務邏輯：查詢股票盤中價差"""
import asyncio
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import structlog

from app.config import settings
from app.datasource.base import MinuteBar, StockDataSource
from app.datasource.mock import MockDataSource
from app.datasource.real import RealDataSource
from app.datasource.yahoo_api_source import YahooAPIDataSource
from app.datasource.yfinance_source import YFinanceDataSource
from app.models import PricePoint, PriceSource, StockResult

logger = structlog.get_logger()


class PriceCache:
    """簡單的記憶體快取（TTL 支援）"""

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._cache: dict[str, tuple[Any, datetime]] = {}
        self._ttl_seconds = ttl_seconds

    def get(self, key: str) -> Any | None:
        """取得快取資料"""
        if key not in self._cache:
            return None
        
        value, timestamp = self._cache[key]
        if datetime.now() - timestamp > timedelta(seconds=self._ttl_seconds):
            # 過期，移除快取
            del self._cache[key]
            return None
        
        return value

    def set(self, key: str, value: Any) -> None:
        """設定快取資料"""
        self._cache[key] = (value, datetime.now())

    def clear(self) -> None:
        """清除所有快取"""
        self._cache.clear()


class IntradayDiffService:
    """盤中價差查詢服務"""

    def __init__(self, datasource: StockDataSource | None = None) -> None:
        """
        初始化服務
        
        Args:
            datasource: 資料源實例，若未提供則根據設定自動建立
        """
        if datasource is None:
            if settings.datasource_type == "mock":
                self.datasource = MockDataSource()
            elif settings.datasource_type == "yfinance":
                self.datasource = YFinanceDataSource()
            elif settings.datasource_type == "yahoo_api":
                self.datasource = YahooAPIDataSource()
            else:
                self.datasource = RealDataSource()
        else:
            self.datasource = datasource
        
        self.cache = PriceCache(ttl_seconds=settings.cache_ttl_seconds)
        self.max_concurrent = settings.max_concurrent_requests
        self.tolerance_minutes = settings.time_alignment_tolerance_minutes

    async def query_intraday_diff(
        self,
        symbols: list[str],
        target_date: date,
        timezone: str,
        price_source: PriceSource,
    ) -> tuple[list[StockResult], list[str]]:
        """
        查詢多檔股票的盤中價差
        
        Args:
            symbols: 股票代碼清單
            target_date: 查詢日期
            timezone: 時區
            price_source: 價格來源類型
        
        Returns:
            (查詢結果清單, 警告訊息清單)
        """
        results: list[StockResult] = []
        warnings: list[str] = []
        
        # 使用 semaphore 限制併發數量
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_symbol(symbol: str) -> StockResult:
            """處理單一股票查詢"""
            async with semaphore:
                try:
                    result = await self._query_single_stock(
                        symbol, target_date, timezone, price_source
                    )
                    return result
                except Exception as e:
                    logger.error(
                        "query_symbol_failed",
                        symbol=symbol,
                        error=str(e),
                        exc_info=True,
                    )
                    warnings.append(f"查詢 {symbol} 時發生錯誤：{str(e)}")
                    # 回傳空結果
                    return StockResult(
                        symbol=symbol,
                        t0900=None,
                        t0950=None,
                        diff=None,
                        currency=self.datasource.get_currency(symbol),
                        notes=[f"系統錯誤：{str(e)}"],
                    )
        
        # 並行查詢所有股票
        tasks = [process_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        
        return list(results), warnings

    async def _query_single_stock(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
        price_source: PriceSource,
    ) -> StockResult:
        """
        查詢單一股票
        
        Args:
            symbol: 股票代碼
            target_date: 查詢日期
            timezone: 時區
            price_source: 價格來源類型
        
        Returns:
            查詢結果
        """
        notes: list[str] = []
        currency = self.datasource.get_currency(symbol)
        
        # 檢查是否為交易日
        trading_day_info = await self.datasource.check_trading_day(
            symbol, target_date, timezone
        )
        
        if not trading_day_info.is_trading_day:
            reason = trading_day_info.reason or "Non-trading day"
            if reason == "Holiday":
                notes.append("Non-trading day (Holiday)")
            elif reason == "Weekend":
                notes.append("Non-trading day (Weekend)")
            else:
                notes.append(f"Non-trading day ({reason})")
            
            return StockResult(
                symbol=symbol,
                t0900=None,
                t0950=None,
                diff=None,
                currency=currency,
                notes=notes,
            )
        
        # 根據 price_source 取得價格
        if price_source == PriceSource.OFFICIAL_OPEN:
            t0900 = await self._get_official_open_price(
                symbol, target_date, timezone, notes
            )
            t0950 = await self._get_minute_price(
                symbol, target_date, timezone, 9, 50, notes
            )
        elif price_source == PriceSource.FIRST_TRADE:
            t0900 = await self._get_first_trade_price(
                symbol, target_date, timezone, notes
            )
            t0950 = await self._get_minute_price(
                symbol, target_date, timezone, 9, 50, notes
            )
        else:  # MINUTE_BAR
            t0900 = await self._get_minute_price(
                symbol, target_date, timezone, 9, 0, notes
            )
            t0950 = await self._get_minute_price(
                symbol, target_date, timezone, 9, 50, notes
            )
        
        # 計算價差
        diff = None
        if t0900 and t0950 and t0900.price is not None and t0950.price is not None:
            diff = (t0950.price - t0900.price).quantize(Decimal("0.01"))
        
        return StockResult(
            symbol=symbol,
            t0900=t0900,
            t0950=t0950,
            diff=diff,
            currency=currency,
            notes=notes,
        )

    async def _get_official_open_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
        notes: list[str],
    ) -> PricePoint | None:
        """取得官方開盤價"""
        cache_key = f"official_open:{symbol}:{target_date}:{timezone}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            result = await self.datasource.get_official_open_price(
                symbol, target_date, timezone
            )
            if result:
                dt, price = result
                price_point = PricePoint(
                    time=dt,
                    price=price,
                    source="official_open",
                )
                self.cache.set(cache_key, price_point)
                return price_point
            else:
                notes.append("Official open price not available")
                return None
        except Exception as e:
            logger.warning(
                "get_official_open_failed",
                symbol=symbol,
                error=str(e),
            )
            notes.append(f"Failed to get official open price: {str(e)}")
            return None

    async def _get_first_trade_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
        notes: list[str],
    ) -> PricePoint | None:
        """取得第一筆成交價"""
        cache_key = f"first_trade:{symbol}:{target_date}:{timezone}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            result = await self.datasource.get_first_trade_price(
                symbol, target_date, timezone
            )
            if result:
                dt, price = result
                price_point = PricePoint(
                    time=dt,
                    price=price,
                    source="first_trade",
                )
                self.cache.set(cache_key, price_point)
                return price_point
            else:
                notes.append("First trade price not available")
                return None
        except Exception as e:
            logger.warning(
                "get_first_trade_failed",
                symbol=symbol,
                error=str(e),
            )
            notes.append(f"Failed to get first trade price: {str(e)}")
            return None

    async def _get_minute_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
        hour: int,
        minute: int,
        notes: list[str],
    ) -> PricePoint | None:
        """
        取得指定分鐘的價格（含時間對齊邏輯）
        
        時間對齊規則：
        1. 優先取目標分鐘的資料
        2. 若無資料，向前尋找（+1, +2 分鐘）
        3. 若仍無，向後尋找（-1, -2 分鐘）
        4. 若仍無，記錄 notes 並回傳 None
        """
        cache_key = f"minute:{symbol}:{target_date}:{timezone}:{hour}:{minute}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # 取得所有分鐘 K 線
            bars = await self.datasource.get_minute_bars(symbol, target_date, timezone)
            if not bars:
                notes.append(f"No minute bar data available for {hour:02d}:{minute:02d}")
                return None
            
            # 建立時間索引
            tz = ZoneInfo(timezone)
            target_dt = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
                0,
                tzinfo=tz,
            )
            
            # 嘗試精確匹配
            bar = self._find_bar_at_time(bars, target_dt)
            if bar:
                price_point = PricePoint(
                    time=bar.timestamp,
                    price=bar.open,
                    source="minute_bar",
                )
                self.cache.set(cache_key, price_point)
                return price_point
            
            # 嘗試向前對齊（+1, +2 分鐘）
            for offset in range(1, self.tolerance_minutes + 1):
                forward_dt = target_dt + timedelta(minutes=offset)
                bar = self._find_bar_at_time(bars, forward_dt)
                if bar:
                    notes.append(
                        f"Used {hour:02d}:{minute + offset:02d} data "
                        f"(+{offset} min alignment)"
                    )
                    price_point = PricePoint(
                        time=bar.timestamp,
                        price=bar.open,
                        source=f"minute_bar (aligned +{offset}min)",
                    )
                    self.cache.set(cache_key, price_point)
                    return price_point
            
            # 嘗試向後對齊（-1, -2 分鐘）
            for offset in range(1, self.tolerance_minutes + 1):
                backward_dt = target_dt - timedelta(minutes=offset)
                bar = self._find_bar_at_time(bars, backward_dt)
                if bar:
                    notes.append(
                        f"Used {hour:02d}:{minute - offset:02d} data "
                        f"(-{offset} min alignment)"
                    )
                    price_point = PricePoint(
                        time=bar.timestamp,
                        price=bar.open,
                        source=f"minute_bar (aligned -{offset}min)",
                    )
                    self.cache.set(cache_key, price_point)
                    return price_point
            
            # 完全找不到資料
            notes.append(
                f"No data found for {hour:02d}:{minute:02d} "
                f"(±{self.tolerance_minutes} min tolerance)"
            )
            return None
            
        except Exception as e:
            logger.warning(
                "get_minute_price_failed",
                symbol=symbol,
                hour=hour,
                minute=minute,
                error=str(e),
            )
            notes.append(f"Failed to get minute price: {str(e)}")
            return None

    def _find_bar_at_time(
        self,
        bars: list[MinuteBar],
        target_dt: datetime,
    ) -> MinuteBar | None:
        """
        在 K 線清單中尋找指定時間的資料
        
        Args:
            bars: K 線清單
            target_dt: 目標時間
        
        Returns:
            找到的 K 線，若無則回傳 None
        """
        for bar in bars:
            # 比較時間（忽略秒數）
            bar_time = bar.timestamp.replace(second=0, microsecond=0)
            target_time = target_dt.replace(second=0, microsecond=0)
            
            if bar_time == target_time:
                return bar
        
        return None
