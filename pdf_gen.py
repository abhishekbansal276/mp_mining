import os
import shutil
import logging
import asyncio
from playwright.async_api import async_playwright
from PIL import Image

logging.basicConfig(
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def pdf_gen(tp_num_list, log_callback=None, send_pdf_callback=None):
    """
    Generate a single PDF containing all TP pages using full-page screenshots.
    Each TP page is captured as PNG, then merged into a single PDF.
    """

    if not tp_num_list:
        msg = "ℹ️ No TP numbers provided."
        logger.info(msg)
        if log_callback:
            log_callback(msg)
        return None

    # Create folders
    os.makedirs("pdf", exist_ok=True)
    temp_folder = "pdf/temp"
    os.makedirs(temp_folder, exist_ok=True)
    screenshot_paths = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, slow_mo=50)
        context = await browser.new_context(viewport={"width": 1280, "height": 1024})

        for tp_num in tp_num_list:
            tp_num = str(tp_num)
            try:
                page = await context.new_page()
                url = f"https://upmines.upsdc.gov.in//Transporter/PrintTransporterFormVehicleCheckValidOrNot.aspx?eId={tp_num}"
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state("networkidle")

                # Optional: wait for key element
                try:
                    await page.wait_for_selector("#lbl_istp", timeout=15000)
                except:
                    if log_callback:
                        log_callback(f"⚠️ Key element not found for TP {tp_num}, screenshot may be incomplete.")

                # Scroll to bottom
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                await asyncio.sleep(1)

                # Full-page screenshot
                screenshot_path = os.path.join(temp_folder, f"{tp_num}.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                screenshot_paths.append(screenshot_path)

                msg = f"✅ Screenshot captured for TP: {tp_num}"
                logger.info(msg)
                if log_callback:
                    log_callback(msg)

                await page.close()

            except Exception as e:
                msg = f"❌ Failed TP {tp_num}: {e}"
                logger.error(msg)
                if log_callback:
                    log_callback(msg)

        await browser.close()

    if not screenshot_paths:
        if log_callback:
            log_callback("⚠️ No screenshots captured, PDF cannot be generated.")
        return None

    # Merge screenshots into single PDF
    images = []
    final_pdf_path = None
    try:
        for path in screenshot_paths:
            with Image.open(path) as img:
                images.append(img.convert("RGB"))

        if images:
            final_pdf_path = "pdf/All_TP.pdf"
            images[0].save(final_pdf_path, save_all=True, append_images=images[1:])
            msg = f"✅ All TP pages merged into single PDF: {final_pdf_path}"
            logger.info(msg)
            if log_callback:
                log_callback(msg)

    finally:
        # Cleanup temporary folder safely
        for path in screenshot_paths:
            try:
                os.remove(path)
            except Exception as e:
                logger.warning(f"⚠️ Failed to delete temp file {path}: {e}")
        if os.path.exists(temp_folder):
            try:
                os.rmdir(temp_folder)
            except Exception as e:
                logger.warning(f"⚠️ Failed to remove temp folder: {e}")

    # Optionally send merged PDF
    if send_pdf_callback and final_pdf_path:
        if asyncio.iscoroutinefunction(send_pdf_callback):
            await send_pdf_callback(final_pdf_path)
        else:
            send_pdf_callback(final_pdf_path)

    return final_pdf_path
