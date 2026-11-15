"""PDF loading: rasterise pages and capture any embedded text layer."""

from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf
from PIL import Image


@dataclass
class TextBlock:
    """A block from the PDF text layer (only present for born-digital PDFs)."""

    text: str
    bbox: tuple[float, float, float, float]
    size: float = 11.0
    bold: bool = False
    rows: list[list[str]] | None = None  # set when the block is a detected table


@dataclass
class Page:
    index: int
    image: Image.Image
    width: float
    height: float
    text: str = ""
    blocks: list[TextBlock] = field(default_factory=list)


def load_pages(pdf: bytes | str, dpi: int = 150) -> list[Page]:
    """Rasterise each page of ``pdf`` (bytes or a path) at ``dpi``."""
    doc = pymupdf.open(stream=pdf, filetype="pdf") if isinstance(pdf, (bytes, bytearray)) else pymupdf.open(pdf)
    pages: list[Page] = []
    try:
        for i, p in enumerate(doc):
            pix = p.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            pages.append(
                Page(
                    index=i,
                    image=img,
                    width=p.rect.width,
                    height=p.rect.height,
                    text=p.get_text().strip(),
                    blocks=_blocks(p),
                )
            )
    finally:
        doc.close()
    return pages


def _tables(page: pymupdf.Page) -> list[TextBlock]:
    try:
        found = page.find_tables()
    except Exception:  # table detection is best-effort
        return []
    out = []
    for t in found.tables:
        # Read each cell from the text layer directly: Table.extract() can drop spaces.
        rows = [
            [" ".join(page.get_textbox(pymupdf.Rect(c)).split()) if c else "" for c in row.cells]
            for row in t.rows
        ]
        if rows:
            text = " ".join(c for row in rows for c in row if c)
            out.append(TextBlock(text=text, bbox=tuple(t.bbox), rows=rows))
    return out


def _inside(inner: tuple, outer: tuple, tol: float = 2.0) -> bool:
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol
            and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def _blocks(page: pymupdf.Page) -> list[TextBlock]:
    tables = _tables(page)
    out: list[TextBlock] = list(tables)
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        if any(_inside(tuple(b["bbox"]), t.bbox) for t in tables):
            continue
        lines, sizes, bold = [], [], True
        for line in b["lines"]:
            spans = line["spans"]
            txt = "".join(s["text"] for s in spans).strip()
            if txt:
                lines.append(txt)
            for s in spans:
                if s["text"].strip():
                    sizes.append(s["size"])
                    bold = bold and bool(s["flags"] & 16)
        if lines:
            out.append(
                TextBlock(
                    text=" ".join(lines),
                    bbox=tuple(b["bbox"]),
                    size=max(sizes) if sizes else 11.0,
                    bold=bold and bool(sizes),
                )
            )
    out.sort(key=lambda b: (round(b.bbox[1]), b.bbox[0]))
    return out
