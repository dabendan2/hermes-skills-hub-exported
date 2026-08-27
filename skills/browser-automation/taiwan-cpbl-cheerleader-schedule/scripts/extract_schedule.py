#!/usr/bin/env python3
import os
import sys
import json
import time
import base64
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

# 高精度視覺班表提取 Prompt
SYSTEM_PROMPT = """# Role: 高精度班表與表格圖像數據提取專家 (OCR & Visual Grid Data Extraction Agent)

## Profile
你是一位專門處理「視覺班表」、「排班圖卡」與「矩陣表格」的高精度數據提取代理。你的任務是將傳入的視覺班表圖片，嚴格轉換為無遺漏、結構化且可程式化讀取的 JSON 格式數據。

---

## Processing Workflow (步驟指南)

請依序執行以下視覺分析與數據提取步驟：

### 步驟 1：基本資訊與元數據提取 (Metadata)
- 標題 (Title)：提取主要標題（例如：應援班表）。
- 團隊/主體名稱 (Team/Organization)：提取主體或團隊名稱（如：Passion Sisters / 中信兄弟啦啦隊 / Fubon Angels / Uni-Girls）。
- 月份/時間範圍 (Month/Period)：提取月份或適用時間（如：JULY）。
- 注意事項/免責聲明 (Disclaimer)：提取圖片底部或角落的備註說明文字。

### 步驟 2：欄位與列的結構建立 (Grid Structure)
1. 橫軸（Columns）- 人員名單：
   - 從左至右依序提取所有成員/人員姓名。
   - 保持原始圖片中的排序順序。
2. 縱軸（Rows）- 日期與標籤：
   - 由上至下依序提取所有日期（如：7.03, 08/04）。
   - 提取星期（如：FRI, SAT）。
   - 特殊標籤偵測：檢查日期上方或旁邊是否有額外註記（如：「客場」、「主場」、「大巨蛋」等小標籤/Pill Badge）。

### 步驟 3：交叉矩陣出席比對 (Attendance Mapping)
- 逐一檢查矩陣中的每一個單元格 (Row, Column)。
- 圖示辨識：若單元格內出現代表出席/排班的圖示（例如：吉祥物圖案、大象圖示、勾選號、星號等），判定該成員在該日期「出席/有班」。
- 空白單元格：若單元格為空，判定為「未排班」。

---

## Output Format Specification (輸出格式要求)

請嚴格僅輸出標準 JSON 格式（包含以下完整 Schema），不要輸出額外的解說文字：

```json
{
  "metadata": {
    "title": "字串：主標題",
    "group_name": "字串：團體名稱",
    "team_name": "字串：球隊/機構名稱",
    "month": "字串：月份",
    "disclaimer": "字串：底部免責或注意事項聲明"
  },
  "members": [
    "成員1姓名",
    "成員2姓名"
  ],
  "schedules": [
    {
      "date": "MM/DD格式日期",
      "day_of_week": "星期（英文三字或中文）",
      "tag": "特殊標籤（如：大巨蛋，若無則為 null）",
      "attending_members": [
        "當天有班的成員姓名1",
        "當天有班的成員姓名2"
      ]
    }
  ],
  "member_summary": {
    "成員1姓名": ["出席日期1", "出席日期2"],
    "成員2姓名": ["出席日期1"]
  }
}
```"""

VERIFICATION_PROMPT = """# Role: 班表數據雙重校對與自我驗證專家 (Attendance Verification & Correction Agent)

## Profile
你是一位資深的排班與數據審查校對專家。你的職責是將「初步提取的 JSON 數據」與「原始班表圖像」進行深度像素級核對，揪出所有漏判、錯判、誤判，並產出 100% 精準無誤的最終校正數據。

---

## Task Instructions (校對校正任務)

請對照傳入的原始圖片，逐項審查並修正「初步提取的 JSON 數據」：
1. 漏班檢查 (False Negatives)：再次核對是否有成員出席標記被漏掉。
2. 多班檢查 (False Positives)：再次核對是否有空白單元格被誤判為出席。
3. 日期格式與對應一致性 (Consistency Check)：確保 schedules 與 member_summary 日期統一（格式如 08/04）。

---

## Output Requirement
你必須僅輸出 100% 正確的、經過雙重校對後的 JSON 數據（與原 Schema 相同），不得包含任何 Markdown 包裹符號或解釋性文字。"""

MODEL_NAME = "gemini-3.6-flash"

