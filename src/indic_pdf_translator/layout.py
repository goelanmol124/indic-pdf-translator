"""Pure helpers for page stitching and translation chunking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PageSplit:
    head: list[str]  # first elements, sent to the boundary merge with the previous page
    body: list[str]  # kept as-is
    tail: list[str]  # last elements, sent to the boundary merge with the next page


def split_pages(layouts: list[list[str]], overlap: int) -> list[PageSplit]:
    """Split each page layout into head/body/tail so no element is used twice.

    The first page has no head and the last page has no tail. Short pages give
    their elements to the head first, so ``head + body + tail == layout`` always.
    """
    n = len(layouts)
    splits = []
    for i, layout in enumerate(layouts):
        head = layout[:overlap] if i > 0 else []
        rest = layout[len(head):]
        tail_len = min(overlap, len(rest)) if i < n - 1 else 0
        body = rest[: len(rest) - tail_len]
        tail = rest[len(rest) - tail_len:]
        splits.append(PageSplit(head, body, tail))
    return splits


def stitch(splits: list[PageSplit], merged_boundaries: list[list[str]]) -> list[str]:
    """Join page bodies with the merged boundary segments between them."""
    if len(merged_boundaries) != max(len(splits) - 1, 0):
        raise ValueError("need exactly one merged boundary per adjacent page pair")
    out: list[str] = []
    for i, s in enumerate(splits):
        # The first page's head and the last page's tail are always empty.
        out.extend(s.body)
        if i < len(merged_boundaries):
            out.extend(merged_boundaries[i])
    return out


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_layout(layout: list[str], max_tokens: int = 500) -> list[list[str]]:
    """Group consecutive HTML elements into chunks of roughly ``max_tokens``."""
    chunks: list[list[str]] = []
    cur: list[str] = []
    count = 0
    for el in layout:
        cur.append(el)
        count += estimate_tokens(el)
        if count >= max_tokens:
            chunks.append(cur)
            cur, count = [], 0
    if cur:
        chunks.append(cur)
    return chunks
