"""Provider interface: every model-backed stage of the pipeline goes through here."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PIL import Image

from ..pdf import Page


@dataclass
class Review:
    passed: bool
    feedback: str = ""


@dataclass
class Usage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    by_model: dict[str, int] = field(default_factory=dict)


class Provider(ABC):
    """A backend that can read, lay out, merge and translate document pages."""

    name: str = "base"
    #: whether ``review_layout`` does anything (enables the render -> review -> retry loop)
    supports_review: bool = False

    def __init__(self) -> None:
        self.usage = Usage()

    @abstractmethod
    async def ocr(self, page: Page) -> str:
        """Return the page text."""

    @abstractmethod
    async def layout(self, page: Page, ocr_text: str, feedback: str | None = None) -> list[str]:
        """Return the page as an ordered list of HTML elements."""

    async def review_layout(self, page: Page, layout: list[str], rendered: Image.Image | None) -> Review:
        """Check a layout against the page image. Default: accept."""
        return Review(passed=True)

    @abstractmethod
    async def merge(self, prev_tail: list[str], next_head: list[str], prev: Page, nxt: Page) -> list[str]:
        """Merge the end of one page with the start of the next (split paragraphs, running headers...)."""

    @abstractmethod
    async def translate(self, chunk: list[str], target: str, source: str) -> list[str]:
        """Translate a chunk of HTML elements, keeping their markup."""

    async def aclose(self) -> None:  # pragma: no cover - hook for providers holding connections
        return None
