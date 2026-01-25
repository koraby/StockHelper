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
