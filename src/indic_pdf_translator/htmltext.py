"""Transform the text nodes of an HTML fragment while keeping its tags intact."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from typing import Callable

_TAG_RE = re.compile(r"<[^>]+>")


class _Rewriter(HTMLParser):
    def __init__(self, fn: Callable[[str], str]):
        super().__init__(convert_charrefs=True)
        self.fn = fn
        self.out: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text() or f"<{tag}>")

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text() or f"<{tag}/>")

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if data.strip():
            lead = data[: len(data) - len(data.lstrip())]
            trail = data[len(data.rstrip()):]
            data = lead + html.escape(self.fn(data.strip()), quote=False) + trail
        else:
            data = html.escape(data, quote=False)
        self.out.append(data)


def map_text(fragment: str, fn: Callable[[str], str]) -> str:
    """Apply ``fn`` to every non-blank text node of ``fragment``."""
    p = _Rewriter(fn)
    p.feed(fragment)
    p.close()
    return "".join(p.out)


def strip_tags(fragment: str) -> str:
    return html.unescape(_TAG_RE.sub("", fragment)).strip()
