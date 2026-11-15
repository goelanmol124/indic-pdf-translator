"""End-to-end pipeline: PDF -> page images -> OCR -> HTML layout (review loop)
-> cross-page merge -> chunked translation -> layout-preserving HTML."""

from __future__ import annotations

import asyncio
import html
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .layout import chunk_layout, split_pages, stitch
from .pdf import Page, load_pages
from .providers import Provider, Usage, get_provider
from .render import build_html, render_png

log = logging.getLogger(__name__)


@dataclass
class Options:
    target: str = "en"
    source: str = "auto"
    dpi: int = 150
    max_review_rounds: int = 2
    overlap: int = 3
    chunk_tokens: int = 500
    render_for_review: bool = True


@dataclass
class Result:
    html: str
    source_layout: list[str]
    translated_layout: list[str]
    page_count: int
    usage: Usage
    timings: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def save_intermediate(self, directory: str | Path) -> Path:
        """Write intermediate stages as JSON. Contains document text: keep it private."""
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "intermediate.json"
        data = {
            "page_count": self.page_count,
            "source_layout": self.source_layout,
            "translated_layout": self.translated_layout,
            "usage": asdict(self.usage),
            "timings": self.timings,
            "warnings": self.warnings,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


async def _page_layout(provider: Provider, page: Page, opts: Options, warnings: list[str]) -> list[str]:
    try:
        text = await provider.ocr(page)
    except Exception as e:
        warnings.append(f"page {page.index + 1}: OCR failed ({e})")
        text = page.text
    try:
        layout = await provider.layout(page, text)
        if provider.supports_review:
            for _ in range(opts.max_review_rounds):
                rendered = await render_png(layout) if opts.render_for_review else None
                review = await provider.review_layout(page, layout, rendered)
                if review.passed:
                    break
                feedback = review.feedback + "\nPrevious attempt: " + json.dumps(layout, ensure_ascii=False)
                layout = await provider.layout(page, text, feedback=feedback)
    except Exception as e:
        warnings.append(f"page {page.index + 1}: layout failed, using plain OCR text ({e})")
        layout = []
    if not layout and text:
        layout = [f"<div>{html.escape(p)}</div>" for p in text.split("\n\n") if p.strip()]
    if not layout:
        warnings.append(f"page {page.index + 1}: no text found (scanned page? use an OCR-capable provider)")
    return layout


async def _merge(provider: Provider, pages: list[Page], layouts: list[list[str]], opts: Options,
                 warnings: list[str]) -> list[str]:
    splits = split_pages(layouts, opts.overlap)

    async def boundary(i: int) -> list[str]:
        tail, head = splits[i].tail, splits[i + 1].head
        if not tail and not head:
            return []
        try:
            return await provider.merge(tail, head, pages[i], pages[i + 1])
        except Exception as e:
            warnings.append(f"merge of pages {i + 1}-{i + 2} failed, kept unmerged ({e})")
            return tail + head

    merged = await asyncio.gather(*(boundary(i) for i in range(len(pages) - 1)))
    return stitch(splits, list(merged))


async def _translate(provider: Provider, layout: list[str], opts: Options, warnings: list[str]) -> list[str]:
    chunks = chunk_layout(layout, opts.chunk_tokens)

    async def one(i: int, chunk: list[str]) -> list[str]:
        try:
            return await provider.translate(chunk, opts.target, opts.source)
        except Exception as e:
            # Never silently drop content: keep the untranslated chunk and say so.
            warnings.append(f"translation of chunk {i + 1}/{len(chunks)} failed, left untranslated ({e})")
            return chunk

    parts = await asyncio.gather(*(one(i, c) for i, c in enumerate(chunks)))
    return [el for part in parts for el in part]


async def translate_pdf_async(
    pdf: bytes | str | Path,
    provider: Provider | str = "mock",
    options: Options | None = None,
) -> Result:
    """Translate a PDF (bytes or path) and return a :class:`Result` with the HTML output."""
    opts = options or Options()
    prov = get_provider(provider) if isinstance(provider, str) else provider
    warnings: list[str] = []
    timings: dict[str, float] = {}

    t = time.perf_counter()
    pages = load_pages(str(pdf) if isinstance(pdf, Path) else pdf, dpi=opts.dpi)
    timings["rasterise"] = time.perf_counter() - t

    t = time.perf_counter()
    layouts = list(await asyncio.gather(*(_page_layout(prov, p, opts, warnings) for p in pages)))
    timings["ocr_layout"] = time.perf_counter() - t

    t = time.perf_counter()
    source_layout = await _merge(prov, pages, layouts, opts, warnings) if len(pages) > 1 else (layouts[0] if layouts else [])
    timings["merge"] = time.perf_counter() - t

    t = time.perf_counter()
    translated = await _translate(prov, source_layout, opts, warnings)
    timings["translate"] = time.perf_counter() - t

    for w in warnings:
        log.warning(w)
    return Result(
        html=build_html(translated, lang=opts.target),
        source_layout=source_layout,
        translated_layout=translated,
        page_count=len(pages),
        usage=prov.usage,
        timings=timings,
        warnings=warnings,
    )


def translate_pdf(pdf: bytes | str | Path, provider: Provider | str = "mock", options: Options | None = None) -> Result:
    """Synchronous wrapper around :func:`translate_pdf_async`."""
    return asyncio.run(translate_pdf_async(pdf, provider, options))
