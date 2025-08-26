import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- Config ---
BASE_URL = "https://upmines.upsdc.gov.in//Transporter/PrintTransporterFormVehicleCheckValidOrNot.aspx?eId={}"
HEADLESS = True  # <-- Don't Show the browser
CONCURRENCY_LIMIT = 5  # You can adjust concurrency
SLOW_MO = 50  # Slow down actions for visibility

# --- Fetch single eMM11 entry ---
async def fetch_single_emm11(playwright, emm11_num, district, log=print):
    url = BASE_URL.format(emm11_num)
    browser = await playwright.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
    page = await browser.new_page()

    try:
        await page.goto(url, timeout=20000)
        await page.wait_for_selector("#lbl_destination_district", timeout=10000)
        district_text = (await page.locator("#lbl_destination_district").inner_text()).strip()
        await page.wait_for_selector("#lbl_qty_to_Transport", timeout=10000)
        qty = (await page.locator("#lbl_qty_to_Transport").inner_text()).strip()
        await page.wait_for_selector("#txt_etp_generated_on", timeout=10000)
        generated = (await page.locator("#txt_etp_generated_on").inner_text()).strip()
        await page.wait_for_selector("#txt_istp_valid_upto", timeout=10000)
        valid = (await page.locator("#txt_istp_valid_upto").inner_text()).strip()

        await page.wait_for_selector("#lbl_istp", timeout=5000)
        await page.wait_for_selector("#lbl_Origin_Transit_Pass_No", timeout=5000)

        istp = (await page.locator("#lbl_istp").inner_text()).strip()
        ostp = (await page.locator("#lbl_Origin_Transit_Pass_No").inner_text()).strip()

        if district_text.upper() == district.upper():
            entry = {
                "eMM11_num": str(emm11_num),        # Added for unique identification
                "istp": istp,
                "ostp": ostp,
                "destination_district": district_text,
                "qty": qty,
                "valid_upto": valid,
                "generated_on": generated
            }
            log(f"[{emm11_num}] ✅ Found: {entry}")
            return entry
        else:
            log(f"[{emm11_num}] ⚠️ District mismatch: {district_text}")

    except PlaywrightTimeoutError:
        log(f"[{emm11_num}] ⏱ Timeout while loading page")
    except Exception as e:
        log(f"[{emm11_num}] ❌ Error: {e}")
    finally:
        await browser.close()

    return None

# --- Fetch multiple eMM11 entries ---
async def fetch_emm11_data(start_num, end_num, district, data_callback=None, log=print):
    """
    Fetch entries from start_num to end_num for a district.
    Calls data_callback(entry) if provided for each valid entry.
    Returns list of entries if no callback.
    """
    results = []

    async with async_playwright() as playwright:
        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

        async def limited_fetch(num):
            async with semaphore:
                entry = await fetch_single_emm11(playwright, num, district, log=log)
                if entry:
                    if data_callback:
                        await data_callback(entry)
                    else:
                        results.append(entry)

        tasks = [limited_fetch(i) for i in range(start_num, end_num + 1)]
        await asyncio.gather(*tasks)

    if not data_callback:
        log(f"[LOG] Total fetched entries: {len(results)}")
        return results
    return []
