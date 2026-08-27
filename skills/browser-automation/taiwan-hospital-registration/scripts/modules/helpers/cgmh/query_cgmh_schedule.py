import asyncio
import os
import sys
from playwright.async_api import async_playwright

# Authoritative outpatient schedule query for CGMH Hospital Network (e.g. V: Tucheng, 3: Linkou, etc.)
# Scrapes the department's weekly table and parses each clinic slot's status.

async def query_cgmh_schedule(hospital_id, dept_code, doctor_name=None):
    """
    Scrapes register.cgmh.org.tw/Department_WEEK/{hospital_id}/{dept_code} and parses doctor slots.
    """
    async with async_playwright() as p:
        print("Initializing headless browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            url = f"https://register.cgmh.org.tw/Department_WEEK/{hospital_id}/{dept_code}"
            print(f"Navigating to Department WEEK page: {url}")
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("table.department-table")
            
            # Extract department name
            dept_name_el = await page.query_selector("h1, h2, .title, .breadcrumb")
            dept_name = "該科別"
            if dept_name_el:
                dept_name = (await dept_name_el.inner_text()).strip()
            
            # Parse table
            table = await page.query_selector("table.department-table")
            if not table:
                raise Exception("Unable to locate department-table element.")
                
            rows = await table.query_selector_all("tr")
            slots = []
            
            # Header column parsing (usually: 日期, 上午, 下午, 晚間)
            headers = []
            if len(rows) > 0:
                th_elements = await rows[0].query_selector_all("th")
                headers = [(await th.inner_text()).strip() for th in th_elements]
            
            # Row loop
            for r in rows[1:]:
                # Select both th and td elements inside the row to preserve Date (th) and Sessions (td)
                cells = await r.query_selector_all("xpath=./*")
                if len(cells) < 2:
                    continue
                    
                # First cell is the Date (e.g. "06/24（三）" in <th>)
                date_text = (await cells[0].inner_text()).strip()
                
                # Check remaining session cells (上午, 下午, 晚間 in <td>)
                for idx, td in enumerate(cells[1:], 1):
                    session_name = headers[idx] if idx < len(headers) else f"診別 {idx}"
                    
                    # Split cells by line breaks to get individual doctor slots
                    td_html = await td.inner_html()
                    lines = [l.strip() for l in td_html.replace("<br>", "\n").replace("<br/>", "\n").splitlines() if l.strip()]
                    
                    # Get inner texts cleanly
                    items_data = await page.evaluate("""(td) => {
                        return Array.from(td.childNodes)
                            .map(n => n.textContent ? n.textContent.trim() : "")
                            .filter(t => t.length > 0);
                    }""", td)
                    
                    cleaned_items = []
                    for item in items_data:
                        parts = [x.strip() for x in item.split("\n") if x.strip()]
                        cleaned_items.extend(parts)
                        
                    for slot_raw in cleaned_items:
                        # Parse slot text e.g., "21985 林士驊(停診)" or "10585 林成俊"
                        parts = slot_raw.split()
                        if len(parts) < 2:
                            continue
                            
                        code_num = parts[0]
                        rest = " ".join(parts[1:])
                        
                        # Extract session_id (first digit) and doctor_id (remaining digits)
                        if len(code_num) >= 5 and code_num.isdigit():
                            sess_id = code_num[0]
                            doc_id = code_num[1:]
                        else:
                            sess_id = str(idx)
                            doc_id = code_num
                            
                        doc_name = rest
                        status = "可掛號 (Available)"
                        
                        if "(停診)" in rest:
                            doc_name = rest.replace("(停診)", "").strip()
                            status = "停診 (Canceled)"
                        elif "(額滿)初診可掛" in rest:
                            doc_name = rest.replace("(額滿)初診可掛", "").strip()
                            status = "額滿-初診可掛 (Full - First Visit Only)"
                        elif "(額滿)" in rest:
                            doc_name = rest.replace("(額滿)", "").strip()
                            status = "額滿 (Full)"
                        elif "超過掛號開放時間" in rest:
                            doc_name = rest.replace("超過掛號開放時間", "").strip()
                            status = "超過掛號開放時間 (Closed)"
                        
                        if doctor_name and doctor_name not in doc_name:
                            continue
                            
                        slots.append({
                            "date": date_text,
                            "session_id": sess_id,
                            "session_name": session_name,
                            "doctor_id": doc_id,
                            "doctor_name": doc_name,
                            "status": status,
                            "raw_code": code_num
                        })
            return {"slots": slots, "dept_name": dept_name}
            
        except Exception as e:
            print(f"Schedule Query Error: {e}")
            raise e
        finally:
            await browser.close()

def apt_status_color(status):
    if "停診" in status:
        return f"🔴 {status}"
    elif "額滿" in status:
        return f"🟡 {status}"
    elif "超過掛號開放時間" in status:
        return f"⚫ {status}"
    else:
        return f"🟢 {status}"

if __name__ == "__main__":
    hosp_val = sys.argv[1] if len(sys.argv) > 1 else "V"
    dept_val = sys.argv[2] if len(sys.argv) > 2 else "V1200A"
    doc_filter = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        res = asyncio.run(query_cgmh_schedule(hosp_val, dept_val, doc_filter))
        slots_list = res["slots"]
        dept_name = res["dept_name"]
        
        print("\n=== SCHEDULE_SUCCESS ===")
        print(f"院區代碼：{hosp_val} | 科別：{dept_name} ({dept_val})")
        if doc_filter:
            print(f"篩選醫師：{doc_filter}")
            
        if not slots_list:
            print("查無任何符合條件的門診班表。")
        else:
            print(f"查詢到 {len(slots_list)} 門診時段：")
            current_date = ""
            for slot in slots_list:
                if slot["date"] != current_date:
                    current_date = slot["date"]
                    print(f"\n📅 {current_date}:")
                print(f"  [{slot['session_name']}] {apt_status_color(slot['status'])} {slot['doctor_name']} 醫師 (代碼: {slot['doctor_id']}, 診號前碼: {slot['session_id']})")
        print("=========================")
    except Exception as ex:
        print(f"\n=== SCHEDULE_FAILURE ===\n{ex}", file=sys.stderr)
        sys.exit(1)
