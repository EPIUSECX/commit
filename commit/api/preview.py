import asyncio
import io

import frappe
from pyppeteer import launch

from commit.api.convert_to_webp import convert_to_webp
from commit.security import validate_public_https_url


async def capture_screenshot(url, width=1366, height=800, delay=3):
    validate_public_https_url(url)
    browser = await launch(
        headless=True, handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False
    )
    try:
        page = await browser.newPage()
        await page.setViewport({"width": width, "height": height})
        await page.goto(url, {"waitUntil": "load", "timeout": 30000})
        await asyncio.sleep(delay)
        return await page.screenshot({"fullPage": False, "encoding": "binary"})
    finally:
        await browser.close()


def save_preview_screenshot(url, doctype, docname, field):
    screenshot_bytes = asyncio.run(capture_screenshot(url))

    # ✅ Correct way: Wrap bytes in BytesIO
    screenshot_io = io.BytesIO(screenshot_bytes)

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": docname + "_" + "preview.png",
            "attached_to_doctype": doctype,
            "attached_to_name": docname,
            "attached_to_field": field,
            "is_private": 1,
            "content": screenshot_io.getvalue(),
        }
    )
    file_doc.save()

    # Convert to WebP
    file_url = convert_to_webp(file_doc.file_url, file_doc)
    # Update the document with the preview file URL
    doc = frappe.get_cached_doc(doctype, docname)
    doc.set(field, file_url)
    doc.save()

    frappe.db.commit()
