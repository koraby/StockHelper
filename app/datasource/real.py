"""真實資料源實作（保留擴展介面）"""
from datetime import date, datetime
from decimal import Decimal

from app.datasource.base import MinuteBar, StockDataSource, TradingDayInfo


class RealDataSource(StockDataSource):
    """
    真實資料源實作
    
    可整合的資料供應商：
    - Yahoo Finance (yfinance)：免費，支援全球多數市場，但分鐘資料有限制
    - Polygon.io：需付費，美股資料完整，包含分鐘級 K 線
    - Tiingo：需付費，支援美股與加密貨幣
    - 台灣證交所 TWSE API：免費，台股官方資料
    - Alpha Vantage：免費額度有限，支援全球市場
    
    環境變數配置：
    - POLYGON_API_KEY：Polygon.io API 金鑰
    - TIINGO_API_KEY：Tiingo API 金鑰
    - YAHOO_FINANCE_ENABLED：是否啟用 Yahoo Finance（預設 True）
    - TWSE_API_ENABLED：是否啟用台灣證交所 API（預設 True）
    """

    def __init__(self, config: dict | None = None) -> None:
        """
        初始化真實資料源
        
        Args:
            config: 配置字典，包含 API 金鑰等資訊
        """
        self.config = config or {}
        # TODO: 初始化 HTTP 客戶端
        # self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # TODO: 載入 API 金鑰
        # self.polygon_api_key = os.getenv("POLYGON_API_KEY", "")
        # self.tiingo_api_key = os.getenv("TIINGO_API_KEY", "")

    async def get_minute_bars(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> list[MinuteBar]:
        """
        取得分鐘 K 線資料
        
        實作建議：
        1. 根據 symbol 判斷交易所（使用 parse_exchange_from_symbol）
        2. 根據交易所選擇合適的資料源：
            - 台股：優先使用 TWSE API，備援 Yahoo Finance
            - 美股：優先使用 Polygon.io（若有金鑰），備援 Yahoo Finance
            - 其他：使用 Yahoo Finance
        3. 處理時區轉換
        4. 處理 API 錯誤與重試
        """
        # TODO: 實作真實資料查詢
        raise NotImplementedError("真實資料源尚未實作，請使用 MockDataSource")

    async def get_official_open_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """
        取得官方開盤價
        
        實作建議：
        - 台股：從 TWSE API 取得官方開盤價
        - 美股：從 Polygon.io 或 Yahoo Finance 取得
        - 注意：不是所有資料源都提供官方開盤價，可能需要回退到 first_trade
        """
        # TODO: 實作官方開盤價查詢
        raise NotImplementedError("真實資料源尚未實作，請使用 MockDataSource")

    async def get_first_trade_price(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> tuple[datetime, Decimal] | None:
        """
        取得第一筆成交價
        
        實作建議：
        1. 取得當日所有成交記錄
        2. 找出第一筆成交（時間戳記最早）
        3. 返回時間與價格
        """
        # TODO: 實作第一筆成交價查詢
        raise NotImplementedError("真實資料源尚未實作，請使用 MockDataSource")

    async def check_trading_day(
        self,
        symbol: str,
        target_date: date,
        timezone: str,
    ) -> TradingDayInfo:
        """
        檢查是否為交易日
        
        實作建議：
        1. 使用交易日曆 API（如 Polygon.io calendar API）
        2. 或從實際資料查詢結果推斷（若當日無任何交易資料，可能為非交易日）
        3. 檢查是否為週末
        4. 檢查是否為已知假期
        """
        # TODO: 實作交易日檢查
        raise NotImplementedError("真實資料源尚未實作，請使用 MockDataSource")

    def get_currency(self, symbol: str) -> str:
        """取得幣別"""
        if ".TW" in symbol.upper() or ".TWO" in symbol.upper():
            return "TWD"
        if ".JP" in symbol.upper():
            return "JPY"
        if ".HK" in symbol.upper():
            return "HKD"
        if ".L" in symbol.upper():  # 倫敦
            return "GBP"
        # 預設美元
        return "USD"

    # === Yahoo Finance 整合範例 ===
    # async def _fetch_from_yahoo(self, symbol: str, target_date: date) -> list[MinuteBar]:
    #     """
    #     從 Yahoo Finance 取得資料
    #     
    #     使用 yfinance 套件：
    #     import yfinance as yf
    #     ticker = yf.Ticker(symbol)
    #     data = ticker.history(start=target_date, end=target_date + timedelta(days=1), interval="1m")
    #     """
    #     pass

    # === Polygon.io 整合範例 ===
    # async def _fetch_from_polygon(self, symbol: str, target_date: date) -> list[MinuteBar]:
    #     """
    #     從 Polygon.io 取得資料
    #     
    #     API 端點：GET /v2/aggs/ticker/{symbol}/range/1/minute/{from}/{to}
    #     需要 API 金鑰：apiKey query parameter
    #     """
    #     url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/{target_date}/{target_date}"
    #     params = {"apiKey": self.polygon_api_key, "adjusted": "true"}
    #     response = await self.http_client.get(url, params=params)
    #     # 解析回應並轉換為 MinuteBar
    #     pass

    # === TWSE API 整合範例 ===
    # async def _fetch_from_twse(self, symbol: str, target_date: date) -> list[MinuteBar]:
    #     """
    #     從台灣證交所取得資料
    #     
    #     參考 API：
    #     - 盤後資訊：https://www.twse.com.tw/exchangeReport/STOCK_DAY
    #     - 盤中資訊：https://mis.twse.com.tw/stock/api/getStockInfo.jsp
    #     """
    #     pass
