import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import easyocr
from emm11_processor import process_emm11

reader = easyocr.Reader(['en'], gpu=False)

async def login_to_website(data, log_callback=print):
    aadhar_number = "752883893309"
    password = "Nic@8574"
    max_attempts = 5

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto("https://upmines.upsdc.gov.in/DefaultLicense.aspx", timeout=20000)
        except PlaywrightTimeoutError:
            log_callback("❌ Failed to load login page.")
            await browser.close()
            return []

        login_success = False
        for attempt in range(1, max_attempts + 1):
            try:
                await page.fill("#ContentPlaceHolder1_txtAadharNumber", aadhar_number)
                await page.fill("#ContentPlaceHolder1_txtPassword", password)

                captcha_elem = await page.query_selector("#Captcha")
                captcha_bytes = await captcha_elem.screenshot()
                result = reader.readtext(captcha_bytes, detail=0)
                captcha_text = result[0].strip() if result else ""

                if not captcha_text.isdigit():
                    await page.reload()
                    await page.wait_for_timeout(1500)
                    continue

                await page.fill("#ContentPlaceHolder1_txtCaptcha", captcha_text)
                await page.click("#ContentPlaceHolder1_btn_captcha")

                try:
                    await page.wait_for_selector('#pnlMenuEng', timeout=5000)
                    login_success = True
                    break
                except PlaywrightTimeoutError:
                    await page.reload()
                    await page.wait_for_timeout(2000)

            except Exception:
                await page.reload()
                await page.wait_for_timeout(2000)

        if not login_success:
            log_callback("❌ All login attempts failed.")
            await browser.close()
            return []

        # Convert fetched data to ISTP/OSTP pairs
        tp_pairs = [(r["istp"], r["ostp"]) for r in data if r.get("istp") and r.get("ostp")]

        if not tp_pairs:
            await browser.close()
            return data

        unused_tp_list = await process_emm11(page, tp_pairs, log_callback=log_callback)

        # Mark entries with 'unused' key
        for record in data:
            istp = record.get("istp")
            record["unused"] = any(istp == u[0] for u in unused_tp_list)

        await browser.close()
        return data
