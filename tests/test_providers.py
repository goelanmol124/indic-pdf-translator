"""Provider behaviour without network: the Gemini provider runs against a fake client."""

import json
from types import SimpleNamespace

import pytest

from indic_pdf_translator import Options, translate_pdf_async
from indic_pdf_translator.pdf import Page
from indic_pdf_translator.providers import Provider, Review, get_provider
from indic_pdf_translator.providers.gemini import GeminiProvider, GenerationError
from indic_pdf_translator.providers.mock import pseudo_translate


class FakeModels:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def generate_content(self, model, contents, config):
        self.calls.append((model, contents, config))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(text=json.dumps(reply) if not isinstance(reply, str) else reply,
                               usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=5))


def fake_client(replies):
    models = FakeModels(replies)
    return SimpleNamespace(aio=SimpleNamespace(models=models)), models


def _page():
    from PIL import Image
    return Page(index=0, image=Image.new("RGB", (10, 10), "white"), width=10, height=10)


def test_get_provider():
    assert get_provider("mock").name == "mock"
    with pytest.raises(ValueError):
        get_provider("nope")


def test_gemini_requires_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(GenerationError):
        GeminiProvider()


async def test_gemini_falls_back_across_models():
    client, models = fake_client([RuntimeError("quota"), "not json", {"HTMLlayout": ["<div>ok</div>"]}])
    prov = GeminiProvider(client=client, models=["m1", "m2"])
    out = await prov.translate(["<div>नमस्ते</div>"], "en", "hi")
    assert out == ["<div>ok</div>"]
    # prompt 1 x (m1, m2) failed, then prompt 2 on m1 succeeded
    assert [c[0] for c in models.calls] == ["m1", "m2", "m1"]
    cfg = models.calls[-1][2]
    assert cfg["response_mime_type"] == "application/json"
    assert "English" in cfg["system_instruction"] and "Hindi" in cfg["system_instruction"]
    assert prov.usage.input_tokens == 20 and prov.usage.output_tokens == 10


async def test_gemini_all_attempts_fail():
    client, _ = fake_client([RuntimeError("x")] * 4)
    prov = GeminiProvider(client=client, models=["m1", "m2"])
    with pytest.raises(GenerationError):
        await prov.translate(["<div>a</div>"], "en", "auto")


async def test_gemini_ocr_and_review():
    client, _ = fake_client([{"ocr": "  text  "}, {"status": "fail", "feedback": "missing word"}])
    prov = GeminiProvider(client=client, models=["m"])
    assert await prov.ocr(_page()) == "text"
    review = await prov.review_layout(_page(), ["<div>t</div>"], None)
    assert not review.passed and "missing word" in review.feedback


class FlakyProvider(Provider):
    """Exercises the review loop and the no-content-loss fallbacks."""

    name = "flaky"
    supports_review = True

    def __init__(self):
        super().__init__()
        self.layout_calls = 0

    async def ocr(self, page):
        return page.text

    async def layout(self, page, ocr_text, feedback=None):
        self.layout_calls += 1
        return [f"<div>page {page.index} v{self.layout_calls if feedback else 0}</div>"]

    async def review_layout(self, page, layout, rendered):
        return Review(passed="v0" not in layout[0], feedback="fix it")

    async def merge(self, prev_tail, next_head, prev, nxt):
        raise RuntimeError("merge down")

    async def translate(self, chunk, target, source):
        raise RuntimeError("translate down")


async def test_pipeline_review_loop_and_fallbacks(sample_pdf):
    prov = FlakyProvider()
    res = await translate_pdf_async(sample_pdf, prov, Options(dpi=72, render_for_review=False))
    assert prov.layout_calls == 4  # 2 pages x (initial + one retry after a failed review)
    assert res.translated_layout == res.source_layout  # untranslated, but nothing dropped
    assert len(res.source_layout) == 2
    assert any("merge" in w for w in res.warnings)
    assert any("translation" in w for w in res.warnings)


def test_pseudo_translate():
    assert pseudo_translate("The court order", "hi") == "न्यायालय आदेश"
    assert pseudo_translate("Hello", "bn") == "[bn] Hello"
