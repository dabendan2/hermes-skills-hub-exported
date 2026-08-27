# Taiwan Real Estate CLI Toolset (台灣房地產物件篩選與實價登錄解析工具箱)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![NPM: tw-lvr-cli](https://img.shields.io/badge/NPM-tw--lvr--cli-red.svg)](https://www.npmjs.com/package/tw-lvr-cli)

An intelligent, fast command-line toolset built in Python for extracting active property listings, querying actual transaction prices (內政部實價登錄), inferring building floor layout configurations, and auto-cropping blueprint layouts in Taiwan.

這是一個為台灣房地產市場設計的**一站式命令行工具箱**。它結合了**「現有市場在售物件精準篩選」**與官方**「內政部實價登錄行情深度解析」**，能自動過濾非住宅用途、推導垂直戶別格局，並對格局圖進行裁剪。

---

## 📂 Project Structure & Features / 專案結構與核心功能

### 1. Active Listing Scraper / 在售物件精準篩選器 (`realestate_cli.py`)
*   **📐 Precise Net Area Parsing**: Filters properties by exact indoor net area (主建物 + 陽台, or `主+陽`) in pings (坪).
*   **🛡️ Office Auto-Exclusion**: Real-time background check of deed purpose (謄本用途) to filter out "一般事務所", "辦公室", or commercial listings.
*   **🔗 Link Validation**: Checks candidate URLs in the background to ensure they are active (returns 200, not 404).
*   **🚗 Parking Space Detection**: Identifies whether the property includes a parking space directly.

### 2. Actual Price Registry Query / 內政部實價登錄自動化 (`scripts/tw-lvr-wrapper.sh`)
*   Automates queries to Taiwan's official Real Estate Actual Transaction Database without logging in using `tw-lvr-cli`.
*   Includes path-finding and wrapper logic to auto-locate Playwright's `chrome-headless-shell` binary to avoid browser path failures.

### 3. Vertical Stack Layout Inference / 垂直戶別格局推導 (`scripts/infer_layout.py`)
*   Takes a physical address, sequential-parses the layout layers, queries transaction histories of the same vertical stack or neighboring floors (e.g., `X之2號3樓`, `X-2號4樓`), and deduces the exact area (坪數) and layout configurations.

### 4. Community Statistics Report / 社區實登數據分析 (`scripts/community_stats.py`)
*   Parses large JSON output files from `tw-lvr` actual price queries, groups records by building/community name, and generates beautiful Markdown transaction reports (avg price, year trends, layout distributions).

### 5. Localized Corner-Crop OCR / 格局圖尺寸標記裁剪 (`scripts/extract_layout.py`)
*   Downloads layout blueprints, auto-crops to specified corners where sizes/pings/layout codes are printed, and runs OCR to extract labels.

---

## 🚀 Installation / 安裝指南

### 1. Clone & Install Python Dependencies
```bash
git clone https://github.com/dabendan2/taiwan-realestate-cli-scraper.git
cd taiwan-realestate-cli-scraper
pip install -r requirements.txt
```

### 2. Install Playwright & Real Price CLI Dependencies (For Actual Price Queries)
```bash
# Install NodeJS CLI global tool
npm i -g tw-lvr-cli

# Install headless browser dependency
npx playwright install chromium-headless-shell
```

---

## 📖 Usage Examples / 使用範例

### A. Active Market Listings / 搜尋最新在售住宅
Search for active listings in Neihu, Songshan, and Nangang under 3000萬, max 10 years old, with at least 15 pings net (主+陽), and excluding offices:
```bash
python3 realestate_cli.py --districts "內湖區,南港區,松山區" --net-area 15 --price 3000 --age 10
```

### B. Query Actual Prices (實價登錄) / 查詢歷史成交價格
Query pre-sales transactions with community filter (e.g. "日安PARK" in Banqiao):
```bash
./scripts/tw-lvr-wrapper.sh extract --where "新北市板橋區縣民大道" --from 202401 --to 202612 --presale --community "日安PARK" --top 5 --pretty
```

### C. Infer Vertical Stack Layout / 垂直戶別格局自動推導
Deduce room/bathroom counts and net area based on a specific address's historical registry:
```bash
python3 scripts/infer_layout.py --address "新北市板橋區中山路一段161號8樓"
```

### D. Generate Community Statistics / 社區成交統計報表
```bash
# Fetch raw data to local JSON file
./scripts/tw-lvr-wrapper.sh extract --where "新北市板橋區縣民大道" --from 202301 --to 202612 --out raw_data.json

# Analyze and print Markdown report
python3 scripts/community_stats.py raw_data.json "日安PARK"
```

---

## 📄 License / 授權條款

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
