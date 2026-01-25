"""YFinance 資料源實作 - 使用 yfinance 取得真實股票資料"""
import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
import yfinance as yf

from app.datasource.base import MinuteBar, StockDataSource, TradingDayInfo

logger = structlog.get_logger()


class YFinanceDataSource(StockDataSource):
    """
    使用 yfinance 的真實資料源
    
    支援：
    - 台股（需加 .TW 後綴，如 2330.TW）
    - 美股（直接使用代碼，如 AAPL）
    - 其他 Yahoo Finance 支援的市場
    
    限制：
    - 分鐘級資料只能取得最近 7 天
    - 歷史分鐘資料可能不完整
    - 非交易時段無資料
    """

    def __init__(self) -> None:
        """初始化 YFinance 資料源"""
        self._cache: dict[str, list[MinuteBar]] = {}

    def _convert_symbol(self, symbol: str) -> str:
        """
        轉換股票代碼格式
        
        台股代碼需要加上 .TW 後綴
        """
        # 如果已經有後綴，直接使用
        if "." in symbol:
            return symbol
        
        # 純數字通常是台股
        if symbol.isdigit():
            return f"{symbol}.TW"
        
        # 其他假設為美股
        return symbol

    async def get_minute_bars(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> list[MinuteBar]:
        """
        取得分鐘 K 線資料
        
        使用 yfinance 的 history 方法取得 1 分鐘級別資料
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
        
        try:
            # 使用 asyncio 在執行緒池中執行同步的 yfinance 呼叫
            bars = await asyncio.get_event_loop().run_in_executor(
                None,
                self._fetch_minute_bars_sync,
                yf_symbol,
                target_date,
                timezone,
            )
            
            # 儲存快取
            self._cache[cache_key] = bars
            
            logger.info(
                "minute_bars_fetched",
                symbol=yf_symbol,
                bars_count=len(bars),
            )
            
            return bars
            
        except Exception as e:
            logger.error(
                "fetch_minute_bars_failed",
                symbol=yf_symbol,
                error=str(e),
            )
            return []

    def _fetch_minute_bars_sync(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> list[MinuteBar]:
        """同步取得分鐘 K 線（在執行緒池中執行）"""
        ticker = yf.Ticker(symbol)
        
        # yfinance 需要 start 和 end 日期
        start_date = target_date
        end_date = target_date + timedelta(days=1)
        
        # 取得 1 分鐘級別資料
        # 注意：yfinance 的分鐘資料只能取得最近 7 天
        try:
            data = ticker.history(
                start=start_date,
                end=end_date,
                interval="1m",
                prepost=False,  # 不包含盤前盤後
            )
        except Exception as e:
            logger.warning(
                "yfinance_history_failed",
                symbol=symbol,
                error=str(e),
            )
            return []
        
        if data.empty:
            logger.warning(
                "no_data_available",
                symbol=symbol,
                date=str(target_date),
            )
            return []
        
        bars: list[MinuteBar] = []
        tz = ZoneInfo(timezone)
        
        for idx, row in data.iterrows():
            # 轉換時區
            timestamp = idx.to_pydatetime()
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=tz)
            else:
                timestamp = timestamp.astimezone(tz)
            
            bar = MinuteBar(
                timestamp=timestamp,
                open_price=Decimal(str(row["Open"])).quantize(Decimal("0.0001")),
                high=Decimal(str(row["High"])).quantize(Decimal("0.0001")),
                low=Decimal(str(row["Low"])).quantize(Decimal("0.0001")),
                close=Decimal(str(row["Close"])).quantize(Decimal("0.0001")),
                volume=int(row["Volume"]),
            )
            bars.append(bar)
        
        # 按時間排序
        bars.sort(key=lambda b: b.timestamp)
        
        return bars

    async def get_official_open_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """
        取得官方開盤價
        
        使用當日第一根分鐘 K 線的開盤價
        """
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
        """
        取得第一筆成交價
        
        使用當日第一根分鐘 K 線的開盤價
        """
        return await self.get_official_open_price(symbol, target_date, timezone)

    async def check_trading_day(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> TradingDayInfo:
        """
        檢查是否為交易日
        
        透過嘗試取得資料來判斷
        """
        # 先檢查是否為週末
        weekday = target_date.weekday()
        if weekday >= 5:  # 週六(5)或週日(6)
            return TradingDayInfo(
                is_trading_day=False,
                reason="Weekend",
            )
        
        # 嘗試取得資料
        bars = await self.get_minute_bars(symbol, target_date, timezone)
        
        if bars:
            return TradingDayInfo(is_trading_day=True)
        else:
            # 無資料可能是假日或資料尚未更新
            return TradingDayInfo(
                is_trading_day=False,
                reason="No data available (possibly holiday or data not yet updated)",
            )

    def get_currency(self, symbol: str) -> str:
        """取得幣別"""
        upper_symbol = symbol.upper()

        if ".JP" in upper_symbol:
            return "JPY"
        if ".HK" in upper_symbol:
            return "HKD"
        if ".L" in upper_symbol:
            return "GBP"
        if ".DE" in upper_symbol:
            return "EUR"
        if ".PA" in upper_symbol:
            return "EUR"
        if ".USA" in upper_symbol:
            return "USD"
        # 預設新台幣
        return "TWD"
