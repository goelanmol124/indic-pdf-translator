"""Prompts for the LLM provider stages (OCR, layout, review, merge, translate).

Ported from the original Hindi -> English legal translation pipeline; the target
language is now a parameter.
"""

from __future__ import annotations

OCR_SYSTEM = (
    "Perform precise OCR for a legal document. "
    "Transcribe the text exactly as it appears, preserving all formatting, including special "
    "characters and punctuation. Provide the output as plain text without any summarization or "
    "paraphrasing. Enclose any unclear or uncertain words within <doubtful> tags."
)
OCR_PROMPTS = [
    OCR_SYSTEM,
    "Perform OCR for a legal document.",
    "Provide the exact text as given in the provided image.",
]

LAYOUT_SYSTEM = (
    "Analyze the image and the text content (obtained through OCR, partially correct, may contain errors) "
    "to create an HTML layout of the page with logical text flow. "
    "Classify content as table or paragraph; table-like structures, including borderless ones, are tables and "
    "must be valid HTML tables that keep their structure. "
    "Different lines of the same paragraph must be a single div element so the text flows correctly. "
    "Create a new div only for a new paragraph, table or similar block. "
    "Add inline style for alignment (left, right, center, justify), bold, and font size (14 for normal text). "
    "IMPORTANT: the image is the source of truth for the text; the OCR text may contain errors. "
    "IMPORTANT: no text may be added or removed. "
    "IMPORTANT: if feedback from a previous attempt is provided, fix every issue it lists. "
    "Mark doubtful OCR text in red using a span with class=\"doubtful\". "
    "Handle signatures and oddly formatted text gracefully. Use simple, relevant HTML. "
    "Output JSON with HTMLlayout: a list of HTML div elements in reading order."
)
LAYOUT_PROMPTS = [LAYOUT_SYSTEM, "Process the given image and text."]

REVIEW_SYSTEM = (
    "You are a quality-assurance proofreader. You are given the original page image, optionally a rendered "
    "image of an HTML layout, and the HTML layout itself. Compare them, in this order of priority: "
    "1. No section of the original is missing and no text was added; name the exact words missing, added or misread. "
    "2. Tables and paragraphs are identified correctly (tables may have invisible borders). "
    "3. Elements appear in the same order as the original. "
    "4. Alignment is correct. 5. Formatting (bold, italics) is correct. "
    "Doubtful text must be marked in red. Div elements must follow a logical flow. "
    "Give very specific, actionable changes to the HTML layout. "
    "Return status 'pass' if the layout is accurate, otherwise 'fail' with feedback."
)
REVIEW_PROMPTS = [
    REVIEW_SYSTEM,
    "Validate the rendered layout against the original. Check words, order, tables, alignment and formatting, "
    "and give very specific fixes for any issue found.",
]

MERGE_SYSTEM = (
    "Merge adjacent page segments of a legal document:\n"
    "1. Join the end of the previous page with the start of the next page.\n"
    "2. Keep the original formatting and structure.\n"
    "3. Remove repeated headers, footers and page numbers.\n"
    "4. Merge paragraphs that were split across the page break into single elements.\n"
    "5. Keep unclear text marked in red.\n"
    "Use only the content provided as text; the images are only for reference. "
    "Output JSON with HTMLlayout: a list of HTML elements."
)
MERGE_PROMPTS = [MERGE_SYSTEM, "Merge the end of the previous page with the start of the next page."]


def translate_system(target: str, source: str) -> str:
    src = f" from {source}" if source and not source.startswith("the source") else ""
    return (
        "You are an expert legal translator specialising in accurate, precise document translation. "
        f"Translate the provided document{src} into fluent, legally sound {target}, keeping the original "
        "meaning and losing no information.\n"
        "Input: HTML-formatted text extracted from a scanned document by OCR; it may contain OCR errors.\n"
        "Rules:\n"
        f"1. Translate the text into {target} suitable for legal use.\n"
        "2. Correct obvious OCR errors using context; prefer accuracy over a literal rendering of flawed OCR.\n"
        "3. If a segment remains doubtful, mark the translated phrase with strikethrough (<s>).\n"
        "4. Do not hallucinate: add no information and do not change the meaning or gravity of the text.\n"
        "5. Drop elements that are clearly not document content (page numbers, scribbles, artefacts).\n"
        "6. Preserve the HTML structure and formatting; ignore stray line breaks inside paragraphs.\n"
        "7. Do not summarise, paraphrase or comment.\n"
        f"8. The output text must be in {target} only.\n"
        "Output JSON with HTMLlayout: the list of translated HTML elements."
    )


def translate_prompts(target: str, source: str) -> list[str]:
    return [
        translate_system(target, source),
        f"Translate this legal document precisely into {target}, keeping all HTML formatting.",
    ]


LAYOUT_SCHEMA = {
    "type": "OBJECT",
    "required": ["HTMLlayout"],
    "properties": {"HTMLlayout": {"type": "ARRAY", "items": {"type": "STRING"}}},
}
OCR_SCHEMA = {"type": "OBJECT", "required": ["ocr"], "properties": {"ocr": {"type": "STRING"}}}
REVIEW_SCHEMA = {
    "type": "OBJECT",
    "required": ["status", "feedback"],
    "properties": {
        "status": {"type": "STRING", "enum": ["pass", "fail"]},
        "feedback": {"type": "STRING"},
        "specific_issues": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "description": {"type": "STRING"},
                    "severity": {"type": "STRING", "enum": ["critical", "warning", "info"]},
                    "suggested_fix": {"type": "STRING"},
                },
            },
        },
    },
}
