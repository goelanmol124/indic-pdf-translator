"""Google Gemini provider (vision OCR + structured JSON output).

Needs the ``gemini`` extra (``google-genai``) and ``GEMINI_API_KEY``. Every call
tries each prompt variant against each configured model in order, so a model
outage or a malformed JSON reply falls through to the next option.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from PIL import Image

from .. import prompts as P
from ..languages import language_name
from ..pdf import Page
from .base import Provider, Review

log = logging.getLogger(__name__)

DEFAULT_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]


class GenerationError(RuntimeError):
    pass


class GeminiProvider(Provider):
    name = "gemini"
    supports_review = True

    def __init__(
        self,
        api_key: str | None = None,
        models: list[str] | None = None,
        concurrency: int = 4,
        client: Any = None,
    ) -> None:
        super().__init__()
        env_models = [m.strip() for m in os.environ.get("GEMINI_MODELS", "").split(",") if m.strip()]
        self.models = models or env_models or list(DEFAULT_MODELS)
        self._sem = asyncio.Semaphore(concurrency)
        if client is None:
            api_key = api_key or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise GenerationError("GEMINI_API_KEY is not set (see .env.example)")
            try:
                from google import genai
            except ImportError as e:  # pragma: no cover
                raise GenerationError("Install the gemini extra: pip install 'indic-pdf-translator[gemini]'") from e
            client = genai.Client(api_key=api_key)
        self._client = client

    # ------------------------------------------------------------------ core
    async def generate(
        self,
        contents: list[Any],
        prompts: list[str],
        system: str,
        schema: dict,
        temperature: float = 0.1,
        top_p: float = 0.2,
        max_output_tokens: int = 8192,
    ) -> dict:
        """Run a structured-JSON generation with prompt x model fallbacks."""
        errors = []
        for prompt in prompts:
            for model in self.models:
                try:
                    return await self._call(model, [prompt, *contents, prompt], system, schema,
                                            temperature, top_p, max_output_tokens)
                except Exception as e:  # network, quota, safety block, bad JSON...
                    log.warning("Gemini %s failed: %s", model, e)
                    errors.append(f"{model}: {e}")
        raise GenerationError("all Gemini attempts failed: " + "; ".join(errors[-4:]))

    async def _call(self, model, contents, system, schema, temperature, top_p, max_output_tokens) -> dict:
        config = {
            "system_instruction": system,
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        async with self._sem:
            resp = await self._client.aio.models.generate_content(model=model, contents=contents, config=config)
        meta = getattr(resp, "usage_metadata", None)
        self.usage.requests += 1
        self.usage.by_model[model] = self.usage.by_model.get(model, 0) + 1
        if meta is not None:
            self.usage.input_tokens += getattr(meta, "prompt_token_count", 0) or 0
            self.usage.output_tokens += getattr(meta, "candidates_token_count", 0) or 0
        text = resp.text
        if not text:
            raise GenerationError("empty response")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise GenerationError("response is not a JSON object")
        return data

    @staticmethod
    def _html_list(data: dict) -> list[str]:
        items = data.get("HTMLlayout")
        if not isinstance(items, list):
            raise GenerationError("response has no HTMLlayout list")
        return [str(i) for i in items]

    # ---------------------------------------------------------------- stages
    async def ocr(self, page: Page) -> str:
        data = await self.generate([page.image], P.OCR_PROMPTS, P.OCR_SYSTEM, P.OCR_SCHEMA, top_p=0.1)
        return str(data.get("ocr", "")).strip()

    async def layout(self, page: Page, ocr_text: str, feedback: str | None = None) -> list[str]:
        contents: list[Any] = [page.image, ocr_text]
        if feedback:
            contents.append("Feedback on the previous attempt (fix all of it):\n" + feedback)
        max_tokens = min(max(2048, len(ocr_text) * 5), 65536)
        data = await self.generate(contents, P.LAYOUT_PROMPTS, P.LAYOUT_SYSTEM, P.LAYOUT_SCHEMA,
                                   top_p=0.1, max_output_tokens=max_tokens)
        return self._html_list(data)

    async def review_layout(self, page: Page, layout: list[str], rendered: Image.Image | None) -> Review:
        contents: list[Any] = [page.image]
        if rendered is not None:
            contents.append(rendered)
        contents.append(f"Generated HTMLlayout: {json.dumps(layout, ensure_ascii=False)}")
        try:
            data = await self.generate(contents, P.REVIEW_PROMPTS, P.REVIEW_SYSTEM, P.REVIEW_SCHEMA,
                                       max_output_tokens=2048)
        except GenerationError as e:
            log.warning("Layout review failed, accepting layout: %s", e)
            return Review(passed=True)
        passed = data.get("status") != "fail"
        feedback = json.dumps({k: data.get(k) for k in ("feedback", "specific_issues")}, ensure_ascii=False)
        return Review(passed=passed, feedback=feedback)

    async def merge(self, prev_tail: list[str], next_head: list[str], prev: Page, nxt: Page) -> list[str]:
        contents = [
            prev.image,
            nxt.image,
            "Content to be merged:\nPrevious page end: "
            f"{json.dumps(prev_tail, ensure_ascii=False)}\nNext page start: {json.dumps(next_head, ensure_ascii=False)}",
            "Use only the content provided in the text to merge.",
        ]
        data = await self.generate(contents, P.MERGE_PROMPTS, P.MERGE_SYSTEM, P.LAYOUT_SCHEMA, max_output_tokens=4096)
        return self._html_list(data)

    async def translate(self, chunk: list[str], target: str, source: str) -> list[str]:
        tgt, src = language_name(target), language_name(source)
        text = "Provided HTML OCR text: ```" + json.dumps(chunk, ensure_ascii=False) + "```"
        data = await self.generate([text], P.translate_prompts(tgt, src), P.translate_system(tgt, src),
                                   P.LAYOUT_SCHEMA)
        return self._html_list(data)
