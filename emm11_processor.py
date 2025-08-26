from playwright.async_api import Page

async def process_emm11(page: Page, tp_pairs, log_callback=print):
    """
    Processes a list of TP pairs on the website and identifies unused TP numbers.
    Detailed logging added for debugging every input/output.

    Args:
        page (Page): Playwright page instance already logged in.
        tp_pairs (List[Tuple[str, str]]): List of (istp, ostp) tuples.
        log_callback (Callable): Function to log messages.

    Returns:
        List[Tuple[str, str]]: List of unused TP pairs.
    """
    unused_tp_list = []

    # log_callback(f"🔹 Received TP pairs: {tp_pairs}")

    try:
        # --- Click Master Entries menu ---
        master_menu = page.locator("//a[normalize-space()='Master Entries']")
        await master_menu.wait_for(state="visible", timeout=6000)
        await master_menu.click()
        log_callback("ℹ️ Clicked Master Entries")
        await page.wait_for_timeout(500)

        # --- Click submenu ---
        submenu = page.locator("//a[contains(normalize-space(.), 'Apply for eFormC Quantity by Transit Pass Number')]")
        await submenu.wait_for(state="visible", timeout=6000)
        await submenu.click()
        # log_callback("ℹ️ Clicked submenu: Apply for eFormC Quantity by Transit Pass Number")
        await page.wait_for_load_state("networkidle")

        # --- Select licensee and mode ---
        await page.select_option("#ContentPlaceHolder1_ddl_LicenseeID", index=1)
        # log_callback("ℹ️ Licensee selected")
        await page.click("#ContentPlaceHolder1_RbtWise_1")
        # log_callback("ℹ️ Mode selected")
        await page.wait_for_timeout(1500)

        # --- Process each TP pair ---
        for idx, pair in enumerate(tp_pairs, start=1):
            # log_callback(f"🔹 Processing TP pair #{idx}: {pair}")
            
            if not pair or len(pair) != 2:
                log_callback(f"⚠️ Skipping invalid pair: {pair}")
                continue

            istp, ostp = pair
            if not istp or not ostp:
                log_callback(f"⚠️ Skipping empty ISTP/OSTP: {pair}")
                continue

            try:
                # log_callback(f"⏳ Filling fields for ISTP='{istp}', OSTP='{ostp}'")
                await page.fill("input[name='ctl00$ContentPlaceHolder1$txtOSTP']", str(ostp))
                await page.fill("input[name='ctl00$ContentPlaceHolder1$txtISTP']", str(istp))
                await page.click("input[name='ctl00$ContentPlaceHolder1$btnProceed1']")
                # log_callback(f"ℹ️ Submitted TP pair: {istp} / {ostp}")

                # --- Wait for page reload/network idle ---
                await page.wait_for_load_state("networkidle")
                # log_callback("⏳ Page reload complete")

                # --- Re-locate error label after reload ---
                error_locator = page.locator("//span[@id='ContentPlaceHolder1_ErrorLbl']")
                try:
                    await error_locator.wait_for(state="visible", timeout=5000)
                    error_html = await error_locator.inner_html()
                    error_text = (await error_locator.inner_text()).replace('\xa0', ' ').strip()
                    # log_callback(f"🔍 ERROR HTML: {error_html}")
                    # log_callback(f"🔍 ERROR TEXT: '{error_text}'")
                except Exception:
                    error_text = ""
                    log_callback("ℹ️ Error label not visible")

                # --- Detect unused TP based on error text ---
                if "other destination district istp not allowed" in error_text.lower():
                    unused_tp_list.append((istp, ostp))
                    log_callback(f"✅ Unused TP: {istp} / {ostp}")
                # else:
                #     log_callback(f"⚠️ Used or invalid TP: {istp} / {ostp} -> '{error_text}'")

            except Exception as e:
                log_callback(f"⚠️ TP pair ({istp}, {ostp}) failed: {e}")

        log_callback(f"📄 Total unused TP pairs: {len(unused_tp_list)}")
        log_callback(f"🔹 Returning unused TP list: {unused_tp_list}")
        return unused_tp_list

    except Exception as e:
        log_callback(f"🔥 Fatal error in process_emm11: {e}")
        return []
