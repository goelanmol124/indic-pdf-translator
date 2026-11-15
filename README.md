# indic-pdf-translator

**Layout-preserving PDF translation for scanned documents in Indian languages.**
It turns a PDF (scanned or born-digital) into a translated, print-ready HTML document that
keeps the original structure: headings, alignment, bold text, paragraphs and tables. It was
built for legal documents from Indian courts (for example Hindi court orders translated into
English), and the provider-based design works for any language pair the model supports.

```
PDF ──► page images ──► OCR ──► HTML layout ──► cross-page merge ──► chunked translation ──► HTML / PDF
                          (vision LLM)  │ ▲ render + review loop     (paragraphs, headers)     (tags kept)
                                        └─┘
```

## Why

Plain machine translation of a PDF loses everything that makes a legal document readable:
tables turn into word soup, paragraphs break at every line and page, and headers and page
numbers end up mid-sentence. This project treats the problem as **OCR → layout reconstruction
→ translation**. The layout is rebuilt as HTML first and checked against the page image, so
the translation step only has to translate text inside known markup.

## How it works

| Stage | What happens | Module |
|---|---|---|
| Rasterise | Each page is rendered to an image with PyMuPDF (default 150 DPI). The text layer is captured when the PDF has one. | `pdf.py` |
| OCR | A vision model transcribes the page exactly and marks unclear words as `<doubtful>`. | `providers/` |
| Layout | The model rebuilds the page as a list of HTML `<div>`/`<table>` elements, using the image as the source of truth and the OCR text as a hint. | `providers/` |
| Review loop | The layout is rendered with headless Chromium (optional), and the model compares the screenshot with the original page. On a *fail* it gets specific feedback and tries again, up to `--review-rounds` times. | `pipeline.py`, `render.py` |
| Merge | The last few elements of each page and the first few of the next are merged. This joins paragraphs split across a page break and drops running headers, footers and page numbers. Every element is used exactly once. | `layout.py`, `pipeline.py` |
| Translate | The merged layout is split into chunks of about 500 tokens and translated concurrently, keeping the HTML markup. A failed chunk stays untranslated and produces a warning, so content is never silently dropped. | `pipeline.py` |
| Render | A standalone HTML document with A4 print CSS and Noto fonts for each Indic script. It can also be exported to PDF through Chromium. | `render.py` |

## Providers

Providers are pluggable (`indic_pdf_translator.providers.Provider`):

| Provider | Needs | OCR | Layout | Review loop | Translation |
|---|---|---|---|---|---|
| `mock` (default) | nothing, works offline | PDF text layer | text blocks plus detected ruled tables, with alignment, bold and size heuristics | – | **pseudo-translation** (small English→Hindi glossary, or a `[xx]` tag for other targets) |
| `gemini` | `GEMINI_API_KEY`, `pip install .[gemini]` | Gemini vision | Gemini (JSON schema output) | yes | Gemini legal-translation prompt |

The `mock` provider lets you run the whole pipeline, the example and the tests without an
API key or network access. It is **not a real translator**, and it cannot read scanned pages
(they have no text layer). The `gemini` provider tries every configured model and prompt
variant in turn, so a quota error or a malformed reply falls through to the next one.

To add a backend such as OpenAI, a local model, IndicTrans2 or Bhashini, subclass `Provider`
and implement `ocr`, `layout`, `merge` and `translate`. `review_layout` is optional.

## Supported languages

Language codes are passed to the model by name: `en` English, `hi` Hindi, `bn` Bengali,
`mr` Marathi, `gu` Gujarati, `pa` Punjabi, `or` Odia, `ta` Tamil, `te` Telugu, `kn` Kannada,
`ml` Malayalam, `ur` Urdu, `as` Assamese, `ne` Nepali, `sa` Sanskrit. Unknown codes are passed
through unchanged. The HTML renderer detects Devanagari, Bengali, Gurmukhi, Gujarati, Odia,
Tamil, Telugu, Kannada, Malayalam and Urdu (Arabic script) text and applies the matching Noto
font. In practice the original project was tuned and used for **Hindi → English**; other pairs
depend on how well the model handles them.

