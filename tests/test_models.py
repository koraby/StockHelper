"""單元測試：資料模型"""
from datetime import date

import pytest
from pydantic import ValidationError

from app.models import IntradayDiffRequest, PriceSource


class TestIntradayDiffRequest:
    """測試請求模型驗證"""

    def test_valid_request(self) -> None:
        """測試有效的請求"""
        request = IntradayDiffRequest(
            symbols=["2330.TW", "AAPL"],
            date=date(2025, 5, 20),
            timezone="Asia/Taipei",
        )
        assert len(request.symbols) == 2
        assert request.date == date(2025, 5, 20)
        assert request.timezone == "Asia/Taipei"
        assert request.price_source == PriceSource.MINUTE_BAR

    def test_symbols_min_length(self) -> None:
        """測試 symbols 最小長度限制"""
        with pytest.raises(ValidationError) as exc_info:
            IntradayDiffRequest(
                symbols=[],
                date=date(2025, 5, 20),
            )
        assert "symbols" in str(exc_info.value)

    def test_symbols_max_length(self) -> None:
        """測試 symbols 最大長度限制"""
        with pytest.raises(ValidationError) as exc_info:
            IntradayDiffRequest(
                symbols=[f"STOCK{i}" for i in range(201)],
                date=date(2025, 5, 20),
            )
        assert "symbols" in str(exc_info.value)

    def test_symbols_empty_string(self) -> None:
        """測試 symbols 不可包含空字串"""
        with pytest.raises(ValidationError) as exc_info:
            IntradayDiffRequest(
                symbols=["2330.TW", ""],
                date=date(2025, 5, 20),
            )
        assert "空字串" in str(exc_info.value)

    def test_invalid_timezone(self) -> None:
        """測試無效的時區"""
        with pytest.raises(ValidationError) as exc_info:
            IntradayDiffRequest(
                symbols=["2330.TW"],
                date=date(2025, 5, 20),
                timezone="Invalid/Timezone",
            )
        assert "時區" in str(exc_info.value)

    def test_price_source_default(self) -> None:
        """測試 price_source 預設值"""
        request = IntradayDiffRequest(
            symbols=["2330.TW"],
            date=date(2025, 5, 20),
        )
        assert request.price_source == PriceSource.MINUTE_BAR

    def test_price_source_official_open(self) -> None:
        """測試 official_open 價格來源"""
        request = IntradayDiffRequest(
            symbols=["2330.TW"],
            date=date(2025, 5, 20),
            price_source=PriceSource.OFFICIAL_OPEN,
        )
        assert request.price_source == PriceSource.OFFICIAL_OPEN
