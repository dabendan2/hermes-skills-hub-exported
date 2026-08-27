# CGMH CAPTCHA Solving Pattern

The Chang Gung Memorial Hospital (CGMH) portal has very strict session timeouts and CAPTCHAs that refresh frequently. This reference documents the "Background-Poll" pattern for reliable automation.

## The Challenge
1. **Short Lifespan**: CAPTCHAs expire if not submitted within ~60 seconds.
2. **Session Persistence**: The CAPTCHA is tied to the specific browser context/tab.
3. **Vision Processing Latency**: `vision_analyze` can take 10-20 seconds, often leaving very little time for the agent to receive the result and make a second tool call to submit the form.

## The Solution: Background Polling
Run a Python script in the background that:
1. Navigates to the page and waits for the CAPTCHA.
2. Saves the CAPTCHA to a temporary path (e.g., `/tmp/current_captcha.png`).
3. Polls a local "answer file" (e.g., `/tmp/captcha_answer.txt`) while keeping the browser open.
4. When the agent writes the answer to that file, the script immediately fills the form and submits.

## Implementation Example
```python
import asyncio
import os
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="...")
        page = await context.new_page()
        try:
            await page.goto("https://register.cgmh.org.tw/Query/V")
            await page.wait_for_selector("input[name='verification']")
            
            # Save captcha for agent to see
            captcha_img = await page.query_selector("img[alt='驗證碼']")
            await captcha_img.screenshot(path="/tmp/current_captcha.png")
            print("CAPTCHA_READY")
            
            answer_file = "/tmp/captcha_answer.txt"
            # Wait loop for agent input
            for _ in range(60):
                if os.path.exists(answer_file):
                    with open(answer_file, "r") as f:
                        answer = f.read().strip()
                    # Perform submission logic...
                    return
                await asyncio.sleep(1)
        finally:
            await browser.close()
```

## Agent Workflow (User-Approved Flow)
1. Start the script via `terminal(background=true)`.
2. Wait for `CAPTCHA_READY` in the log or check the file existence.
3. Use `vision_analyze` on the screenshot to get a suggested answer.
4. Send the screenshot (using `MEDIA:/home/ubuntu/workspace/captcha_large.png` or similar) and the suggested answer to the user.
5. Wait for the user to confirm the suggested answer or provide the correct one (using `clarify` or asking directly in the chat).
6. Once confirmed, write the answer: `echo "CONFIRMED_ANSWER" > /tmp/captcha_answer.txt` (or via `write_file`).
7. `process(action='wait', ...)` to see the result.
