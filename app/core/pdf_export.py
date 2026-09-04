from pathlib import Path
from playwright.sync_api import sync_playwright


def export_pdf(html_content, output_path):
    """
    Converts rendered HTML into PDF.

    Purpose:
    - final portable resume artifact
    - browser-quality rendering
    """

    with sync_playwright() as p:

        browser = p.chromium.launch()

        page = browser.new_page()

        page.set_content(
            html_content,
            # base_url=Path(output_path).parent.resolve().as_uri(),
            wait_until="networkidle"
        )

        page.pdf(
            path=output_path,
            format="A4"
        )
        
        browser.close()
        
