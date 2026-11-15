"""indic-pdf-translator: layout-preserving PDF translation for Indian-language documents."""

__version__ = "0.2.0"

from .pipeline import Options, Result, translate_pdf, translate_pdf_async  # noqa: E402
from .providers import Provider, get_provider  # noqa: E402

__all__ = ["Options", "Result", "translate_pdf", "translate_pdf_async", "Provider", "get_provider", "__version__"]
