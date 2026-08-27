---
name: taiwan-realestate-pro-skills
description: 不動產專業領域技能：涵蓋在售物件爬取與存活驗證、內政部官方實價登錄（實售價格）自動化查詢、垂直戶別規格推導、與格局圖 OCR 局部裁剪。
category: real-estate
metadata:
  related_skills: [browser-stealth-bypass]
---

# 不動產專業領域技能 (Taiwan Real Estate Professional Skills)

Expert skill for automating the discovery, retrieval, structural verification, transaction price query (實價登錄), and active market listing scraping of Taiwanese real estate (pre-sales, new-builds, and completed properties).

## Trigger Conditions
* User asks for layout drawings (家配圖/格局圖) or specific details of a Taiwan building.
* User wants to verify or analyze floor-plan area (坪數), exclusive area (專有部分), public facility ratio (公設比), or layout codes.
* User asks for recent actual transaction prices (實價登錄) of a specific street, neighborhood, or building/community in Taiwan.
* User asks for active properties currently on sale (在售/代售物件) with specific criteria (e.g., price, age, bedrooms, parking, area).
* Bypassing anti-scraping blocks by navigating alternative real-estate aggregators or programmatically querying official databases.

## Key Features

### 1. Active Market Listing Scraping & Auto-Verification
* **Yungching (永慶房仲網) Path-Based Filtering**: Scrapes active properties under specific constraints using fast, direct-query URLs (e.g. `/{max_price}_price/0-{max_age}_age` appended to the list path).
* **List-Level Precision Filtering**: Key metadata is parsed directly from listing cards (e.g. searching for the `主+陽XX.XX` text pattern representing indoor net area, `屋齡: X年`, and parking/price details) to minimize HTTP round-trips.
* **Stealth Background Verification**: Runs background HTTP checks on candidates to ensure the listing links are active (status 200, not 404/expired).
* **Deed/Usage Check (排除辦公室/一般事務所)**: Inspects the detailed page's `主要用途`/`謄本用途` or listing tags. If the usage is commercial/office rather than residential (`住家用` or `集合住宅`), it is automatically filtered out.

### 2. Multi-Source Discovery & Layout Retrieval
* Search and navigate real-estate portals (591, Leju, Yungching, Sinyi) to find unblocked, high-quality layout drawings.
* Strip image size suffixes (e.g. `!fit.338x252.jpg` or `!300x360.png`) to retrieve the high-resolution source image (e.g. `!fit.900x.jpg` or base `.jpg`) for layout clarity.

### 3. Exact Address Layout Inference (中古屋/華廈平面圖推導)
* **Strict Verification Priority**: When an exact address is provided, run the exact vertical stack layout inference first using `scripts/infer_layout.py` to programmatically resolve the registered rooms, bathrooms, and main area.
* Query transaction histories of the same vertical stack or neighboring floors of the same line (e.g., `X之2號3樓`, `X-2號4樓`) to identify the exact area (坪數) and room/bathroom configurations.
* Map these spec details to standard layout drawings from community pages.

### 4. Pre-sales Base Locating & Map Link Generation
* Pre-sales don't have registered doorplate addresses yet. Search portals to locate land lot numbers (地號), block identifiers, or adjacent landmarks (parks, schools).
* Standardize map links:
  * *Coordinate Link*: `https://www.google.com/maps/place/LAT,LON`
  * *Intersection/Keyword search link*: `https://www.google.com/maps/search/?api=1&query=縣市區路1路2路口`

### 5. Localized Corner-Crop OCR & Pyeong (坪數) Math
* Crop blueprint images into specialized regions (bottom-left or top-left corners) where layout codes and exclusive square meters are printed to reduce OCR noise.
* Convert exclusive square meters to pings:
  $$\text{Sales Area (坪)} = \frac{\text{Exclusive Area } (m^2) \times 0.3025}{1 - \text{Public Ratio}}$$

### 6. Actual Transaction Price (實價登錄) Query
* Uses `tw-lvr-cli` to query Taiwan's official transaction database without login.
* Supports completed homes (成屋買賣) and pre-sales (預售屋) queries, producing structured, typed JSON/CSV.

---

## 💻 內建 CLI 腳本工具

### A. 在售物件精準篩選工具：`realestate_cli.py`
部署路徑：`/home/ubuntu/.hermes/scripts/realestate_cli.py`
一鍵查詢多區域、自訂總價、屋齡、室內實坪，自動排除非住宅用途。
```bash
# 基本用法（預設查詢松山、內湖、南港，室內實坪大於15坪，排除辦公室）
/home/ubuntu/.hermes/scripts/realestate_cli.py

# 自訂區域與自訂實坪條件（如尋找板橋、萬華，實坪大於20坪的住宅，總價3500萬內，屋齡15年內）
/home/ubuntu/.hermes/scripts/realestate_cli.py --districts "板橋區,萬華區" --net-area 20 --price 3500 --age 15
```

### B. 實價登錄與格局推導工具：`tw-lvr-wrapper.sh` & `scripts/`
* **實價登錄查詢**：
  ```bash
  # 查詢成屋實價登錄
  ./scripts/tw-lvr-wrapper.sh extract --where "新竹市東區關新路" --from 202501 --to 202612 --top 3 --pretty
  
  # 查詢預售屋實價登錄
  ./scripts/tw-lvr-wrapper.sh extract --where "新北市板橋區縣民大道" --from 202401 --to 202612 --presale --community "日安PARK" --top 2 --pretty
  ```
* **垂直戶別格局推導** (`infer_layout.py`)：
  ```bash
  python3 scripts/infer_layout.py --address "新北市板橋區中山路一段161號"
  ```

---

## ⚠️ 關鍵防雷與實戰 Pitfalls

* **待售物件與實價登錄分離**：若使用者要求「在售/代售物件」且「不要實價登錄」，不要使用 `tw-lvr-cli`。直接運行 `realestate_cli.py` 獲取市面上真實存活的廣告物件。
* **排除辦公室/一般事務所**：台北市與新北市在工業區或特定商業區規劃有大量「一般事務所（即商業辦公用）」。在提供物件前，必須檢查 `謄本用途`、`建物格局` 及 `使用分區`，若出現「一般事務所」、「辦公室」、「商業用」，必須予以剔除。
* **待售連結時效與耐久性**：
  * **Always Verify Before Delivering**：提供給使用者的物件連結，必須先於背景訪問確認狀態碼 200，絕不輸出已失效的 404 物件。
  * **Provide Community Fallbacks**：除單一待售頁連結外，應額外附上 591 社區主頁連結（如 `market.591.com.tw/<id>`），此連結為永久性，會動態更新該社區最新上架。
* **「兩房、室內實坪 > 20 坪」的市場真相**：
  * 屋齡 10 年內、公設比 33-35% 的新大樓中，室內實坪大於 20 坪，建商幾乎 100% 都會規劃為 3 房。
  * 若客戶鎖定「大兩房、扣除公設大於 20 坪、屋齡小於 10 年」，必須主動將搜尋範圍擴展至「小 3 房」或「2+1 房」，並向其說明可自行改為超大兩房使用。
* **Browser Path Auto-Detection (tw-lvr-cli)**：若 `tw-lvr` 出現 code `6` 錯誤，請確保環境變數指向 Playwright binary，或直接使用自帶自動修復路徑的 `./scripts/tw-lvr-wrapper.sh`。