def load_api_key():
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key and os.path.exists("/home/ubuntu/.hermes/.env"):
        with open("/home/ubuntu/.hermes/.env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
                        val = v.split("#")[0].strip().strip('"').strip("'")
                        if val:
                            return val
    return api_key

def get_mime_type(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        return 'image/jpeg'
    elif ext == '.png':
        return 'image/png'
    elif ext == '.webp':
        return 'image/webp'
    return 'image/jpeg'

def call_gemini_vision(api_key, image_bytes, mime_type, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={api_key}"
    img_b64 = base64.b64encode(image_bytes).decode('utf-8')
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": img_b64
                    }
                }
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    data_bytes = json.dumps(payload).encode('utf-8')

    backoff_delays = [30, 60, 90, 120, 180]
    max_attempts = len(backoff_delays) + 1

    last_error = None
    for attempt in range(max_attempts):
        req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                text = result['candidates'][0]['content']['parts'][0]['text']
                return text
        except urllib.error.HTTPError as e:
            last_error = e
            if attempt < len(backoff_delays):
                delay = backoff_delays[attempt]
                print(f"⚠️ {MODEL_NAME} API HTTP {e.code} 錯誤，進行第 {attempt + 1} 次重試（等待 {delay} 秒）...", file=sys.stderr)
                time.sleep(delay)
                continue
            raise e
        except Exception as e:
            last_error = e
            if attempt < len(backoff_delays):
                delay = backoff_delays[attempt]
                print(f"⚠️ 連線/請求異常，進行第 {attempt + 1} 次重試（等待 {delay} 秒）...", file=sys.stderr)
                time.sleep(delay)
                continue
            raise e
    
    raise last_error if last_error else RuntimeError(f"All retries for {MODEL_NAME} failed")

def clean_json_string(raw_text):
    text = raw_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def normalize_date(date_str):
    if not date_str or '/' not in date_str:
        return date_str
    parts = date_str.split('/')
    m = parts[0].zfill(2)
    d = parts[1].zfill(2)
    return f"{m}/{d}"

def process_single_image(image_path, api_key):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"找不到圖片檔案：{image_path}")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    mime_type = get_mime_type(image_path)

    print(f"🔍 [{os.path.basename(image_path)}] 啟動第一階段 Vision OCR...", file=sys.stderr)
    first_text = call_gemini_vision(api_key, image_bytes, mime_type, SYSTEM_PROMPT)
    first_clean = clean_json_string(first_text)

    try:
        first_json = json.loads(first_clean)
    except Exception as e:
        print(f"[{os.path.basename(image_path)}] 第一階段 JSON 解析警告: {e}", file=sys.stderr)
        first_json = {}

    print(f"🧪 [{os.path.basename(image_path)}] 啟動第二階段雙重校對...", file=sys.stderr)
    verify_prompt = f"{VERIFICATION_PROMPT}\n\n初步提取 JSON：\n{json.dumps(first_json, ensure_ascii=False, indent=2)}"
    second_text = call_gemini_vision(api_key, image_bytes, mime_type, verify_prompt)
    second_clean = clean_json_string(second_text)

    try:
        final_json = json.loads(second_clean)
    except Exception:
        final_json = first_json

    for sched in final_json.get('schedules', []):
        sched['date'] = normalize_date(sched.get('date', ''))

    final_json['image_file'] = os.path.basename(image_path)

    # 直接輸出至同目錄同檔名不同副檔名 (.json)
    out_json_path = os.path.splitext(image_path)[0] + '.json'
    with open(out_json_path, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)
    print(f"💾 [{os.path.basename(image_path)}] 已寫入：{out_json_path}", file=sys.stderr)

    return out_json_path

def main():
    if len(sys.argv) < 2:
        print("錯誤：參數不正確。", file=sys.stderr)
        print("用法：python3 extract_schedule.py <圖片檔案路徑1> [圖片檔案路徑2 ...]", file=sys.stderr)
        sys.exit(1)

    image_paths = sys.argv[1:]
    api_key = load_api_key()
    if not api_key:
        print("錯誤：找不到 GEMINI_API_KEY 或 GOOGLE_API_KEY。", file=sys.stderr)
        sys.exit(1)

    created_files = []

    if len(image_paths) == 1:
        out_path = process_single_image(image_paths[0], api_key)
        created_files.append(out_path)
    else:
        print(f"🚀 啟動多圖卡獨立並行處理模式 (共 {len(image_paths)} 張圖卡)...", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=min(len(image_paths), 5)) as executor:
            future_to_path = {executor.submit(process_single_image, path, api_key): path for path in image_paths}
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    out_path = future.result()
                    created_files.append(out_path)
                except Exception as exc:
                    print(f"❌ [{os.path.basename(path)}] 處理發生例外: {exc}", file=sys.stderr)

    # 輸出產出的 JSON 檔案路徑清單
    output_summary = {
        "status": "success",
        "saved_json_files": created_files
    }
    print(json.dumps(output_summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