## Quick start

```bash
git clone https://github.com/goelanmol124/indic-pdf-translator
cd indic-pdf-translator
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Offline demo: synthetic English sample PDF -> pseudo-Hindi HTML
python examples/make_sample_pdf.py examples/sample.pdf
indic-pdf-translate examples/sample.pdf --target hi -o output/sample.hi.html
pytest
```

Real translation with Gemini (for example a Hindi PDF into English):

```bash
pip install -e ".[gemini,render]"
playwright install chromium          # optional: screenshots for the review loop, and --pdf export
cp .env.example .env                 # then set GEMINI_API_KEY
indic-pdf-translate order.pdf --provider gemini --source hi --target en \
    -o output/order.en.html --pdf output/order.en.pdf
```

From Python:

```python
from indic_pdf_translator import Options, translate_pdf

result = translate_pdf("order.pdf", provider="gemini", options=Options(source="hi", target="en"))
open("order.en.html", "w", encoding="utf-8").write(result.html)
print(result.warnings, result.usage)
```

## Configuration

| Setting | CLI | Env | Default |
|---|---|---|---|
| Provider | `--provider` | `IPT_PROVIDER` | `mock` |
| API key | – | `GEMINI_API_KEY` | – |
| Models, tried in order | – | `GEMINI_MODELS` | `gemini-2.5-flash,gemini-2.0-flash` |
| Concurrent model requests | – | `IPT_CONCURRENCY` | `4` |
| Source / target language | `--source` / `--target` | – | `auto` / `en` |
| Rasterisation DPI | `--dpi` | – | `150` |
| Layout review rounds | `--review-rounds`, `--no-render-review` | – | `2`, with screenshots if Playwright is installed |
| Intermediate JSON | `--save-intermediate DIR` | – | off |

`.env` is loaded automatically when `python-dotenv` is installed. It is included in the `gemini` extra.

> `--save-intermediate` writes the OCR and layout text of your document. Treat it, and
> everything under `output/`, as confidential. Both are git-ignored.

## Project layout

```
src/indic_pdf_translator/
  cli.py          command-line entry point (indic-pdf-translate)
  pipeline.py     orchestration: OCR -> layout/review -> merge -> translate -> render
  pdf.py          rasterisation, text layer and table detection (PyMuPDF)
  layout.py       page head/body/tail split, stitching, chunking (pure functions)
  render.py       HTML document builder, Playwright screenshot / PDF export
  htmltext.py     transform text nodes while keeping tags
  prompts.py      OCR / layout / review / merge / translation prompts and JSON schemas
  languages.py    language codes, Indic script detection
  providers/      base.py (interface), mock.py (offline), gemini.py (Google Gemini)
examples/         make_sample_pdf.py: synthetic two-page sample (no real data)
tests/            pytest suite, runs offline
docs/             architecture notes
```

## Limitations

- **Output is HTML (optionally printed to PDF), not a copy of the original PDF with text swapped in place.**
  "Layout-preserving" means structure (reading order, headings, alignment, emphasis, tables) is
  kept, not pixel positions, original fonts, stamps or signatures.
- Translation quality, OCR accuracy and cost depend on the model. LLM output can be wrong or
  incomplete. **A qualified human must review any translation used in court or for legal purposes.**
- Each page needs several model calls (OCR, layout, review rounds), plus one per page boundary
  and one per chunk, so long documents are slow and cost real money.
- Documents are sent to the model provider. Do not process confidential documents with a
  provider your data-handling obligations don't allow.
- The `mock` provider's translation is a placeholder, and it only works on PDFs with a text layer.
- Tables that continue across a page break are merged by the model, not deterministically.

## Development

```bash
pip install -e ".[dev]"
pytest -q
```

The tests generate their own synthetic PDF and use the mock provider and a fake Gemini client,
so they need no network access or keys.
