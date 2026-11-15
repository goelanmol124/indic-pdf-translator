"""Generate a small synthetic two-page English PDF for demos and tests.

The content is invented: no real case, court, or person.

    python examples/make_sample_pdf.py examples/sample.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

W, H = pymupdf.paper_size("a4")
MARGIN = 72


def _centered(page: pymupdf.Page, y: float, text: str, size: float, font: str = "hebo") -> float:
    width = pymupdf.get_text_length(text, fontname=font, fontsize=size)
    page.insert_text(((W - width) / 2, y), text, fontname=font, fontsize=size)
    return y + size * 1.8


def _para(page: pymupdf.Page, y: float, text: str, height: float = 60) -> float:
    rect = pymupdf.Rect(MARGIN, y, W - MARGIN, y + height)
    page.insert_textbox(rect, text, fontname="helv", fontsize=11, align=pymupdf.TEXT_ALIGN_JUSTIFY)
    return y + height + 8


def _page_number(page: pymupdf.Page, n: int) -> None:
    _centered(page, H - 40, f"Page {n}", 9, font="helv")


def make_sample(path: str | Path) -> Path:
    path = Path(path)
    doc = pymupdf.open()

    p1 = doc.new_page(width=W, height=H)
    y = _centered(p1, 90, "IN THE DISTRICT COURT OF SAMPLE CITY", 15)
    y = _centered(p1, y, "Case No. 000/2025 (synthetic example)", 11, font="helv")
    y = _centered(p1, y + 6, "ORDER", 13)
    y = _para(p1, y + 10, "This is a synthetic sample document for translation. The petitioner filed an "
                          "application for a copy of the order. The respondent was given notice of the hearing.")
    y = _para(p1, y, "The court will hear the case on the next date. This paragraph continues across the page "
                     "break and is joined by the merge step of the", height=50)
    _page_number(p1, 1)

    p2 = doc.new_page(width=W, height=H)
    y = _para(p2, 80, "translation pipeline before it is translated.", height=30)
    y = _para(p2, y, "The table below lists the fee filed with the application:", height=30)
    rows = [("Item", "Description", "Amount"), ("1", "Application fee", "100 rupees"),
            ("2", "Copy fee", "50 rupees"), ("", "Total", "150 rupees")]
    col_x = [MARGIN, MARGIN + 60, MARGIN + 300, W - MARGIN]
    for r, row in enumerate(rows):
        top = y + r * 22
        for c, cell in enumerate(row):
            rect = pymupdf.Rect(col_x[c], top, col_x[c + 1], top + 22)
            p2.draw_rect(rect, width=0.6)
            p2.insert_textbox(rect + (4, 5, -4, 0), cell, fontname="hebo" if r == 0 else "helv", fontsize=10)
    y += len(rows) * 22 + 40
    p2.insert_text((W - MARGIN - 120, y), "Signature of the Judge", fontname="helv", fontsize=11)
    _page_number(p2, 2)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    doc.close()
    return path


if __name__ == "__main__":
    out = make_sample(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name("sample.pdf"))
    print(f"wrote {out}")
