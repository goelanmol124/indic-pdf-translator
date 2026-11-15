"""Render a list of HTML elements into a print-ready document.

``build_html`` is dependency-free. ``render_png`` / ``html_to_pdf`` need the
optional ``render`` extra (Playwright + Chromium).
"""

from __future__ import annotations

import io
import logging
import re

from PIL import Image

from .languages import SCRIPTS, detect_script

log = logging.getLogger(__name__)

# Lines that open Indian court documents ("IN THE HIGH COURT OF ...", "BEFORE ...", "BETWEEN ...").
_HEADING_RE = re.compile(r"^\s*(?:<[^>]+>\s*)*(IN THE|BEFORE|BETWEEN)\b")

_CSS = """
@page { size: A4; margin: 2cm 2.5cm; }
body { font-family: 'Times New Roman', 'Noto Serif', serif; font-size: 14pt; line-height: 1.5;
       color: #000; background: #fff; margin: 20px; text-align: justify; }
.document { margin: 0 auto; max-width: 48em; }
div, p { margin-bottom: 1em; page-break-inside: avoid; overflow-wrap: break-word; }
.table-container { width: 100%; overflow-x: auto; margin: 1.5em 0; page-break-inside: avoid; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: inherit; }
table, th, td { border: 1px solid #000; padding: 6px 8px; vertical-align: middle; text-align: center; }
th { background: #f5f5f5; font-weight: bold; }
.heading { text-align: center; font-weight: bold; margin: 1.5em 0; text-transform: uppercase; }
.doubtful, .red-text, span[style*="color:red"], span[style*="color: red"] { color: #c00 !important; }
{script_css}
"""


def _script_css() -> str:
    return "\n".join(
        f".{cls} {{ font-family: '{font}', sans-serif; line-height: 1.75; }}" for _, _, cls, font in SCRIPTS
    )


def _fonts_link() -> str:
    fams = "&".join("family=" + font.replace(" ", "+") for _, _, _, font in SCRIPTS)
    return f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?{fams}&display=swap">'


def _decorate(item: str) -> str:
    if "<table" in item:
        item = f'<div class="table-container">{item}</div>'
    if _HEADING_RE.match(item):
        item = f'<div class="heading">{item}</div>'
    script = detect_script(item)
    if script and f'class="{script}"' not in item:
        item = f'<div class="{script}">{item}</div>'
    return item


def build_html(elements: list[str], lang: str = "en", title: str = "Translated document") -> str:
    """Wrap HTML elements in a standalone, printable HTML document."""
    body = "\n".join(_decorate(e) for e in elements)
    css = _CSS.replace("{script_css}", _script_css())
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{lang}">\n<head>\n<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{title}</title>\n{_fonts_link()}\n<style>{css}</style>\n</head>\n"
        f'<body>\n<div class="document">\n{body}\n</div>\n</body>\n</html>\n'
    )


def playwright_available() -> bool:
    try:
        import playwright.async_api  # noqa: F401
    except ImportError:
        return False
    return True


async def render_png(elements: list[str], width: int = 800) -> Image.Image | None:
    """Screenshot the rendered layout (used by the layout review loop). None if unavailable."""
    if not playwright_available():
        return None
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": width, "height": 1200})
            await page.set_content(build_html(elements), wait_until="load")
            png = await page.screenshot(full_page=True, type="png")
            await browser.close()
    except Exception as e:  # browser not installed, sandbox issues, ...
        log.warning("Rendering with Playwright failed: %s", e)
        return None
    img = Image.open(io.BytesIO(png))
    # Cap very tall screenshots so they stay a sensible size for a vision model.
    return img.crop((0, 0, img.width, min(img.height, width * 10)))


async def html_to_pdf(html_doc: str) -> bytes:
    """Print an HTML document to PDF with headless Chromium."""
    if not playwright_available():
        raise RuntimeError("PDF export needs the 'render' extra: pip install 'indic-pdf-translator[render]' "
                           "&& playwright install chromium")
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html_doc, wait_until="load")
        pdf = await page.pdf(format="A4", print_background=True)
        await browser.close()
    return pdf
