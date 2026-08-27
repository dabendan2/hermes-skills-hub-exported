import asyncio
import os
import sys
from playwright.async_api import async_playwright

# Ensure the directory of this script is in python path to resolve local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from cgmh_utils import solve_captcha

# Authoritative registration booking for CGMH Hospital Network (e.g. V: Tucheng, 3: Linkou, etc.)
# Uses Tesseract OCR for automated CAPTCHA solving with fallback retry loops.

async def book_cgmh_appointment(id_number, birthday, dept_code, date_str, doctor_id, session_id, hospital_id="V", max_captcha_retries=5):
    """
    Main function to login and book a specific outpatient appointment at CGMH Hospital Network.
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
            # URL Structure for direct check-in registration
            url = f"https://register.cgmh.org.tw/Checkin/{hospital_id}/{dept_code}/{date_str}/{doctor_id}/{session_id}"
            print(f"Navigating to direct booking URL: {url}")
            await page.goto(url, timeout=60000)
            
            # Main retry loop for CAPTCHA solving (Stage 1)
            captcha_attempt = 0
            while captcha_attempt < max_captcha_retries:
                captcha_attempt += 1
                print(f"CAPTCHA Attempt {captcha_attempt}/{max_captcha_retries}...")
                
                # Wait for form elements to load
                await page.wait_for_selector("img[id='captcha']")
                await page.wait_for_selector("input[id='idNumber']")
                await page.wait_for_selector("input[id='birthday']")
                await page.wait_for_selector("input[id='verification']")
                
                # Fill user ID and Birthday
                await page.fill("input[id='idNumber']", id_number)
                await page.fill("input[id='birthday']", birthday)
                
                # Crop and capture the CAPTCHA image
                captcha_element = await page.query_selector("img[id='captcha']")
                if not captcha_element:
                    raise Exception("Unable to locate CAPTCHA element.")
                captcha_path = "/tmp/cgmh_book_captcha_temp.png"
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
                await page.fill("input[id='verification']", captcha_code)
                submit_btn = await page.query_selector("a.PatQueryChick")
                if not submit_btn:
                    raise Exception("Unable to locate Submit button.")
                await submit_btn.click()
                
                # Wait for action response (popup or transition)
                await asyncio.sleep(3.0)
                
                # 1. Check for immediate browser dialog errors
                if dialog_errors:
                    err_msg = dialog_errors[0]
                    print(f"CRITICAL ERROR: Browser dialog error encountered: '{err_msg}'")
                    raise Exception(f"Hospital booking verification failed: {err_msg}")
                
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
                        print(f"CRITICAL ERROR: System alert popup during verification: [{title}] {msg}")
                        raise Exception(f"Hospital booking verification failed: [{title}] {msg}")
                
                # 3. Successful bypass!
                print("Verification CAPTCHA verified successfully!")
                break
            else:
                raise Exception(f"Failed to solve CAPTCHA after {max_captcha_retries} attempts.")
            
            # --- Stage 2: Final confirmation page ---
            print("Successfully entered secondary booking page. Processing final confirmation...")
            await asyncio.sleep(2)
            
            # Check if there is an error message displayed on this stage
            body_text = await page.inner_text("body")
            
            # Wait, check if "送出掛號" button is on page
            if "送出掛號" in body_text:
                print("Found '送出掛號' page! Clicking the final submit button...")
                
                # Take pre-submit screenshot for safety
                await page.screenshot(path="/home/ubuntu/workspace/before_final_booking_submit.png")
                
                click_success = False
                # Try visible selectors for '送出掛號'
                for selector in ["a:has-text('送出掛號')", "button:has-text('送出掛號')", "input[value='送出掛號']", ".PatQueryChick", "input[type='submit']"]:
                    try:
                        el = await page.query_selector(selector)
                        if el and await el.is_visible():
                            await el.click()
                            print(f"Clicked using selector: {selector}")
                            click_success = True
                            break
                    except Exception as click_err:
                        print(f"Failed clicking selector {selector}: {click_err}")
                
                if not click_success:
                    # Fallback text search click
                    elements = await page.query_selector_all("a, button, input")
                    for el in elements:
                        text = await el.text_content() or await el.get_attribute("value") or ""
                        if "送出掛號" in text:
                            await el.click()
                            click_success = True
                            break
                            
                if not click_success:
                    raise Exception("Failed to locate '送出掛號' final submit button.")
                
                # Wait 5 seconds for confirmation to complete
                print("Waiting 5 seconds for final booking confirmation results...")
                await asyncio.sleep(5)
                
                # Check for post-submission error popups (e.g. duplicating registrations)
                alert_visible_post = await page.evaluate("""() => {
                    const el = document.querySelector("div.sweet-alert.showSweetAlert.visible");
                    if (el && el.style.display !== 'none') {
                        const h2 = el.querySelector("h2") ? el.querySelector("h2").innerText : "";
                        const p = el.querySelector("p") ? el.querySelector("p").innerText : "";
                        return { visible: true, title: h2, message: p };
                    }
                    return { visible: false };
                }""")
                
                if alert_visible_post["visible"]:
                    msg_post = alert_visible_post["message"]
                    title_post = alert_visible_post["title"]
                    print(f"CRITICAL ERROR: Post-submit alert popup: [{title_post}] {msg_post}")
                    raise Exception(f"Booking final submission failed: [{title_post}] {msg_post}")
                
                # Capture final confirmation page screenshot
                await page.screenshot(path="/home/ubuntu/workspace/booking_final_result.png", full_page=True)
                print("Booking complete. Saved booking_final_result.png")
                
                final_text = await page.inner_text("body")
                return {"page_text": final_text, "attempts": captcha_attempt}
            else:
                # Check if there is some other validation error on the page text instead of alert
                print("CRITICAL ERROR: Did not reach '送出掛號' stage. Details:")
                # Crop/Save screenshot of error state
                await page.screenshot(path="/home/ubuntu/workspace/booking_stage_error.png", full_page=True)
                
                # Try to extract actual warning message
                warn_msg = await page.evaluate("""() => {
                    const el = document.querySelector(".warning, .error, .danger, td[colspan]");
                    return el ? el.innerText : "Unknown error page state";
                }""")
                raise Exception(f"Failed to enter booking confirmation page. Reason: {warn_msg}")
                
        except Exception as e:
            print(f"Execution Error: {e}")
            raise e
        finally:
            await browser.close()

if __name__ == "__main__":
    # Parameters for booking
    id_val = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("USER_ID_NUMBER")
    if not id_val:
        raise ValueError("請提供身份證字號 (CLI 參數或 USER_ID_NUMBER 環境變數)")
    bday_val = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("USER_BIRTHDAY_ROC")
    if not bday_val:
        raise ValueError("請提供民國生日 (CLI 參數或 USER_BIRTHDAY_ROC 環境變數)")
    dept_val = sys.argv[3] if len(sys.argv) > 3 else "V1200A"
    date_val = sys.argv[4] if len(sys.argv) > 4 else "20260722"
    doc_val = sys.argv[5] if len(sys.argv) > 5 else "1985"
    sess_val = sys.argv[6] if len(sys.argv) > 6 else "2"
    hosp_val = sys.argv[7] if len(sys.argv) > 7 else "V"
    
    try:
        res = asyncio.run(book_cgmh_appointment(id_val, bday_val, dept_val, date_val, doc_val, sess_val, hosp_val))
        final_page = res["page_text"]
        attempts = res["attempts"]
        
        print("\n=== BOOKING_SUCCESS ===")
        print(f"驗證碼嘗試次數：{attempts} 次")
        print("掛號申請已成功送出！最終頁面摘要：")
        # Extract confirmation details if possible
        lines = final_page.splitlines()
        for line in lines:
            if "掛號成功" in line or "預約成功" in line or "序號" in line or "看診號" in line  or "日期" in line or "時間" in line or "上午" in line or "下午" in line or "地點" in line or "門診" in line:
                cleaned_line = line.strip()
                if cleaned_line and len(cleaned_line) > 2:
                    print(f"  {cleaned_line}")
        print("=======================")
    except Exception as ex:
        print(f"\n=== BOOKING_FAILURE ===\n{ex}", file=sys.stderr)
        sys.exit(1)
