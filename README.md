# 📈 Stock Intraday Diff Service

> FastAPI 股票盤中價差查詢服務 - 查詢股票在指定日期的 09:00 與 09:50 開盤價及價差

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)

---

## ✨ 功能特點

| 功能 | 說明 |
|:-----|:-----|
| 📊 **批次查詢** | 支援 1-50 檔股票批次查詢 |
| 🌍 **跨市場** | 支援跨交易所代碼（.TW、.US 等） |
| 💰 **精準價格** | 09:00 和 09:50 開盤價，自動四捨五入至 2 位小數 |
| 🔗 **Yahoo Finance API** | 直接呼叫 Yahoo Finance API 取得即時資料 |

---

## 🚀 快速開始

### 📋 環境需求

- **Python** 3.11+

### 📦 安裝依賴

```powershell
pip install -r requirements.txt
```

### ▶️ 啟動服務

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服務啟動後，可在以下網址存取：

| 文件類型 | 網址 |
|:---------|:-----|
| 📘 **Swagger UI** | http://localhost:8000/docs |
| 📗 **ReDoc** | http://localhost:8000/redoc |

---

## 📖 API 使用範例

### 端點

| 方法 | 路徑 | 說明 |
|:----:|:-----|:-----|
| GET | `/` | API 說明 |
| GET | `/health` | 健康檢查 |
| POST | `/api/intraday-diff` | 批次查詢股票價差 |

### 查詢股票價差

**Request:**

```powershell
curl -X POST http://localhost:8000/api/intraday-diff `
  -H "Content-Type: application/json" `
  -d '{
    "symbols": ["2330.TW", "2317.TW", "2337.TW"],
    "date": "2026-01-28"
  }'
```

**Response:**

```json
[
  {
    "symbol": "2330.TW",
    "date": "2026-01-28",
    "open_0900": 1050.0,
    "open_0950": 1055.0,
    "diff": 5.0,
    "error": null
  },
  {
    "symbol": "2317.TW",
    "date": "2026-01-28",
    "open_0900": 150.5,
    "open_0950": 151.0,
    "diff": 0.5,
    "error": null
  },
  {
    "symbol": "2337.TW",
    "date": "2026-01-28",
    "open_0900": 81.7,
    "open_0950": 83.8,
    "diff": 2.1,
    "error": null
  }
]
```

---

## 📋 API 規格

### POST /api/intraday-diff

#### 請求參數

| 參數 | 類型 | 必填 | 說明 | 預設值 |
|:-----|:-----|:----:|:-----|:-------|
| `symbols` | `string[]` | ✅ | 股票代碼清單（1-50 檔） | - |
| `date` | `string` | ❌ | 查詢日期（YYYY-MM-DD） | 當天日期 |

#### 回應欄位

| 欄位 | 類型 | 說明 |
|:-----|:-----|:-----|
| `symbol` | `string` | 股票代碼 |
| `date` | `string` | 查詢日期 |
| `open_0900` | `number \| null` | 09:00 開盤價 |
| `open_0950` | `number \| null` | 09:50 開盤價 |
| `diff` | `number \| null` | 價差（open_0950 - open_0900） |
| `error` | `string \| null` | 錯誤訊息（如有） |

#### 回應狀態碼

| 狀態碼 | 說明 |
|:------:|:-----|
| `200` | ✅ 查詢成功 |
| `422` | ⚠️ 請求參數驗證失敗 |
| `500` | ❌ 系統內部錯誤 |

---

## 📁 專案結構

```
StockHelper/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 應用程式入口
│   ├── models.py            # Pydantic 資料模型
│   └── config.py            # 配置管理
├── requirements.txt         # 專案依賴
├── Procfile                 # Render 部署配置
├── render.yaml              # Render 部署配置
└── README.md
```

---

## 🌐 部署

本專案已配置 Render 部署：

1. 連結 GitHub 倉庫到 Render
2. 選擇 Web Service
3. 使用 `render.yaml` 自動配置

部署後可在 Render 提供的 URL 存取服務。

---

<p align="center">
  <sub>Made with ❤️ for stock traders</sub>
</p>
