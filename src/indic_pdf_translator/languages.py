"""Language codes and Unicode script detection for Indian languages."""

from __future__ import annotations

LANGUAGES: dict[str, str] = {
    "auto": "the source language (auto-detect)",
    "en": "English",
    "hi": "Hindi",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "or": "Odia",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "ur": "Urdu",
    "as": "Assamese",
    "ne": "Nepali",
    "sa": "Sanskrit",
}

# Unicode block -> (css class, Google Noto font family)
SCRIPTS: list[tuple[int, int, str, str]] = [
    (0x0900, 0x097F, "devanagari", "Noto Sans Devanagari"),
    (0x0980, 0x09FF, "bengali", "Noto Sans Bengali"),
    (0x0A00, 0x0A7F, "gurmukhi", "Noto Sans Gurmukhi"),
    (0x0A80, 0x0AFF, "gujarati", "Noto Sans Gujarati"),
    (0x0B00, 0x0B7F, "oriya", "Noto Sans Oriya"),
    (0x0B80, 0x0BFF, "tamil", "Noto Sans Tamil"),
    (0x0C00, 0x0C7F, "telugu", "Noto Sans Telugu"),
    (0x0C80, 0x0CFF, "kannada", "Noto Sans Kannada"),
    (0x0D00, 0x0D7F, "malayalam", "Noto Sans Malayalam"),
    (0x0600, 0x06FF, "arabic", "Noto Nastaliq Urdu"),
]


def language_name(code: str) -> str:
    """Return a human-readable language name; unknown codes are passed through."""
    return LANGUAGES.get(code.lower(), code)


def detect_script(text: str) -> str | None:
    """Return the css class of the first Indic script found in ``text``, else None."""
    for ch in text:
        cp = ord(ch)
        if cp < 0x0600:
            continue
        for lo, hi, cls, _font in SCRIPTS:
            if lo <= cp <= hi:
                return cls
    return None
