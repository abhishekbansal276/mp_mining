import os
import inspect
import base64
import logging
from io import BytesIO
import qrcode
import re

from playwright.async_api import async_playwright
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2 import PdfMerger

# ---------- Logging Setup ----------
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
# -----------------------------------

def draw_data(c, data):
    c.setFont("Helvetica", 8)

    def draw_wrapped_text(c, x, y, text, max_chars=28, line_spacing=8):
        """
        Ek line me max 33 characters (spaces included), word split na ho.
        Font chota rakhe.
        """
        c.setFont("Helvetica", 8)
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            # Agar current line + word + space exceed karta hai max_chars, toh nayi line
            if len(current_line) + len(word) + (1 if current_line else 0) > max_chars:
                lines.append(current_line)
                current_line = word
            else:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
        if current_line:
            lines.append(current_line)

        for i, line in enumerate(lines):
            c.drawString(x, y - i * line_spacing, line)
            
    def draw_wrapped_text_name(c, x, y, text, max_chars=22, line_spacing=10):
        """
        Ek line me max 15 characters (spaces included), word split na ho.
        Font chota rakhe.
        """
        c.setFont("Helvetica", 8)  # Chota font
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            # Agar current line + word + space exceed karta hai max_chars, toh nayi line
            if len(current_line) + len(word) + (1 if current_line else 0) > max_chars:
                lines.append(current_line)
                current_line = word
            else:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
        if current_line:
            lines.append(current_line)

        for i, line in enumerate(lines):
            c.drawString(x, y - i * line_spacing, line)

    # Top section
    c.drawString(180, 620, data.get("istp_no", ""))
    draw_wrapped_text_name(c, 470, 624, data.get("transporter_name", ""), max_chars=15) 
    c.drawString(180, 595, data.get("transporter_id", ""))   
    c.drawString(470, 595, data.get("transporter_mobile", ""))
    draw_wrapped_text(c, 180, 573.5, data.get("transporter_address", ""))
    c.drawString(470, 568, data.get("qty_transported_cubic_meter", ""))
    c.drawString(180, 540, data.get("mineral_name", ""))
    c.drawString(470, 540, data.get("destination_district", ""))
    c.drawString(180, 510, data.get("distance_km", ""))
    draw_wrapped_text_name(c, 470, 514, data.get("travel_duration", ""))

    c.drawString(180, 480, data.get("transit_pass_generated_on", ""))
    c.drawString(470, 480, data.get("transit_pass_valid_upto", ""))

    draw_wrapped_text(c, 180, 460, data.get("loading_from_district", ""))
    c.drawString(470, 445, data.get("loading_from_state", ""))
    c.drawString(180, 405, data.get("origin_transit_pass_no", ""))
    c.drawString(470, 405, data.get("origin_transit_pass_date", ""))

    # c.drawString(300, 500.5, clean_emM11)
    # c.drawString(372, 717.5, data.get("transporter_id", ""))

    # c.drawString(260, 707, data.get("transporter_mobile", ""))
    # draw_wrapped_text(435, 708, data.get("transporter_address", ""))

    # # Middle section
    # c.drawString(100, 690, data.get("loading_from_district", ""))
    # c.drawString(260, 690, data.get("loading_from_state", ""))
    # c.drawString(405, 682, data.get("qty_transported_cubic_meter", ""))

    # draw_wrapped_text(100, 672.5, data.get("mineral_name", ""))
    # c.drawString(265, 672.5, data.get("loading_from_district", ""))
    # c.drawString(435, 672.5, data.get("destination_address", ""))

    # c.drawString(60, 641, data.get("distance_km", ""))
    # c.drawString(250, 648, data.get("transit_pass_generated_on", ""))
    # c.drawString(435, 648, data.get("transit_pass_valid_upto", ""))

    # c.drawString(110, 625, data.get("travel_duration", ""))
    # c.drawString(260, 630, data.get("destination_district", ""))
    # # c.drawString(435, 630, data.get("destination_state", ""))

    # c.drawString(160, 601, data.get("form_valid_upto", ""))
    # # c.drawString(330, 613, data.get(""))  # No field mapped

    c.drawString(180, 320, data.get("vehicle_number", ""))
    c.drawString(395, 295, data.get("driver_mobile", ""))
    c.drawString(395, 320, data.get("vehicle_type", ""))
    c.drawString(180, 290, data.get("driver_dl_number", ""))
    c.drawString(180, 295, data.get("driver_name", ""))

    if "qr_code_base64" in data:
        try:
            qr_data = base64.b64decode(data["qr_code_base64"].split(",")[1])
            qr_image = ImageReader(BytesIO(qr_data))

            qr_size = 77
            PAGE_WIDTH, PAGE_HEIGHT = A4
            margin_right = 60
            margin_top = 45

            x_qr = PAGE_WIDTH - qr_size - margin_right
            y_qr = PAGE_HEIGHT - qr_size - margin_top

            # Directly draw QR code, no background, no padding
            c.drawImage(
                qr_image,
                x_qr,
                y_qr,
                width=qr_size,
                height=qr_size,
                preserveAspectRatio=True,
                mask='auto'
            )

        except Exception as e:
            logger.warning(f"⚠️ QR drawing failed: {e}")

