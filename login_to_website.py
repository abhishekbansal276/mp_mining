import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import easyocr

from emm11_processor import process_emm11

reader = easyocr.Reader(['en'], gpu=False)

async def login_to_website(data, log_callback=print):
    log_callback(f"🔹 Received `data` parameter: {data}")

    aadhar_number = "752883893309"
    password = "Nic@8574"
    max_attempts = 5

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            log_callback("🔹 Navigating to login page...")
            await page.goto("https://upmines.upsdc.gov.in/DefaultLicense.aspx", timeout=20000)
        except PlaywrightTimeoutError:
            log_callback("❌ Failed to load login page. Server may be down.")
            await browser.close()
            return []

        await page.wait_for_timeout(2000)
        login_success = False

        for attempt in range(1, max_attempts + 1):
            log_callback(f"🔹 Login attempt #{attempt}")
            try:
                await page.fill("#ContentPlaceHolder1_txtAadharNumber", aadhar_number)
                await page.fill("#ContentPlaceHolder1_txtPassword", password)

                captcha_elem = await page.query_selector("#Captcha")
                captcha_bytes = await captcha_elem.screenshot()
                result = reader.readtext(captcha_bytes, detail=0)
                captcha_text = result[0].strip() if result else ""
                log_callback(f"🔹 Captcha recognized: '{captcha_text}'")

                if not captcha_text.isdigit():
                    log_callback("⚠️ Captcha recognition failed, reloading page...")
                    await page.reload()
                    await page.wait_for_timeout(1500)
                    continue

                await page.fill("#ContentPlaceHolder1_txtCaptcha", captcha_text)
                await page.click("#ContentPlaceHolder1_btn_captcha")

                try:
                    await page.wait_for_selector('#pnlMenuEng', timeout=5000)
                    login_success = True
                    log_callback("✅ Login successful")
                    break
                except PlaywrightTimeoutError:
                    log_callback("⚠️ Login failed, retrying...")
                    await page.reload()
                    await page.wait_for_timeout(2000)

            except Exception as e:
                log_callback(f"❌ Exception during login attempt: {e}")
                await page.reload()
                await page.wait_for_timeout(2000)

        if not login_success:
            log_callback("❌ All login attempts failed.")
            await browser.close()
            return []

        # --- Convert fetched data to ISTP/OSTP pairs ---
        tp_pairs = []
        for record in data:
            istp = record.get("istp")
            ostp = record.get("ostp")
            if istp and ostp:
                tp_pairs.append((istp, ostp))
            else:
                log_callback(f"⚠️ Skipping invalid record: {record}")

        if not tp_pairs:
            log_callback("⚠️ No valid TP pairs found to process.")
            await browser.close()
            return data

        log_callback(f"🔹 Passing {len(tp_pairs)} TP pairs to process_emm11")
        unused_tp_list = await process_emm11(page, tp_pairs, log_callback=log_callback)

        # --- Mark entries in `data` with unused key ---
        for record in data:
            istp = record.get("istp")
            record["unused"] = any(istp == u[0] for u in unused_tp_list)

        await browser.close()
        log_callback("🔹 Browser closed, process complete.")

        return data  # <- Now returns full data list with 'unused' key
