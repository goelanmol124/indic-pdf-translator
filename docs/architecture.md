# Architecture notes

## Data flow

1. `pdf.load_pages` rasterises every page (`Page.image`). For born-digital PDFs it also
   records the text layer (`Page.text`) and positioned blocks/tables (`Page.blocks`).
2. `pipeline._page_layout` runs per page, concurrently:
   `provider.ocr` → `provider.layout` → (if `provider.supports_review`) up to N rounds of
   `render.render_png` → `provider.review_layout` → `provider.layout(feedback=...)`.
   If layout fails, the OCR text is wrapped in `<div>`s so no page is lost.
3. `layout.split_pages` cuts each page layout into `head | body | tail` (first page has no
   head, last page no tail, and `head + body + tail == layout`). Each `tail[i] + head[i+1]` pair is
   sent to `provider.merge`; `layout.stitch` joins `body0, merged0, body1, merged1, ...`.
4. `layout.chunk_layout` groups elements into ~500-token chunks; `provider.translate` runs on
   each chunk concurrently. Failed chunks are kept untranslated and reported in `Result.warnings`.
5. `render.build_html` wraps the translated elements in a print-ready HTML document;
   `render.html_to_pdf` optionally prints it with Chromium.

## Changes from the original prototype (`TranslationProdv1.0`)

- Installable package (`src/` layout, `pyproject.toml`, `indic-pdf-translate` CLI) instead of
  loose scripts and a `module/` folder with import-time side effects (logging to `Output/log.txt`).
- Provider interface with an offline `mock` provider; Gemini moved from the deprecated
  `google-generativeai` SDK to `google-genai`, with configurable models and bounded concurrency.
- Target language is a parameter (the prototype was hard-wired to English).
- Page merge no longer duplicates the first element after each overlap window
  (`[:overlap+1]` vs `[overlap:]`) and handles pages shorter than the overlap.
- Translation failures no longer drop content silently.
- Pages are rasterised at 150 DPI (was PyMuPDF's 72 DPI default), which is better for OCR.
- Debug output is opt-in JSON (`--save-intermediate`) instead of always pickling page images
  and model responses.
- Cost estimate with hard-coded prices replaced by token counts (`Result.usage`).
