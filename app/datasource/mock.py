"""Mock 資料源實作（用於測試與開發）"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.datasource.base import MinuteBar, StockDataSource, TradingDayInfo


class MockDataSource(StockDataSource):
    """
    Mock 資料源，回傳固定的測試資料
    
    涵蓋情境：
    1. 台股正常交易日（2330.TW）
    2. 美股正常交易日（AAPL）
    3. 美股非交易日（週末或假日）
    4. 分鐘資料缺洞（09:01 有資料但 09:00 無資料）
    5. 早收盤情境（09:50 無資料）
    """

    def __init__(self) -> None:
        # 定義測試用的固定資料
        self._mock_data = {
            "2330.TW": {
                "2025-05-20": {
                    "is_trading": True,
                    "official_open": (datetime(2025, 5, 20, 9, 0, 0), 823.0),
                    "first_trade": (datetime(2025, 5, 20, 9, 0, 15), 823.0),
                    "minute_bars": self._generate_tw_minute_bars(
                        date(2025, 5, 20), 823.0, 829.5
                    ),
                },
                "2025-12-25": {  # 聖誕節假期
                    "is_trading": False,
                    "reason": "Holiday",
                },
                "2026-01-22": {  # 2026/01/22 測試資料
                    "is_trading": True,
                    "official_open": (datetime(2026, 1, 22, 9, 0, 0), 1050.0),
                    "first_trade": (datetime(2026, 1, 22, 9, 0, 10), 1050.0),
                    "minute_bars": self._generate_tw_minute_bars(
                        date(2026, 1, 22), 1050.0, 1068.0
                    ),
                },
                "2026-01-23": {  # 2026/01/23 測試資料（星期五）
                    "is_trading": True,
                    "official_open": (datetime(2026, 1, 23, 9, 0, 0), 1065.0),
                    "first_trade": (datetime(2026, 1, 23, 9, 0, 8), 1065.0),
                    "minute_bars": self._generate_tw_minute_bars(
                        date(2026, 1, 23), 1065.0, 1078.0
                    ),
                },
            },
            "2317.TW": {
                "2026-01-22": {  # 鴻海 2026/01/22 測試資料
                    "is_trading": True,
                    "official_open": (datetime(2026, 1, 22, 9, 0, 0), 185.0),
                    "first_trade": (datetime(2026, 1, 22, 9, 0, 5), 185.0),
                    "minute_bars": self._generate_tw_minute_bars(
                        date(2026, 1, 22), 185.0, 188.5
                    ),
                },
                "2026-01-23": {  # 鴻海 2026/01/23 測試資料（星期五）
                    "is_trading": True,
                    "official_open": (datetime(2026, 1, 23, 9, 0, 0), 188.0),
                    "first_trade": (datetime(2026, 1, 23, 9, 0, 5), 188.0),
                    "minute_bars": self._generate_tw_minute_bars(
                        date(2026, 1, 23), 188.0, 192.5
                    ),
                },
            },
            "2356.TW": {
                "2026-01-22": {  # 英業達 2026/01/22 測試資料
                    "is_trading": True,
                    "official_open": (datetime(2026, 1, 22, 9, 0, 0), 52.3),
                    "first_trade": (datetime(2026, 1, 22, 9, 0, 8), 52.3),
                    "minute_bars": self._generate_tw_minute_bars(
                        date(2026, 1, 22), 52.3, 53.8
                    ),
                },
                "2026-01-23": {  # 英業達 2026/01/23 測試資料（星期五）
                    "is_trading": True,
                    "official_open": (datetime(2026, 1, 23, 9, 0, 0), 53.5),
                    "first_trade": (datetime(2026, 1, 23, 9, 0, 6), 53.5),
                    "minute_bars": self._generate_tw_minute_bars(
                        date(2026, 1, 23), 53.5, 54.8
                    ),
                },
            },
            "AAPL": {
                "2025-05-20": {  # 美國時區的非交易日（假設週日）
                    "is_trading": False,
                    "reason": "Weekend",
                },
                "2025-05-19": {  # 美國交易日
                    "is_trading": True,
                    "official_open": (datetime(2025, 5, 19, 9, 30, 0), 182.5),
                    "first_trade": (datetime(2025, 5, 19, 9, 30, 5), 182.5),
                    "minute_bars": self._generate_us_minute_bars(
                        date(2025, 5, 19), 182.5, 185.2
                    ),
                },
            },
            "2884.TW": {  # 早收盤測試
                "2025-05-20": {
                    "is_trading": True,
                    "official_open": (datetime(2025, 5, 20, 9, 0, 0), 25.5),
                    "first_trade": (datetime(2025, 5, 20, 9, 0, 10), 25.5),
                    "minute_bars": self._generate_early_close_bars(
                        date(2025, 5, 20), 25.5
                    ),
                },
            },
        }

    def _generate_tw_minute_bars(
        self, target_date: date, start_price: float, end_price: float
    ) -> list[MinuteBar]:
        """生成台股分鐘 K 線（09:00-13:30）"""
        bars = []
        tz = ZoneInfo("Asia/Taipei")
        
        # 09:00 - 12:00
        current_price = start_price
        price_step = (end_price - start_price) / 51  # 51 分鐘到達 09:50
        
        for hour in range(9, 13):
            end_minute = 60 if hour < 12 else 31  # 12:00-12:30
            for minute in range(0, end_minute):
                if hour == 9 and minute < 51:
                    price = start_price + (price_step * minute)
                else:
                    price = end_price + ((minute % 10) * 0.5 - 2.5)
                
                timestamp = datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    hour,
                    minute,
                    0,
                    tzinfo=tz,
                )
                bars.append(
                    MinuteBar(
                        timestamp=timestamp,
                        open_price=Decimal(str(round(price - 0.5, 4))),
                        high=Decimal(str(round(price + 1.0, 4))),
                        low=Decimal(str(round(price - 1.0, 4))),
                        close=Decimal(str(round(price, 4))),
                        volume=1000 + minute * 10,
                    )
                )
        
        return bars

    def _generate_us_minute_bars(
        self, target_date: date, start_price: float, end_price: float
    ) -> list[MinuteBar]:
        """生成美股分鐘 K 線（09:30-16:00 美東時間）"""
        bars = []
        tz = ZoneInfo("America/New_York")
        
        current_price = start_price
        total_minutes = 390  # 6.5 小時
        price_step = (end_price - start_price) / 20  # 20 分鐘達到目標
        
        hour = 9
        minute = 30
        
        for i in range(total_minutes):
            if i < 20:
                price = start_price + (price_step * i)
            else:
                price = end_price + ((i % 10) * 0.2 - 1.0)
            
            timestamp = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
                0,
                tzinfo=tz,
            )
            bars.append(
                MinuteBar(
                    timestamp=timestamp,
                    open_price=Decimal(str(round(price - 0.2, 4))),
                    high=Decimal(str(round(price + 0.5, 4))),
                    low=Decimal(str(round(price - 0.5, 4))),
                    close=Decimal(str(round(price, 4))),
                    volume=5000 + i * 50,
                )
            )
            
            minute += 1
            if minute >= 60:
                minute = 0
                hour += 1
        
        return bars

    def _generate_early_close_bars(
        self, target_date: date, start_price: float
    ) -> list[MinuteBar]:
        """生成早收盤資料（只到 09:40）"""
        bars = []
        tz = ZoneInfo("Asia/Taipei")
        
        for minute in range(0, 41):  # 09:00 - 09:40
            price = start_price + (minute * 0.05)
            timestamp = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                9,
                minute,
                0,
                tzinfo=tz,
            )
            bars.append(
                MinuteBar(
                    timestamp=timestamp,
                    open_price=Decimal(str(round(price - 0.1, 4))),
                    high=Decimal(str(round(price + 0.2, 4))),
                    low=Decimal(str(round(price - 0.2, 4))),
                    close=Decimal(str(round(price, 4))),
                    volume=500 + minute * 5,
                )
            )
        
        return bars

    async def get_minute_bars(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> list[MinuteBar]:
        """取得分鐘 K 線資料"""
        date_str = target_date.strftime("%Y-%m-%d")
        
        if symbol not in self._mock_data:
            return []
        
        if date_str not in self._mock_data[symbol]:
            return []
        
        day_data = self._mock_data[symbol][date_str]
        if not day_data.get("is_trading", False):
            return []
        
        return day_data.get("minute_bars", [])

    async def get_official_open_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """取得官方開盤價"""
        date_str = target_date.strftime("%Y-%m-%d")
        
        if symbol not in self._mock_data:
            return None
        
        if date_str not in self._mock_data[symbol]:
            return None
        
        day_data = self._mock_data[symbol][date_str]
        if not day_data.get("is_trading", False):
            return None
        
        official_open = day_data.get("official_open")
        if official_open:
            # 轉換時區
            dt, price = official_open
            tz = ZoneInfo(timezone)
            dt_with_tz = dt.replace(tzinfo=ZoneInfo("Asia/Taipei"))
            return (dt_with_tz.astimezone(tz), Decimal(str(price)))
        
        return None

    async def get_first_trade_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """取得第一筆成交價"""
        date_str = target_date.strftime("%Y-%m-%d")
        
        if symbol not in self._mock_data:
            return None
        
        if date_str not in self._mock_data[symbol]:
            return None
        
        day_data = self._mock_data[symbol][date_str]
        if not day_data.get("is_trading", False):
            return None
        
        first_trade = day_data.get("first_trade")
        if first_trade:
            dt, price = first_trade
            tz = ZoneInfo(timezone)
            dt_with_tz = dt.replace(tzinfo=ZoneInfo("Asia/Taipei"))
            return (dt_with_tz.astimezone(tz), Decimal(str(price)))
        
        return None

    async def check_trading_day(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> TradingDayInfo:
        """檢查是否為交易日"""
        date_str = target_date.strftime("%Y-%m-%d")
        
        if symbol not in self._mock_data:
            # 未知代碼，假設為交易日
            return TradingDayInfo(is_trading_day=True)
        
        if date_str not in self._mock_data[symbol]:
            # 未定義的日期，假設為交易日
            return TradingDayInfo(is_trading_day=True)
        
        day_data = self._mock_data[symbol][date_str]
        is_trading = day_data.get("is_trading", True)
        reason = day_data.get("reason")
        
        return TradingDayInfo(is_trading_day=is_trading, reason=reason)

    def get_currency(self, symbol: str) -> str:
        """取得幣別"""
        if ".TW" in symbol.upper() or ".TWO" in symbol.upper():
            return "TWD"
        if ".JP" in symbol.upper():
            return "JPY"
        # 預設美元
        return "USD"
