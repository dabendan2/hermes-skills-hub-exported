import asyncio
import os
import sys
from playwright.async_api import async_playwright

# Authoritative consultation progress tracker for CGMH Hospital Network (e.g. V: Tucheng, 3: Linkou, etc.)
# Selects the appropriate specialty group and session, submits the query, and extracts calling numbers.

def get_specialty_group(dept_name):
    """
    Maps a department name to its standard CGMH specialty group code.
    """
    if not dept_name:
        return "02" # Default to Internal Medicine
        
    dn = dept_name.strip()
    
    # 內科系
    if any(k in dn for k in ["胃腸", "肝膽", "內科", "心臟", "腎臟", "新陳代謝", "感染", "風濕", "免疫", "血液", "腫瘤", "胸腔內"]):
        return "02"
    # 外科系
    elif any(k in dn for k in ["外科", "骨", "泌尿", "整形", "直腸", "麻醉", "神經外"]):
        return "03"
    # 牙科
    elif "牙" in dn:
        return "04"
    # 婦產科
    elif any(k in dn for k in ["婦", "產"]):
        return "05"
    # 兒童專科
    elif any(k in dn for k in ["兒", "小兒"]):
        return "06"
    # 中醫
    elif "中醫" in dn:
        return "08"
    # 預設其它專科（包含耳鼻喉科、眼科、皮膚科、復健科、精神科、神經內科等）
    else:
        return "07"

async def query_cgmh_progress(hospital_id, dept_name, doctor_name=None, session_id="2"):
    """
    Scrapes register.cgmh.org.tw/Progress/{hospital_id} to track calling progress.
    session_id: '1' (morning), '2' (afternoon), '3' (evening)
    """
    async with async_playwright() as p:
        print("Initializing headless browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            url = f"https://register.cgmh.org.tw/Progress/{hospital_id}"
            print(f"Navigating to Progress page: {url}")
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("select[name='dept']")
            
            # Map department keyword to specialty group code
            group_code = get_specialty_group(dept_name)
            print(f"Mapped department '{dept_name}' to specialty group '{group_code}'")
            
            # Select group and session
            await page.select_option("select[name='dept']", group_code)
            await page.select_option("select[name='time']", session_id)
            await asyncio.sleep(0.5)
            
            # Click "送出查詢"
            submit_btn = await page.query_selector("button:has-text('送出查詢')")
            if not submit_btn:
                raise Exception("Unable to locate '送出查詢' button.")
                
            await submit_btn.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2.0)
            
            # Parse table rows
            tables = await page.query_selector_all("table")
            progress_list = []
            
            for table in tables:
                text = await table.inner_text()
                if "掛號科別" in text and "看診位置" in text:
                    rows = await table.query_selector_all("tr")
                    for r in rows[1:]: # Skip header
                        tds = await r.query_selector_all("td")
                        if len(tds) < 5:
                            continue
                            
                        dept = (await tds[0].inner_text()).strip()
                        location = (await tds[1].inner_text()).strip()
                        doctor = (await tds[2].inner_text()).strip()
                        curr_num = (await tds[3].inner_text()).strip()
                        next_num = (await tds[4].inner_text()).strip()
                        
                        # Apply filters if provided
                        if dept_name and dept_name not in dept:
                            continue
                        if doctor_name and doctor_name not in doctor:
                            continue
                            
                        progress_list.append({
                            "department": dept,
                            "location": location,
                            "doctor_name": doctor,
                            "current_number": curr_num,
                            "next_number": next_num
                        })
                    break # Only parse the primary progress table
                    
            return progress_list
            
        except Exception as e:
            print(f"Progress Query Error: {e}")
            raise e
        finally:
            await browser.close()

if __name__ == "__main__":
    hosp_val = sys.argv[1] if len(sys.argv) > 1 else "V"
    dept_val = sys.argv[2] if len(sys.argv) > 2 else "胃腸肝膽科"
    doc_val = sys.argv[3] if len(sys.argv) > 3 else None
    sess_val = sys.argv[4] if len(sys.argv) > 4 else "2" # Default to afternoon
    
    try:
        results = asyncio.run(query_cgmh_progress(hosp_val, dept_val, doc_val, sess_val))
        print("\n=== PROGRESS_SUCCESS ===")
        print(f"院區代碼：{hosp_val} | 診別代碼：{sess_val}")
        
        if not results:
            print(f"目前在該診別中，未找到科別「{dept_val}」" + (f" 醫師「{doc_val}」" if doc_val else "") + " 的開診叫號進度。")
        else:
            print(f"查詢到 {len(results)} 間診間叫號進度：")
            for p in results:
                print(f"\n科別：{p['department']} ({p['location']})")
                print(f"  看診醫師：{p['doctor_name']} 醫師")
                print(f"  目前看診號碼：{p['current_number'] if p['current_number'] else '未開診/待診'}")
                print(f"  下一個看診號碼：{p['next_number']}")
        print("========================")
    except Exception as ex:
        print(f"\n=== PROGRESS_FAILURE ===\n{ex}", file=sys.stderr)
        sys.exit(1)
