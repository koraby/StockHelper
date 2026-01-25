"""整合測試：API 端點"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestIntradayDiffAPI:
    """測試 API 端點"""

    def test_root_endpoint(self) -> None:
        """測試根路徑"""
        response = client.get("/")
        assert response.status_code == 200
        assert "service" in response.json()

    def test_health_check(self) -> None:
        """測試健康檢查"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_query_valid_request(self) -> None:
        """測試有效的查詢請求"""
        payload = {
            "symbols": ["2330.TW", "AAPL"],
            "date": "2025-05-20",
            "timezone": "Asia/Taipei",
        }
        response = client.post("/v1/stocks/intraday-diff", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["date"] == "2025-05-20"
        assert data["timezone"] == "Asia/Taipei"
        assert data["price_source"] == "minute_bar"
        assert len(data["results"]) == 2
        
        # 檢查 2330.TW 結果
        tw_result = next(r for r in data["results"] if r["symbol"] == "2330.TW")
        assert tw_result["currency"] == "TWD"
        assert tw_result["t0900"] is not None
        assert tw_result["t0950"] is not None
        assert tw_result["diff"] is not None
        
        # 檢查 AAPL 結果（非交易日）
        us_result = next(r for r in data["results"] if r["symbol"] == "AAPL")
        assert us_result["currency"] == "USD"
        assert us_result["t0900"] is None
        assert us_result["t0950"] is None
        assert us_result["diff"] is None
        assert len(us_result["notes"]) > 0

    def test_query_with_official_open(self) -> None:
        """測試使用官方開盤價"""
        payload = {
            "symbols": ["2330.TW"],
            "date": "2025-05-20",
            "timezone": "Asia/Taipei",
            "price_source": "official_open",
        }
        response = client.post("/v1/stocks/intraday-diff", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["price_source"] == "official_open"
        assert data["results"][0]["t0900"]["source"] == "official_open"

    def test_query_empty_symbols(self) -> None:
        """測試空的 symbols 清單"""
        payload = {
            "symbols": [],
            "date": "2025-05-20",
        }
        response = client.post("/v1/stocks/intraday-diff", json=payload)
        
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_query_too_many_symbols(self) -> None:
        """測試超過上限的 symbols 數量"""
        payload = {
            "symbols": [f"STOCK{i}" for i in range(201)],
            "date": "2025-05-20",
        }
        response = client.post("/v1/stocks/intraday-diff", json=payload)
        
        assert response.status_code == 413
        assert "上限" in response.json()["detail"]

    def test_query_invalid_date_format(self) -> None:
        """測試無效的日期格式"""
        payload = {
            "symbols": ["2330.TW"],
            "date": "20250520",  # 錯誤格式
        }
        response = client.post("/v1/stocks/intraday-diff", json=payload)
        
        assert response.status_code == 422

    def test_query_invalid_timezone(self) -> None:
        """測試無效的時區"""
        payload = {
            "symbols": ["2330.TW"],
            "date": "2025-05-20",
            "timezone": "Invalid/Timezone",
        }
        response = client.post("/v1/stocks/intraday-diff", json=payload)
        
        assert response.status_code == 422

    def test_query_single_stock(self) -> None:
        """測試單一股票查詢"""
        payload = {
            "symbols": ["2330.TW"],
            "date": "2025-05-20",
        }
        response = client.post("/v1/stocks/intraday-diff", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["symbol"] == "2330.TW"

    def test_openapi_schema(self) -> None:
        """測試 OpenAPI schema 可存取"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "/v1/stocks/intraday-diff" in schema["paths"]
