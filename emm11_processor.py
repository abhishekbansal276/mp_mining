from playwright.async_api import Page

async def process_emm11(page: Page, tp_pairs, log_callback=print):
    """
    Processes a list of TP pairs on the website and identifies unused TP numbers.

    Args:
        page (Page): Playwright page instance already logged in.
        tp_pairs (List[Tuple[str, str]]): List of (istp, ostp) tuples.
        log_callback (Callable): Function to log messages.

    Returns:
        List[Tuple[str, str]]: List of unused TP pairs.
    """
    unused_tp_list = []

    try:
        # Navigate to the target page
        submenu = page.locator("//a[normalize-space()='Apply for eFormC Quantity by Transit Pass Number']")

        if await submenu.is_visible():
            # Submenu already open -> direct click
            await submenu.click()
            await page.wait_for_timeout(1000)
        else:
            # Open master menu first
            master_menu = page.locator("//a[normalize-space()='Master Entries']")
            await master_menu.wait_for(state="visible", timeout=6000)
            await master_menu.click()
            await page.wait_for_timeout(1000)

            # Now click submenu
            await submenu.wait_for(state="visible", timeout=6000)
            await submenu.click()
            await page.wait_for_timeout(1000)

        # Select licensee and mode
        await page.select_option("#ContentPlaceHolder1_ddl_LicenseeID", index=1)
        await page.click("#ContentPlaceHolder1_RbtWise_1")
        await page.wait_for_timeout(1500)

        # Process each TP pair
        for istp, ostp in tp_pairs:
            if not istp or not ostp:
                continue

            try:
                await page.fill("input[name='ctl00$ContentPlaceHolder1$txtOSTP']", str(ostp))
                await page.fill("input[name='ctl00$ContentPlaceHolder1$txtISTP']", str(istp))
                await page.click("input[name='ctl00$ContentPlaceHolder1$btnProceed1']")
                await page.wait_for_load_state("networkidle")

                # Check for error indicating unused TP
                error_locator = page.locator("//span[@id='ContentPlaceHolder1_ErrorLbl']")
                try:
                    await error_locator.wait_for(state="visible", timeout=5000)
                    error_text = (await error_locator.inner_text()).replace('\xa0', ' ').strip()
                except Exception:
                    error_text = ""

                if "other destination district istp not allowed" in error_text.lower():
                    unused_tp_list.append((istp, ostp))
                    log_callback(f"✅ Unused: {istp} / {ostp}")

            except Exception as e:
                log_callback(f"⚠️ TP pair ({istp}, {ostp}) failed: {e}")

        # log_callback(f"📄 Total unused TP pairs: {len(unused_tp_list)}")
        return unused_tp_list

    except Exception as e:
        log_callback(f"🔥 Fatal error in process_emm11: {e}")
        return []
