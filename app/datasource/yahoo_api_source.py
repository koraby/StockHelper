"""Yahoo Finance API 資料源實作 - 直接調用 Yahoo Finance API，不依賴 yfinance 庫"""
import asyncio
import json
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog

from app.datasource.base import MinuteBar, StockDataSource, TradingDayInfo

logger = structlog.get_logger()


class YahooAPIDataSource(StockDataSource):
    """
    直接調用 Yahoo Finance API 的資料源
    
    優點：
    - 不依賴 yfinance 庫，避免兼容性問題
    - 在 Render 等雲環境中更穩定
    - 更輕量，減少依賴
    
    支援：
    - 台股（需加 .TW 後綴，如 2330.TW）
    - 美股（直接使用代碼，如 AAPL）
    - 其他 Yahoo Finance 支援的市場
    """

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def __init__(self) -> None:
        """初始化 Yahoo API 資料源"""
        self._cache: dict[str, list[MinuteBar]] = {}

    def _convert_symbol(self, symbol: str) -> str:
        """
        轉換股票代碼格式
        
        台股代碼需要加上 .TW 後綴
        """
        if "." in symbol:
            return symbol
        
        if symbol.isdigit():
            return f"{symbol}.TW"
        
        return symbol

    def _fetch_data(
        self,
        symbol: str,
        interval: str,
        range_str: str | None = None,
        period1: int | None = None,
        period2: int | None = None,
    ) -> dict | None:
        """
        從 Yahoo Finance API 獲取數據
        
        Args:
            symbol: 股票代碼
            interval: 時間間隔 (1m, 5m, 1h, 1d)
            range_str: 時間範圍 (1d, 5d, 1mo)
            period1: 開始時間戳 (Unix timestamp)
            period2: 結束時間戳 (Unix timestamp)
        
        Returns:
            API 返回的 JSON 數據，失敗則返回 None
        """
        url = f"{self.BASE_URL}/{symbol}?interval={interval}"
        
        if range_str:
            url += f"&range={range_str}"
        elif period1 and period2:
            url += f"&period1={period1}&period2={period2}"
        
        logger.debug(
            "fetching_yahoo_api",
            url=url,
        )
        
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.USER_AGENT}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                raw_data = response.read()
                json_data = json.loads(raw_data)
                
                chart = json_data.get("chart", {})
                result = chart.get("result", [])
                
                if not result:
                    error = chart.get("error")
                    if error:
                        logger.warning(
                            "yahoo_api_error",
                            symbol=symbol,
                            error=error,
                        )
                    return None
                
                return result[0]
                
        except Exception as e:
            logger.error(
                "yahoo_api_request_failed",
                symbol=symbol,
                error=str(e),
            )
            return None

    def _parse_bars(
        self,
        data: dict,
        timezone: str,
    ) -> list[MinuteBar]:
        """
        解析 Yahoo Finance API 數據為 MinuteBar 列表
        
        Args:
            data: API 返回的數據
            timezone: 目標時區
        
        Returns:
            MinuteBar 列表
        """
        bars: list[MinuteBar] = []
        tz = ZoneInfo(timezone)
        
        timestamps = data.get("timestamp", [])
        indicators = data.get("indicators", {})
        quote = indicators.get("quote", [{}])[0]
        
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])
        
        for i, ts in enumerate(timestamps):
            if ts is None:
                continue
            
            # 檢查 OHLCV 數據是否有效
            if (
                i >= len(opens) or opens[i] is None or
                i >= len(highs) or highs[i] is None or
                i >= len(lows) or lows[i] is None or
                i >= len(closes) or closes[i] is None
            ):
                continue
            
            # 轉換時間戳
            dt = datetime.fromtimestamp(ts, tz=tz)
            
            bar = MinuteBar(
                timestamp=dt,
                open_price=Decimal(str(opens[i])).quantize(Decimal("0.0001")),
                high=Decimal(str(highs[i])).quantize(Decimal("0.0001")),
                low=Decimal(str(lows[i])).quantize(Decimal("0.0001")),
                close=Decimal(str(closes[i])).quantize(Decimal("0.0001")),
                volume=int(volumes[i]) if i < len(volumes) and volumes[i] else 0,
            )
            bars.append(bar)
        
        # 按時間排序
        bars.sort(key=lambda b: b.timestamp)
        
        return bars

    async def get_minute_bars(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> list[MinuteBar]:
        """
        取得分鐘 K 線資料
        """
        yf_symbol = self._convert_symbol(symbol)
        cache_key = f"{yf_symbol}_{target_date}_{timezone}"
        
        # 檢查快取
        if cache_key in self._cache:
            logger.debug("cache_hit", symbol=yf_symbol, date=str(target_date))
            return self._cache[cache_key]
        
        logger.info(
            "fetching_minute_bars",
            symbol=yf_symbol,
            date=str(target_date),
            timezone=timezone,
        )
        
        # 計算時間範圍
        tz = ZoneInfo(timezone)
        start_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=tz)
        end_dt = start_dt + timedelta(days=1)
        
        period1 = int(start_dt.timestamp())
        period2 = int(end_dt.timestamp())
        
        # 嘗試不同的間隔
        intervals = ["1m", "5m", "1h"]
        bars: list[MinuteBar] = []
        
        for interval in intervals:
            try:
                # 使用 asyncio 在執行緒池中執行同步的 HTTP 請求
                data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._fetch_data(
                        yf_symbol,
                        interval=interval,
                        period1=period1,
                        period2=period2,
                    ),
                )
                
                if data:
                    bars = self._parse_bars(data, timezone)
                    
                    if bars:
                        logger.info(
                            "minute_bars_fetched",
                            symbol=yf_symbol,
                            interval=interval,
                            bars_count=len(bars),
                        )
                        break
                        
            except Exception as e:
                logger.warning(
                    f"{interval}_fetch_failed",
                    symbol=yf_symbol,
                    error=str(e),
                )
                continue
        
        # 儲存快取
        self._cache[cache_key] = bars
        
        if not bars:
            logger.warning(
                "no_minute_data_available",
                symbol=yf_symbol,
                date=str(target_date),
            )
        
        return bars

    async def get_official_open_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """取得官方開盤價"""
        bars = await self.get_minute_bars(symbol, target_date, timezone)
        
        if not bars:
            return None
        
        first_bar = bars[0]
        return (first_bar.timestamp, first_bar.open)

    async def get_first_trade_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """取得第一筆成交價"""
        return await self.get_official_open_price(symbol, target_date, timezone)

    async def check_trading_day(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> TradingDayInfo:
        """檢查是否為交易日"""
        # 先檢查是否為週末
        weekday = target_date.weekday()
        if weekday >= 5:
            return TradingDayInfo(
                is_trading_day=False,
                reason="Weekend",
            )
        
        # 嘗試取得數據
        bars = await self.get_minute_bars(symbol, target_date, timezone)
        
        if bars:
            logger.debug(
                "trading_day_confirmed_by_data",
                symbol=symbol,
                date=str(target_date),
                bars_count=len(bars),
            )
            return TradingDayInfo(is_trading_day=True)
        else:
            # 無數據時假設為交易日，讓後續查詢決定
            logger.info(
                "no_data_assuming_trading_day",
                symbol=symbol,
                date=str(target_date),
            )
            return TradingDayInfo(is_trading_day=True)

    def get_currency(self, symbol: str) -> str:
        """取得幣別"""
        upper_symbol = symbol.upper()

        if ".TW" in upper_symbol or ".TWO" in upper_symbol:
            return "TWD"
        if ".JP" in upper_symbol:
            return "JPY"
        if ".HK" in upper_symbol:
            return "HKD"
        if ".L" in upper_symbol:
            return "GBP"
        if ".DE" in upper_symbol or ".PA" in upper_symbol:
            return "EUR"
        
        return "USD"
