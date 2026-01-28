"""FastAPI 主應用程式"""
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import RawDataRequest

# 建立 FastAPI 應用程式
app = FastAPI(
    title="Stock Intraday Diff Service",
    description="查詢股票在指定日期的 09:00 與 09:50 價格及價差",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """處理請求驗證錯誤（422）"""
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
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "系統內部錯誤，請稍後再試"},
    )


@app.get("/")
async def root() -> dict:
    """根路徑 - API 說明"""
    return {
        "service": "Stock Intraday Diff Service",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/intraday-diff": "批次查詢股票指定兩個時間點的開盤價及價差",
            "GET /health": "健康檢查",
            "GET /docs": "Swagger UI 文件",
        },
        "example": {
            "url": "POST /api/intraday-diff",
            "body": {
                "symbols": ["2330.TW", "2317.TW"],
                "date": "2026-01-28",
                "time1": "09:00",
                "time2": "09:50"
            }
        }
    }


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康檢查"""
    return {"status": "healthy"}


def fetch_symbol_data(symbol: str, date: str, time1: str, time2: str) -> dict:
    """
    取得單一股票指定兩個時間點的開盤價及價差
    
    Args:
        symbol: 股票代碼（如 2330.TW）
        date: 日期（如 2026-01-27）
        time1: 第一個時間點（如 09:00）
        time2: 第二個時間點（如 09:50）
    """
    result = {
        "symbol": symbol,
        "date": date,
        "time1": time1,
        "time2": time2,
        "open_1": None,
        "open_2": None,
        "diff": None,
        "error": None,
    }
    
    try:
        # 解析日期
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        tz = ZoneInfo("Asia/Taipei")
        
        start_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=tz)
        end_dt = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=tz)
        
        period1 = int(start_dt.timestamp())
        period2 = int(end_dt.timestamp())
        
        # 調用 Yahoo Finance API（使用 5 分鐘間隔）
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=5m&period1={period1}&period2={period2}"
        
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            raw_data = response.read()
            json_data = json.loads(raw_data)
            
            chart = json_data.get("chart", {})
            chart_result = chart.get("result", [])
            
            if chart_result:
                data = chart_result[0]
                timestamps = data.get("timestamp", [])
                indicators = data.get("indicators", {})
                quote = indicators.get("quote", [{}])[0]
                
                opens = quote.get("open", [])
                
                # 找到指定時間的 open 價格
                for i, ts in enumerate(timestamps):
                    if ts is None:
                        continue
                    
                    dt = datetime.fromtimestamp(ts, tz=tz)
                    time_str = dt.strftime("%H:%M")
                    
                    if time_str == time1 and i < len(opens) and opens[i] is not None:
                        result["open_1"] = round(opens[i], 2)
                    elif time_str == time2 and i < len(opens) and opens[i] is not None:
                        result["open_2"] = round(opens[i], 2)
                
                # 計算價差
                if result["open_1"] is not None and result["open_2"] is not None:
                    result["diff"] = round(result["open_2"] - result["open_1"], 2)
            else:
                result["error"] = "No data in API response"
                
    except Exception as e:
        result["error"] = str(e)
    
    return result


@app.post("/api/intraday-diff")
async def get_intraday_diff(request: RawDataRequest) -> list[dict]:
    """
    取得多檔股票指定兩個時間點的開盤價及價差
    
    Request Body:
        symbols: 股票代碼清單，例如 ["2330.TW", "2317.TW"]
        date: 日期，格式 YYYY-MM-DD
        time1: 第一個時間點，格式 HH:MM（預設 09:00）
        time2: 第二個時間點，格式 HH:MM（預設 09:50）
    
    Response: 陣列，每個元素包含 symbol, date, time1, time2, open_1, open_2, diff
    """
    results = []
    
    for symbol in request.symbols:
        data = fetch_symbol_data(symbol, request.date, request.time1, request.time2)
        results.append(data)
    
    return results
