"""Offline provider: no network, no API key.

* OCR      -> the PDF's embedded text layer (works for born-digital PDFs only)
* layout   -> one <div> per text block (alignment / bold / size heuristics) and
              <table> for ruled tables detected by PyMuPDF; page numbers dropped
* merge    -> joins a paragraph split across a page break, drops bare page numbers
* translate-> deterministic pseudo-translation: a small English->Hindi glossary,
              or a ``[xx]`` tag for other targets. Good for demos and tests, not
              for real translation.
"""

from __future__ import annotations

import html
import re

from ..htmltext import map_text, strip_tags
from ..pdf import Page, TextBlock
from .base import Provider

GLOSSARY_EN_HI = {
    "the": "", "a": "", "an": "",
    "court": "न्यायालय", "high": "उच्च", "district": "ज़िला", "judge": "न्यायाधीश",
    "order": "आदेश", "case": "मामला", "petition": "याचिका", "petitioner": "याचिकाकर्ता",
    "respondent": "प्रतिवादी", "versus": "बनाम", "vs": "बनाम", "date": "दिनांक",
    "hearing": "सुनवाई", "notice": "सूचना", "application": "आवेदन", "document": "दस्तावेज़",
    "page": "पृष्ठ", "translation": "अनुवाद", "sample": "नमूना", "this": "यह", "is": "है",
    "and": "और", "of": "का", "in": "में", "to": "को", "for": "के लिए", "with": "के साथ",
    "on": "पर", "by": "द्वारा", "was": "था", "be": "हो", "will": "होगा", "are": "हैं",
    "text": "पाठ", "table": "तालिका", "name": "नाम", "amount": "राशि", "rupees": "रुपये",
    "next": "अगली", "fee": "शुल्क", "filed": "दायर", "copy": "प्रति", "signature": "हस्ताक्षर",
    "paragraph": "अनुच्छेद", "continues": "जारी", "across": "पार", "break": "विराम",
    "item": "मद", "description": "विवरण", "total": "कुल", "synthetic": "कृत्रिम", "example": "उदाहरण",
}
_WORD_RE = re.compile(r"[A-Za-z]+")
_PAGE_NO_RE = re.compile(r"^\s*(page\s*)?\d+\s*(of\s*\d+)?\s*$", re.I)


def pseudo_translate(text: str, target: str) -> str:
    if target == "hi":
        def sub(m: re.Match) -> str:
            w = m.group(0)
            return GLOSSARY_EN_HI.get(w.lower(), w)
        out = _WORD_RE.sub(sub, text)
        return re.sub(r"\s{2,}", " ", out).strip()
    return f"[{target}] {text}"


class MockProvider(Provider):
    name = "mock"

    async def ocr(self, page: Page) -> str:
        self.usage.requests += 1
        return page.text

    async def layout(self, page: Page, ocr_text: str, feedback: str | None = None) -> list[str]:
        self.usage.requests += 1
        if page.blocks:
            return [_block_html(b, page.width) for b in page.blocks if not _PAGE_NO_RE.match(b.text)]
        return [f"<div>{html.escape(p)}</div>" for p in ocr_text.split("\n\n") if p.strip()]

    async def merge(self, prev_tail: list[str], next_head: list[str], prev: Page, nxt: Page) -> list[str]:
        self.usage.requests += 1
        tail = [e for e in prev_tail if not _PAGE_NO_RE.match(strip_tags(e))]
        head = [e for e in next_head if not _PAGE_NO_RE.match(strip_tags(e))]
        if tail and head and _is_paragraph(tail[-1]) and _is_paragraph(head[0]):
            last = strip_tags(tail[-1])
            if last and last[-1] not in ".:;!?।":
                joined = tail[-1][: tail[-1].rfind("</div>")] + " " + _inner(head[0]) + "</div>"
                return tail[:-1] + [joined] + head[1:]
        return tail + head

    async def translate(self, chunk: list[str], target: str, source: str) -> list[str]:
        self.usage.requests += 1
        return [map_text(el, lambda t: pseudo_translate(t, target)) for el in chunk]


def _table_html(rows: list[list[str]]) -> str:
    esc = lambda c: html.escape(c, quote=False)  # noqa: E731
    head = "".join(f"<th>{esc(c)}</th>" for c in rows[0])
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _block_html(b: TextBlock, page_width: float) -> str:
    if b.rows:
        return _table_html(b.rows)
    x0, _, x1, _ = b.bbox
    centre = (x0 + x1) / 2
    styles = []
    if abs(centre - page_width / 2) < page_width * 0.05 and (x1 - x0) < page_width * 0.7:
        styles.append("text-align:center")
    if b.bold:
        styles.append("font-weight:bold")
    if b.size >= 14:
        styles.append(f"font-size:{round(b.size)}pt")
    style = f' style="{";".join(styles)}"' if styles else ""
    return f"<div{style}>{html.escape(b.text, quote=False)}</div>"


def _is_paragraph(el: str) -> bool:
    return el.lstrip().startswith("<div") and "<table" not in el


def _inner(el: str) -> str:
    start = el.find(">") + 1
    end = el.rfind("</div>")
    return el[start:end] if end > start else el[start:]
