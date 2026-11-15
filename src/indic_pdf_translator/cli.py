"""Command-line interface: ``indic-pdf-translate input.pdf -o output.html``."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .languages import LANGUAGES
from .pipeline import Options, translate_pdf_async
from .providers import PROVIDERS, get_provider
from .render import html_to_pdf


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="indic-pdf-translate",
        description="Layout-preserving PDF translation (OCR -> HTML layout -> merge -> translate).",
    )
    p.add_argument("input", type=Path, help="input PDF")
    p.add_argument("-o", "--output", type=Path, help="output HTML (default: output/<name>.<target>.html)")
    p.add_argument("--pdf", type=Path, help="also export a PDF (needs the 'render' extra)")
    p.add_argument("-p", "--provider", choices=PROVIDERS, default=None,
                   help="model provider (default: $IPT_PROVIDER or 'mock')")
    p.add_argument("-t", "--target", default="en", help=f"target language code ({', '.join(c for c in LANGUAGES if c != 'auto')})")
    p.add_argument("-s", "--source", default="auto", help="source language code (default: auto)")
    p.add_argument("--dpi", type=int, default=150, help="page rasterisation DPI (default: 150)")
    p.add_argument("--review-rounds", type=int, default=2, help="max layout review/retry rounds (default: 2)")
    p.add_argument("--no-render-review", action="store_true", help="review layouts without a browser screenshot")
    p.add_argument("--save-intermediate", type=Path, metavar="DIR",
                   help="write intermediate JSON (contains document text; keep private)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


async def _run(args: argparse.Namespace) -> int:
    name = args.provider or os.environ.get("IPT_PROVIDER", "mock")
    kwargs = {}
    if name == "gemini" and os.environ.get("IPT_CONCURRENCY"):
        kwargs["concurrency"] = int(os.environ["IPT_CONCURRENCY"])
    provider = get_provider(name, **kwargs)
    opts = Options(
        target=args.target,
        source=args.source,
        dpi=args.dpi,
        max_review_rounds=args.review_rounds,
        render_for_review=not args.no_render_review,
    )
    result = await translate_pdf_async(args.input, provider, opts)

    out = args.output or Path("output") / f"{args.input.stem}.{args.target}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.html, encoding="utf-8")
    print(f"HTML written to {out}")
    if args.pdf:
        args.pdf.parent.mkdir(parents=True, exist_ok=True)
        args.pdf.write_bytes(await html_to_pdf(result.html))
        print(f"PDF written to {args.pdf}")
    if args.save_intermediate:
        print(f"Intermediate data written to {result.save_intermediate(args.save_intermediate)}")
    u = result.usage
    print(f"{result.page_count} page(s), {len(result.translated_layout)} element(s), provider={provider.name}, "
          f"requests={u.requests}, tokens in/out={u.input_tokens}/{u.output_tokens}")
    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _load_dotenv()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    if not args.input.is_file():
        print(f"error: {args.input} not found", file=sys.stderr)
        return 2
    try:
        return asyncio.run(_run(args))
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
