"""資料模型定義"""
from typing import Annotated

from pydantic import BaseModel, Field


class RawDataRequest(BaseModel):
    """盤中價差查詢請求"""

    symbols: Annotated[
        list[str],
        Field(
            min_length=1,
            max_length=50,
            description="股票代碼清單，例如 ['2330.TW', '2317.TW']",
        ),
    ]
    date: Annotated[
        str,
        Field(
            default="2026-01-28",
            description="查詢日期，格式 YYYY-MM-DD",
        ),
    ]
    time1: Annotated[
        str,
        Field(
            default="09:00",
            description="第一個時間點，格式 HH:MM，例如 09:00",
        ),
    ]
    time2: Annotated[
        str,
        Field(
            default="09:50",
            description="第二個時間點，格式 HH:MM，例如 09:50",
        ),
    ]
