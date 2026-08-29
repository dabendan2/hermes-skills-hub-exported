---
name: web-search
description: Multi-engine text search and Playwright reverse image search tools.
category: research
---

# Web Search MCP Skills & Tools

Use when searching text or reverse image visual matching via the `web-search` MCP server (`search_mcp.py`).

## Available Tools in MCP

### 1. `search`
- **用途**: 多引擎聯合網頁文字搜尋（Yahoo TW、DuckDuckGo、維基百科中/英文、搜狗、百度）。
- **參數**: `query` (網頁搜尋關鍵字), `limit` (結果數量，預設 5), `engines` (搜尋引擎列表)。

### 2. `reverse_image_search`
- **用途**: 真實視覺特徵以圖搜圖（圖片反向搜尋）。純粹調用 `PicImageSearch` 庫中的正常引擎（百度識圖、Ascii2D、SauceNAO、Iqdb）進行特徵比對，自動過濾並關閉已失效/報錯之引擎（Yandex, Bing, Google, Copyseeker, TraceMoe, Lenso 等）。
- **參數**: `image_input` (線上圖片網址或本地檔案路徑), `limit` (結果數量，預設 5)。

## 執行與維護說明
- **MCP 腳本位置**: `~/.hermes/skills/research/web-search/scripts/search_mcp.py`與`skills/research/web-search/scripts/search_mcp.py`
- **反爬與引擎庫**: 使用 `PicImageSearch` (BaiDu) 進行 WAF 免疫之圖搜圖 API 請求。無匹配時直接回報工具錯誤。
