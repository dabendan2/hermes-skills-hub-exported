import asyncio
import os
import sys
from playwright.async_api import async_playwright

# Ensure the directory of this script is in python path to resolve local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from cgmh_utils import solve_captcha

# Authoritative registration cancellation for CGMH Hospital Network (e.g. V: Tucheng, 3: Linkou, etc.)
# Uses Tesseract OCR for automated CAPTCHA solving with fallback retry loops.

async def cancel_cgmh_registration(id_number, birthday, target_date, doctor_name, hospital_id="V", max_captcha_retries=5):
    """
    Main function to login and cancel a specific registration at CGMH Hospital Network.
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
        
        # Track browser alerts/dialogs for non-captcha errors
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
            
            # Main retry loop for CAPTCHA solving
            captcha_attempt = 0
            while captcha_attempt < max_captcha_retries:
                captcha_attempt += 1
                print(f"CAPTCHA Attempt {captcha_attempt}/{max_captcha_retries}...")
                
                # Wait for form elements to load
                await page.wait_for_selector("img[id='captcha']")
                await page.wait_for_selector("input.std.mb16.w100")
                await page.wait_for_selector("input[id='birthday']")
                await page.wait_for_selector("input.std.mr8")
                
                # Fill user ID and Birthday
                await page.fill("input.std.mb16.w100", id_number)
                await page.fill("input[id='birthday']", birthday)
                
                # Crop and capture the CAPTCHA image
                captcha_element = await page.query_selector("img[id='captcha']")
                if not captcha_element:
                    raise Exception("Unable to locate CAPTCHA element.")
                captcha_path = "/tmp/cgmh_captcha_temp.png"
                if os.path.exists(captcha_path):
                    os.remove(captcha_path)
                await captcha_element.screenshot(path=captcha_path)
                
                # Run OCR
                captcha_code = solve_captcha(captcha_path)
                print(f"OCR recognized CAPTCHA: '{captcha_code}'")
                
                # Optimization: if the recognized string is not 4 chars, refresh and retry instantly
                if len(captcha_code) != 4:
                    print("OCR length was not 4. Refreshing CAPTCHA directly without submitting...")
                    await captcha_element.click()
                    await asyncio.sleep(1.5)
                    continue
                
                # Fill CAPTCHA and submit
                await page.fill("input.std.mr8", captcha_code)
                submit_btn = await page.query_selector("button:has-text('送出查詢')") or await page.query_selector(".btn[value='送出查詢']")
                if not submit_btn:
                    raise Exception("Unable to locate Submit button.")
                await submit_btn.click()
                
                # Wait for action response (popup or transition)
                await asyncio.sleep(2.5)
                
                # 1. Check for immediate browser dialog errors
                if dialog_errors:
                    err_msg = dialog_errors[0]
                    print(f"CRITICAL ERROR: Browser dialog error encountered: '{err_msg}'")
                    raise Exception(f"Hospital registration query failed: {err_msg}")
                
                # 2. Check for SweetAlert error popups
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
                        # Click "確定!" button to close the alert
                        confirm_btn = await page.query_selector("div.sweet-alert.showSweetAlert.visible button.confirm")
                        if confirm_btn:
                            await confirm_btn.click()
                        await asyncio.sleep(1)
                        # Click CAPTCHA to refresh
                        await page.click("img[id='captcha']")
                        await asyncio.sleep(1.5)
                        continue
                    else:
                        # Other system error, raise immediately!
                        print(f"CRITICAL ERROR: System alert popup: [{title}] {msg}")
                        raise Exception(f"Hospital registration query failed: [{title}] {msg}")
                
                # 3. Successful bypass!
                print("CAPTCHA verified successfully!")
                break
            else:
                raise Exception(f"Failed to solve CAPTCHA after {max_captcha_retries} attempts.")
            
            # Check if there are no registrations
            body_text = await page.inner_text("body")
            if "查無資料，請確認輸入資料正確性" in body_text:
                raise Exception("查無掛號資料，無法進行取消掛號。")
                
            # Locate target registration row
            tables = await page.query_selector_all("table")
            target_row = None
            cancel_link = None
            
            for table in tables:
                class_attr = await table.get_attribute("class") or ""
                if "query" in class_attr or "table" in class_attr:
                    rows = await table.query_selector_all("tbody#regViewList tr")
                    for row in rows:
                        row_text = await row.inner_text()
                        if target_date in row_text and doctor_name in row_text:
                            target_row = row
                            cancel_link = await row.query_selector("a.btn.cancel")
                            break
                    if target_row:
                        break
                        
            if not target_row or not cancel_link:
                raise Exception(f"找不到符合條件的掛號紀錄：日期 {target_date}, 醫師 {doctor_name}")
                
            print(f"找到符合目標的掛號，準備點擊取消：{target_date} {doctor_name}")
            
            # Click Cancel Appointment Link to show confirmation modal
            await cancel_link.click()
            await asyncio.sleep(1.5)
            
            # Click "確定" inside modal-cancel
            confirm_btn = await page.query_selector("div#modal-cancel button.CancelReg")
            if not confirm_btn:
                confirm_btn = await page.query_selector("button.CancelReg")
                
            if confirm_btn:
                print("點擊確認取消彈出視窗...")
                await confirm_btn.click()
            else:
                print("警告：未找到 modal-cancel 的確認按鈕，嘗試點擊包含文字「確定」的按鈕...")
                fallback_confirm = await page.query_selector("button:has-text('確定')")
                if fallback_confirm:
                    await fallback_confirm.click()
                else:
                    raise Exception("無法定位取消確認按鈕。")
                    
            # Wait for response alert
            await asyncio.sleep(3.5)
            
            # Check for SweetAlert confirmation popup
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
                print(f"取消結果彈出視窗: [{title}] {msg}")
                # Click confirm to dismiss final popup
                final_ok_btn = await page.query_selector("div.sweet-alert.showSweetAlert.visible button.confirm")
                if final_ok_btn:
                    await final_ok_btn.click()
                await asyncio.sleep(1)
                
                # Take final state screenshot
                await page.screenshot(path="/home/ubuntu/workspace/cancellation_outcome.png", full_page=True)
                return {"message": msg, "attempts": captcha_attempt}
            else:
                await page.screenshot(path="/home/ubuntu/workspace/cancellation_outcome.png", full_page=True)
                return {"message": "取消動作已送出（無彈出結果視窗，請查詢驗證）", "attempts": captcha_attempt}
                
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
    date_val = sys.argv[3] if len(sys.argv) > 3 else "2026-07-22"
    doc_val = sys.argv[4] if len(sys.argv) > 4 else os.environ.get("DOCTOR_NAME", "張三醫師")
    hosp_val = sys.argv[5] if len(sys.argv) > 5 else "V"
    
    try:
        res = asyncio.run(cancel_cgmh_registration(id_val, bday_val, date_val, doc_val, hosp_val))
        result_msg = res["message"]
        attempts = res["attempts"]
        
        print("\n=== CANCEL_SUCCESS ===")
        print(f"驗證碼嘗試次數：{attempts} 次")
        print(f"取消執行結果：{result_msg}")
        print("======================")
    except Exception as ex:
        print(f"\n=== CANCEL_FAILURE ===\n{ex}", file=sys.stderr)
        sys.exit(1)
