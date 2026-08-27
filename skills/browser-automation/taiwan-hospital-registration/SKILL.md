---
name: taiwan-hospital-registration
description: Taiwan hospital registration CLI (hospital) for CGMH, FEMH, and TPECH.
---

# Taiwan Hospital Registration & Progress (`hospital`)

單一整合式門診掛號與叫號進度管理 CLI（`hospital`），整合長庚體系（CGMH）、亞東紀念醫院（FEMH）與臺北市立聯合醫院（TPECH，含和平及各院區）。

## 特色與改版說明
- **單一 CLI 入口**：統一使用 `hospital` 指令，廢除舊有 `cgmh`、`femh`、`tpech`、`heping` 獨立軟連結。
- **身分驗證資料**：**嚴格僅讀取 `USER_*` 環境變數**（`USER_ID_NUMBER` / `USER_ID` / `USER_BIRTHDAY_ROC` / `USER_NAME`），不再讀取或回退至 `DAD_*` 環境變數。
- **嚴格單一指令格式**：強制採用單一指令結構 `hospital <hospital_code> <subcommand>`，不提供混用順序，極簡化認知需求。

---

## 嚴格單一指令語法格式

```bash
hospital <hospital_code> <subcommand> [args...] [flags]
```

### 支援醫院代碼 (`hospital_code`)
- `cgmh`：長庚醫療財團法人（可透過 `-b` 指定院區：`V` 土城（預設）、`3` 林口、`1` 台北、`2` 基隆、`5` 桃園、`6` 嘉義、`8` 高雄、`H` 鳳山）
- `femh`：亞東紀念醫院
- `tpech`（或 `heping`）：臺北市立聯合醫院（可透過 `-b` 指定院區：`H` 和平（預設）、`J` 婦幼、`F` 仁愛、`G` 中興、`Q` 忠孝、`M` 陽明等）

---

### 1. 查詢科別代碼與清單 (`dept` / `depts` / `d`)
* **語法**：
  ```bash
  hospital <hospital_code> dept [科別關鍵字] [-b 院區代碼] [--json]
  ```
* **範例**：
  ```bash
  hospital femh dept 家醫
  hospital cgmh dept 骨科 -b V
  hospital tpech dept 內科 --json
  ```

---

### 2. 查詢門診時刻表 / 醫師班表 (`schedule` / `s` / `doctor`)
* **語法**：
  ```bash
  hospital <hospital_code> schedule [科別名稱或代碼] [醫師姓名] [-b 院區代碼] [--json]
  ```
* **範例**：
  ```bash
  hospital femh schedule 家庭醫學部 陳志道
  hospital cgmh schedule V1200A 林士驊 -b V
  hospital tpech schedule 0600 -b H
  ```

---

### 3. 查詢即時看診叫號進度 (`progress` / `p`)
* **語法**：
  ```bash
  hospital <hospital_code> progress [科別名稱或代碼] [醫師姓名] [時段 1/2/3] [診間] [個人序號] [-b 院區代碼] [--json]
  ```
* **範例**：
  ```bash
  hospital femh progress 家庭醫學部 陳志道 2 D264 116
  hospital cgmh progress 胃腸肝膽科 "" 2 -b V
  hospital tpech progress 家醫 --json
  ```

---

### 4. 查詢個人預約掛號紀錄 (`records` / `query` / `r`)
自動讀取 `USER_ID_NUMBER` 與 `USER_BIRTHDAY_ROC` 環境變數。
* **語法**：
  ```bash
  hospital <hospital_code> records [身分證字號] [出生年月日] [-b 院區代碼] [--json]
  ```
* **範例**：
  ```bash
  hospital femh records
  hospital cgmh records A123456789 800101 -b V
  hospital tpech records --json
  ```

---

### 5. 預約門診掛號 / 取消掛號 (`book` / `cancel`)
* **範例**：
  ```bash
  hospital cgmh book A123456789 800101 V1200A 20260722 1985 2 -b V
  hospital cgmh cancel A123456789 800101 2026-07-22 林士驊 -b V
  ```

---

## 輸出格式規範
- 純文字模組包含標準頭尾 Banner：`=== DEPT_SUCCESS ===` / `=== SCHEDULE_SUCCESS ===` / `=== PROGRESS_SUCCESS ===` / `=== QUERY_SUCCESS ===`
- 自動化模式加入 `--json` 即輸出結構化 JSON。