def generate_pdf(data, template_path, output_path):
    overlay_stream = BytesIO()
    c = canvas.Canvas(overlay_stream, pagesize=A4)
    draw_data(c, data)
    c.save()
    overlay_stream.seek(0)

    bg_reader = PdfReader(template_path)
    ov_reader = PdfReader(overlay_stream)
    writer = PdfWriter()

    page = bg_reader.pages[0]
    page.merge_page(ov_reader.pages[0])
    writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

async def create_qr_image_base64(tp_num, url):
    logger.info(f"🧾 Generating QR for TP: {tp_num}")
    if not url or not isinstance(url, str):
        logger.error(f"❌ Invalid URL for TP {tp_num}: {url!r}")
        raise ValueError(f"Invalid URL passed to QR generator for TP {tp_num}")

    try:
        logger.debug(f"🔗 QR URL for TP {tp_num}: {url}")
        img = qrcode.make(url)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()

        if not img_bytes:
            logger.error(f"❌ QR image generation failed for TP {tp_num}: no bytes returned")
            raise ValueError(f"QR image generation failed for TP {tp_num}")

        base64_str = base64.b64encode(img_bytes).decode()
        logger.info(f"✅ QR generated successfully for TP {tp_num}")
        return f"data:image/png;base64,{base64_str}"

    except Exception as e:
        logger.exception(f"❌ Exception while generating QR for TP {tp_num}: {e}")
        raise

async def pdf_gen(tp_num_list, template_path="mp_format.pdf", log_callback=None, send_pdf_callback=None):
    if not tp_num_list:
        logger.info("ℹ️ No TP numbers provided.")
        return None

    os.makedirs("pdf", exist_ok=True)
    all_pdfs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        for tp_num in tp_num_list:
            tp_num = str(tp_num)
            logger.info(f"📦 Processing TP: {tp_num}")
            try:
                page = await context.new_page()
                url = f"https://upmines.upsdc.gov.in//Transporter/PrintTransporterFormVehicleCheckValidOrNot.aspx?eId={tp_num}"
                await page.goto(url, timeout=20000)

                lbl_etpNo = await page.locator("#lbl_istp").inner_text()
                if tp_num not in lbl_etpNo:
                    raise ValueError(f"Mismatch: expected {tp_num}, got {lbl_etpNo}")

                data = {    
                    "istp_no": await page.locator('#lbl_istp').inner_text(),
                    "transporter_name": await page.locator('#lbl_name_of_Transporter').inner_text(),
                    "transporter_id": await page.locator("#lbl_TransporterId").inner_text(),
                    "transporter_mobile": await page.locator("#lbl_mobile_no").inner_text(),
                    "transporter_address": await page.locator('#lbl_TransporterDetails').inner_text(),
                    "qty_transported_cubic_meter": await page.locator("#lbl_qty_to_Transport").inner_text(),
                    "mineral_name": await page.locator("#lbl_type_of_mining_mineral").inner_text(),
                    "destination_district": await page.locator("#lbl_destination_district").inner_text(),
                    "distance_km": await page.locator('#lbl_distrance').inner_text(),
                    "travel_duration": await page.locator("#lbl_travel_duration").inner_text(),
                    "transit_pass_generated_on": await page.locator("#txt_etp_generated_on").inner_text(),
                    "transit_pass_valid_upto": await page.locator("#txt_istp_valid_upto").inner_text(),
                    "loading_from_district": await page.locator("#lbl_loadingfrom").inner_text(),
                    "loading_from_state": await page.locator("#lbl_loadingfromState").inner_text(),
                    "origin_transit_pass_no": await page.locator("#lbl_Origin_Transit_Pass_No").inner_text(),
                    "origin_transit_pass_date": await page.locator("#lbl_Origin_Transit_Pass_Generation_Date").inner_text(),
                    "destination_address": await page.locator("#lbl_destination_address").inner_text(),
                    "vehicle_number": await page.locator("#lbl_registraton_number_of_vehicle").inner_text(),
                    "vehicle_type": await page.locator("#lbl_vehicleType").inner_text(),
                    "driver_name": await page.locator("#lbl_name_of_driver").inner_text(),
                    "driver_mobile": await page.locator("#lbl_mobile_number_of_driver").inner_text(),
                    "driver_dl_number": await page.locator("#lbl_dl_number").inner_text(),
                    "form_valid_upto": await page.locator("#lbl_formValidUpTo").inner_text()
                }

                data["qr_code_base64"] = await create_qr_image_base64(tp_num, url)

                output_path = f"pdf/{tp_num}.pdf"
                generate_pdf(data, template_path, output_path)
                all_pdfs.append(output_path)

                logger.info(f"✅ Successfully processed TP: {tp_num}")

                if send_pdf_callback:
                    if inspect.iscoroutinefunction(send_pdf_callback):
                        await send_pdf_callback(output_path, tp_num)
                    else:
                        send_pdf_callback(output_path, tp_num)

                await page.close()

            except Exception as e:
                logger.error(f"❌ Failed TP {tp_num}: {e}")

        await browser.close()

    # 🔗 Merge all PDFs
    if all_pdfs:
        merged_path = "pdf/merged_tp.pdf"
        merger = PdfMerger()
        for pdf in all_pdfs:
            merger.append(pdf)
        merger.write(merged_path)
        merger.close()
        logger.info(f"📑 Merged PDF created: {merged_path}")
        return merged_path

    return None