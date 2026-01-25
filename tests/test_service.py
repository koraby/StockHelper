"""單元測試：服務邏輯"""
from datetime import date
from decimal import Decimal

import pytest

from app.datasource.mock import MockDataSource
from app.models import PriceSource
from app.service import IntradayDiffService


@pytest.fixture
def service() -> IntradayDiffService:
    """建立測試用服務實例"""
    datasource = MockDataSource()
    return IntradayDiffService(datasource=datasource)


class TestIntradayDiffService:
    """測試服務邏輯"""

    @pytest.mark.asyncio
    async def test_query_tw_stock_normal_trading_day(
        self, service: IntradayDiffService
    ) -> None:
        """測試台股正常交易日"""
        results, warnings = await service.query_intraday_diff(
            symbols=["2330.TW"],
            target_date=date(2025, 5, 20),
            timezone="Asia/Taipei",
            price_source=PriceSource.MINUTE_BAR,
        )
        
        assert len(results) == 1
        assert len(warnings) == 0
        
        result = results[0]
        assert result.symbol == "2330.TW"
        assert result.currency == "TWD"
        assert result.t0900 is not None
        assert result.t0950 is not None
        assert result.t0900.price == Decimal("823.0")
        assert result.t0950.price == Decimal("829.5")
        assert result.diff == Decimal("6.50")

    @pytest.mark.asyncio
    async def test_query_us_stock_non_trading_day(
        self, service: IntradayDiffService
    ) -> None:
        """測試美股非交易日"""
        results, warnings = await service.query_intraday_diff(
            symbols=["AAPL"],
            target_date=date(2025, 5, 20),
            timezone="Asia/Taipei",
            price_source=PriceSource.MINUTE_BAR,
        )
        
        assert len(results) == 1
        result = results[0]
        assert result.symbol == "AAPL"
        assert result.currency == "USD"
        assert result.t0900 is None
        assert result.t0950 is None
        assert result.diff is None
        assert len(result.notes) > 0
        assert "Non-trading day" in result.notes[0]

    @pytest.mark.asyncio
    async def test_query_multiple_stocks(
        self, service: IntradayDiffService
    ) -> None:
        """測試批次查詢多檔股票"""
        results, warnings = await service.query_intraday_diff(
            symbols=["2330.TW", "AAPL"],
            target_date=date(2025, 5, 20),
            timezone="Asia/Taipei",
            price_source=PriceSource.MINUTE_BAR,
        )
        
        assert len(results) == 2
        
        # 2330.TW 應該有資料
        tw_result = next(r for r in results if r.symbol == "2330.TW")
        assert tw_result.t0900 is not None
        assert tw_result.t0950 is not None
        
        # AAPL 應該是非交易日
        us_result = next(r for r in results if r.symbol == "AAPL")
        assert us_result.t0900 is None
        assert us_result.t0950 is None

    @pytest.mark.asyncio
    async def test_query_early_close(
        self, service: IntradayDiffService
    ) -> None:
        """測試早收盤情境（09:50 無資料）"""
        results, warnings = await service.query_intraday_diff(
            symbols=["2884.TW"],
            target_date=date(2025, 5, 20),
            timezone="Asia/Taipei",
            price_source=PriceSource.MINUTE_BAR,
        )
        
        assert len(results) == 1
        result = results[0]
        assert result.symbol == "2884.TW"
        assert result.t0900 is not None
        assert result.t0950 is None  # 早收盤，09:50 無資料
        assert result.diff is None
        assert len(result.notes) > 0

    @pytest.mark.asyncio
    async def test_time_alignment_tolerance(
        self, service: IntradayDiffService
    ) -> None:
        """測試時間對齊容忍度"""
        # Mock 資料中 2884.TW 只有到 09:40
        # 查詢 09:50 應該嘗試向前/向後對齊
        results, warnings = await service.query_intraday_diff(
            symbols=["2884.TW"],
            target_date=date(2025, 5, 20),
            timezone="Asia/Taipei",
            price_source=PriceSource.MINUTE_BAR,
        )
        
        result = results[0]
        # 09:50 無法對齊（超出 ±2 分鐘），應為 None
        assert result.t0950 is None

    @pytest.mark.asyncio
    async def test_official_open_price_source(
        self, service: IntradayDiffService
    ) -> None:
        """測試官方開盤價來源"""
        results, warnings = await service.query_intraday_diff(
            symbols=["2330.TW"],
            target_date=date(2025, 5, 20),
            timezone="Asia/Taipei",
            price_source=PriceSource.OFFICIAL_OPEN,
        )
        
        assert len(results) == 1
        result = results[0]
        assert result.t0900 is not None
        assert result.t0900.source == "official_open"
        assert result.t0950 is not None
        assert "minute_bar" in result.t0950.source

    @pytest.mark.asyncio
    async def test_currency_detection(
        self, service: IntradayDiffService
    ) -> None:
        """測試幣別偵測"""
        results, warnings = await service.query_intraday_diff(
            symbols=["2330.TW", "AAPL"],
            target_date=date(2025, 5, 20),
            timezone="Asia/Taipei",
            price_source=PriceSource.MINUTE_BAR,
        )
        
        tw_result = next(r for r in results if r.symbol == "2330.TW")
        us_result = next(r for r in results if r.symbol == "AAPL")
        
        assert tw_result.currency == "TWD"
        assert us_result.currency == "USD"
