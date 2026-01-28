"""FastAPI 主應用程式"""
import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import (
    ErrorResponse,
    IntradayDiffRequest,
    IntradayDiffResponse,
)
from app.service import IntradayDiffService

# 配置結構化日誌
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()

# 建立 FastAPI 應用程式
app = FastAPI(
    title="Stock Intraday Diff Service",
    description="查詢股票在指定日期的 09:00 與 09:50 價格及價差",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 初始化服務
service = IntradayDiffService()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """處理請求驗證錯誤（422）"""
    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=exc.errors(),
    )
    
    # 格式化錯誤訊息
    formatted_errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        formatted_errors.append(f"{field}: {message}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": {
                "message": "請求資料驗證失敗",
                "errors": formatted_errors,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """處理未預期的錯誤"""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "系統內部錯誤，請稍後再試"},
    )


@app.get("/")
async def root() -> dict[str, str]:
    """根路徑"""
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康檢查"""
    return {"status": "healthy"}


@app.get("/debug/yfinance")
async def debug_yfinance() -> dict:
    """
    診斷 yfinance 在當前環境中的運作狀態
    
    用於排查 Render 環境中 yfinance 無法取得資料的問題
    """
    import traceback
    from datetime import date, timedelta
    import subprocess
    import sys
    
    import yfinance as yf
    
    results = {
        "environment": {
            "datasource_type": settings.datasource_type,
            "python_version": sys.version,
            "yfinance_version": yf.__version__,
        },
        "installed_packages": {},
        "tests": [],
    }
    
    # 檢查關鍵依賴是否已安裝
    critical_packages = ["lxml", "html5lib", "beautifulsoup4", "requests", "pandas"]
    for pkg in critical_packages:
        try:
            mod = __import__(pkg.replace("-", "_").replace("4", ""))
            version = getattr(mod, "__version__", "unknown")
            results["installed_packages"][pkg] = version
        except ImportError:
            results["installed_packages"][pkg] = "NOT INSTALLED"
    
    # 測試 1: 基本 yfinance 連線（日線數據）- 使用 download 方法
    test1 = {"name": "yfinance_download_daily", "status": "unknown", "details": {}}
    try:
        # 使用 download 方法而非 Ticker.history
        data = yf.download("AAPL", period="5d", interval="1d", progress=False)
        if data.empty:
            test1["status"] = "failed"
            test1["details"]["error"] = "Empty DataFrame returned"
        else:
            test1["status"] = "success"
            test1["details"]["rows"] = len(data)
            test1["details"]["columns"] = list(data.columns)
            test1["details"]["last_date"] = str(data.index[-1])
    except Exception as e:
        test1["status"] = "error"
        test1["details"]["error"] = str(e)
        test1["details"]["traceback"] = traceback.format_exc()
    results["tests"].append(test1)
    
    # 測試 2: Ticker.history 方法
    test2 = {"name": "yfinance_ticker_history", "status": "unknown", "details": {}}
    try:
        ticker = yf.Ticker("AAPL")
        data = ticker.history(period="5d", interval="1d")
        if data.empty:
            test2["status"] = "failed"
            test2["details"]["error"] = "Empty DataFrame returned"
            # 嘗試獲取更多資訊
            test2["details"]["ticker_info_keys"] = list(ticker.info.keys())[:10] if ticker.info else []
        else:
            test2["status"] = "success"
            test2["details"]["rows"] = len(data)
    except Exception as e:
        test2["status"] = "error"
        test2["details"]["error"] = str(e)
        test2["details"]["traceback"] = traceback.format_exc()
    results["tests"].append(test2)
    
    # 測試 3: 直接調用 Yahoo Finance API
    test3 = {"name": "direct_yahoo_api", "status": "unknown", "details": {}}
    try:
        import urllib.request
        import json
        
        url = "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=5d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_data = response.read()
            json_data = json.loads(raw_data)
            
            test3["status"] = "success"
            test3["details"]["status_code"] = response.status
            
            # 解析數據
            chart = json_data.get("chart", {})
            result = chart.get("result", [])
            if result:
                timestamps = result[0].get("timestamp", [])
                test3["details"]["data_points"] = len(timestamps)
                test3["details"]["has_indicators"] = "indicators" in result[0]
            else:
                test3["details"]["error"] = "No result in response"
                test3["details"]["response_keys"] = list(json_data.keys())
                
    except Exception as e:
        test3["status"] = "error"
        test3["details"]["error"] = str(e)
        test3["details"]["traceback"] = traceback.format_exc()
    results["tests"].append(test3)
    
    # 測試 4: 台股直接 API
    test4 = {"name": "direct_yahoo_api_tw", "status": "unknown", "details": {}}
    try:
        import urllib.request
        import json
        
        url = "https://query1.finance.yahoo.com/v8/finance/chart/2330.TW?interval=1d&range=5d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_data = response.read()
            json_data = json.loads(raw_data)
            
            test4["status"] = "success"
            test4["details"]["status_code"] = response.status
            
            chart = json_data.get("chart", {})
            result = chart.get("result", [])
            if result:
                timestamps = result[0].get("timestamp", [])
                test4["details"]["data_points"] = len(timestamps)
                # 獲取最新價格
                quote = result[0].get("indicators", {}).get("quote", [{}])[0]
                closes = quote.get("close", [])
                if closes:
                    test4["details"]["last_close"] = closes[-1]
            else:
                test4["details"]["error"] = "No result in response"
                
    except Exception as e:
        test4["status"] = "error"
        test4["details"]["error"] = str(e)
        test4["details"]["traceback"] = traceback.format_exc()
    results["tests"].append(test4)
    
    # 總結
    success_count = sum(1 for t in results["tests"] if t["status"] == "success")
    results["summary"] = {
        "total_tests": len(results["tests"]),
        "success": success_count,
        "failed": len(results["tests"]) - success_count,
        "recommendation": "",
    }
    
    # 建議
    if results["installed_packages"].get("lxml") == "NOT INSTALLED":
        results["summary"]["recommendation"] = "Missing lxml - add to requirements.txt"
    elif success_count >= 2 and results["tests"][0]["status"] != "success":
        results["summary"]["recommendation"] = "Direct API works but yfinance fails - possible yfinance bug"
    elif success_count == 0:
        results["summary"]["recommendation"] = "All tests failed - network or dependency issue"
    
    return results


@app.post(
    "/v1/stocks/intraday-diff",
    response_model=IntradayDiffResponse,
    status_code=status.HTTP_200_OK,
    responses={
        422: {"model": ErrorResponse, "description": "請求驗證失敗"},
        413: {"model": ErrorResponse, "description": "請求過大"},
        500: {"model": ErrorResponse, "description": "系統內部錯誤"},
    },
)
async def query_intraday_diff(
    request: IntradayDiffRequest,
) -> IntradayDiffResponse:
    """
    查詢股票盤中價差
    
    查詢多檔股票在指定日期的 09:00 與 09:50 價格，以及兩者的價差。
    
    **功能特點：**
    - 支援 1-200 檔股票批次查詢
    - 支援跨交易所代碼（如 .TW、.US）
    - 自動處理非交易日、早收盤等特殊情況
    - 時間對齊容忍度 ±2 分鐘
    - 自動記憶體快取（TTL 10 分鐘）
    
    **價格來源：**
    - `official_open`: 官方開盤價（若支援）
    - `first_trade`: 當日第一筆成交價
    - `minute_bar`: 分鐘 K 線收盤價（預設）
    
    **時區處理：**
    所有輸入與輸出時間皆以指定的 `timezone` 為準。
    
    **錯誤處理：**
    - 單一股票查詢失敗不影響其他股票
    - 錯誤訊息會記錄在 `notes` 與 `warnings` 中
    - 整體仍回傳 200 OK（服務降級）
    """
    logger.info(
        "intraday_diff_request",
        symbols=request.symbols,
        date=str(request.date),
        timezone=request.timezone,
        price_source=request.price_source.value,
    )
    
    # 檢查 symbols 數量上限（防止濫用）
    if len(request.symbols) > 200:
        logger.warning(
            "symbols_limit_exceeded",
            count=len(request.symbols),
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="symbols 數量超過上限（最多 200 檔）",
        )
    
    try:
        # 查詢服務
        results, warnings = await service.query_intraday_diff(
            symbols=request.symbols,
            target_date=request.date,
            timezone=request.timezone,
            price_source=request.price_source,
        )
        
        # 建立回應
        response = IntradayDiffResponse(
            date=str(request.date),
            timezone=request.timezone,
            price_source=request.price_source.value,
            results=results,
            warnings=warnings,
        )
        
        logger.info(
            "intraday_diff_response",
            symbols_count=len(request.symbols),
            results_count=len(results),
            warnings_count=len(warnings),
        )
        
        return response
        
    except Exception as e:
        logger.error(
            "intraday_diff_failed",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢失敗：{str(e)}",
        ) from e


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
