"""Pluggable model providers."""

from __future__ import annotations

from typing import Any

from .base import Provider, Review, Usage
from .mock import MockProvider

PROVIDERS = ("mock", "gemini")


def get_provider(name: str, **kwargs: Any) -> Provider:
    """Create a provider by name (``mock`` or ``gemini``)."""
    name = name.lower()
    if name == "mock":
        return MockProvider()
    if name == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(**kwargs)
    raise ValueError(f"unknown provider {name!r}; choose one of {', '.join(PROVIDERS)}")


__all__ = ["Provider", "Review", "Usage", "MockProvider", "get_provider", "PROVIDERS"]
