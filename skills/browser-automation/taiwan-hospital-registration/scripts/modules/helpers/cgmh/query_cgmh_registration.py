import asyncio
import os
import sys
from playwright.async_api import async_playwright

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from cgmh_utils import solve_captcha

async def query_cgmh_registration(id_number, birthday, hospital_id="V", max_captcha_retries=5):
    """
    Main function to login and query CGMH registrations.
    Retries automatically on CAPTCHA errors up to max_captcha_retries times.
    """
    async with async_playwright() as p:
        print("Initializing headless browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 1600}
        )
        page = await context.new_page()
        
        dialog_errors = []
        async def handle_dialog(dialog):
            msg = dialog.message
            print(f"[Dialog Alert] {msg}")
            await dialog.accept()
            if "驗證碼" not in msg:
                dialog_errors.append(msg)
                
        page.on("dialog", handle_dialog)
        
        try:
            url = f"https://register.cgmh.org.tw/Query/{hospital_id}"
            print(f"Navigating to CGMH registration query: {url}")
            await page.goto(url, timeout=60000)
            
            captcha_attempt = 0
            while captcha_attempt < max_captcha_retries:
                captcha_attempt += 1
                print(f"CAPTCHA Attempt {captcha_attempt}/{max_captcha_retries}...")
                
                await page.wait_for_selector("img[id='captcha']")
                await page.wait_for_selector("input[name='idNumber']")
                await page.wait_for_selector("input[id='birthday']")
                await page.wait_for_selector("input[name='verification']")
                
                # Fill user ID (uppercase) and Birthday
                await page.fill("input[name='idNumber']", str(id_number).strip().upper())
                await page.fill("input[id='birthday']", str(birthday).strip())
                
                captcha_element = await page.query_selector("img[id='captcha']")
                if not captcha_element:
                    raise Exception("Unable to locate CAPTCHA element.")
                captcha_path = "/tmp/cgmh_captcha_temp.png"
                if os.path.exists(captcha_path):
                    os.remove(captcha_path)
                await captcha_element.screenshot(path=captcha_path)
                
                captcha_code = solve_captcha(captcha_path)
                print(f"OCR recognized CAPTCHA: '{captcha_code}'")
                
                if len(captcha_code) != 4:
                    print("OCR length was not 4. Refreshing CAPTCHA directly without submitting...")
                    await captcha_element.click()
                    await asyncio.sleep(1.5)
                    continue
                
                await page.fill("input[name='verification']", captcha_code)
                submit_btn = await page.query_selector("button:has-text('送出查詢')") or await page.query_selector(".btn[value='送出查詢']")
                if not submit_btn:
                    raise Exception("Unable to locate Submit button.")
                await submit_btn.click()
                
                await asyncio.sleep(2.5)
                
                if dialog_errors:
                    err_msg = dialog_errors.pop(0)
                    print(f"CRITICAL ERROR: Browser dialog error encountered: '{err_msg}'")
                    raise Exception(f"Hospital registration query failed: {err_msg}")
                
                alert_visible = await page.evaluate("""() => {
                    const el = document.querySelector("div.sweet-alert.showSweetAlert.visible");
                    if (el && el.style.display !== 'none') {
                        const h2 = el.querySelector("h2") ? el.querySelector("h2").innerText : "";
                        const p = el.querySelector("p") ? el.querySelector("p").innerText : "";
                        return { visible: true, title: h2, message: p };
                    }
                    return { visible: false };
                }""")
                
                if alert_visible["visible"]:
                    msg = alert_visible["message"]
                    title = alert_visible["title"]
                    print(f"Alert Popup Detected: [{title}] {msg}")
                    
                    if "驗證碼" in msg or "驗證碼比對錯誤" in msg:
                        print("CAPTCHA incorrect. Retrying CAPTCHA solver...")
                        confirm_btn = await page.query_selector("div.sweet-alert.showSweetAlert.visible button.confirm")
                        if confirm_btn:
                            await confirm_btn.click()
                        await asyncio.sleep(1)
                        await page.click("img[id='captcha']")
                        await asyncio.sleep(1.5)
                        continue
                    else:
                        print(f"CRITICAL ERROR: System alert popup: [{title}] {msg}")
                        raise Exception(f"Hospital registration query failed: [{title}] {msg}")
                
                print("CAPTCHA verified successfully!")
                break
            else:
                raise Exception(f"Failed to solve CAPTCHA after {max_captcha_retries} attempts.")
            
            body_text = await page.inner_text("body")
            
            if "查無資料，請確認輸入資料正確性" in body_text:
                print("Query outcome: No active registrations found.")
                return {"appointments": [], "attempts": captcha_attempt}
                
            tables = await page.query_selector_all("table")
            appointments = []
            
            for table in tables:
                class_attr = await table.get_attribute("class") or ""
                if "query" in class_attr or "table" in class_attr:
                    rows = await table.query_selector_all("tbody#regViewList tr")
                    for row in rows:
                        tds = await row.query_selector_all("td")
                        if len(tds) >= 10:
                            hospital = (await tds[0].inner_text()).strip()
                            date = (await tds[1].inner_text()).strip()
                            session = (await tds[2].inner_text()).strip()
                            dept = (await tds[3].inner_text()).strip()
                            doctor = (await tds[4].inner_text()).strip()
                            seq_num = (await tds[5].inner_text()).strip()
                            location = (await tds[8].inner_text()).strip()
                            expected_time = (await tds[9].inner_text()).strip()
                            
                            appointments.append({
                                "hospital": hospital,
                                "date": date,
                                "session": session,
                                "dept": dept,
                                "doctor": doctor,
                                "seq_num": seq_num,
                                "location": location,
                                "expected_time": expected_time
                            })
            return {"appointments": appointments, "attempts": captcha_attempt}
            
        except Exception as e:
            print(f"Execution Error: {e}")
            raise e
        finally:
            await browser.close()

if __name__ == "__main__":
    id_val = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("USER_ID_NUMBER")
    if not id_val:
        raise ValueError("請提供身份證字號 (CLI 參數或 USER_ID_NUMBER 環境變數)")
    bday_val = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("USER_BIRTHDAY_ROC")
    if not bday_val:
        raise ValueError("請提供民國生日 (CLI 參數或 USER_BIRTHDAY_ROC 環境變數)")
    hosp_val = sys.argv[3] if len(sys.argv) > 3 else "V"
    
    try:
        res = asyncio.run(query_cgmh_registration(id_val, bday_val, hosp_val))
        results = res["appointments"]
        attempts = res["attempts"]
        print("\n=== QUERY_SUCCESS ===")
        print(f"驗證碼嘗試次數：{attempts} 次")
        if not results:
            print(f"目前在該院區 ({hosp_val}) 沒有任何掛號紀錄。")
        else:
            print(f"查詢到 {len(results)} 筆掛號紀錄：")
            for idx, apt in enumerate(results, 1):
                print(f"\n第 {idx} 筆：")
                print(f"  院區：{apt['hospital']}")
                print(f"  日期：{apt['date']}")
                print(f"  診別：{apt['session']}")
                print(f"  科別：{apt['dept']}")
                print(f"  醫師：{apt['doctor']} 醫師")
                print(f"  看診序號：{apt['seq_num']}")
                print(f"  就診地點：{apt['location']}")
                print(f"  預估看診時間：{apt['expected_time']}")
        print("=====================")
    except Exception as ex:
        print(f"\n=== QUERY_FAILURE ===\n{ex}", file=sys.stderr)
        sys.exit(1)
