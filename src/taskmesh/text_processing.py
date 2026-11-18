"""Deterministic text-processing workload used by the TaskMesh demo.

The rules are intentionally simple and fixed so the same input always produces
the same output:

* Whitespace: Windows/old-Mac line endings become ``\\n``, runs of horizontal
  whitespace collapse to one space, every line is stripped, and runs of three
  or more newlines collapse to a single blank line.
* Words: whitespace-separated tokens in the cleaned text.
* Characters: every character in the cleaned text, spaces and newlines included.
* Sentences: text segments separated by ``.``, ``!`` or ``?`` (empty segments
  are ignored, so trailing punctuation does not create an extra sentence).
* Lines: lines in the cleaned text, separated by ``\\n``.

Only text is processed. Submitted input is never evaluated as code.
"""

from __future__ import annotations

import re
from typing import Any

TEXT_JOB_TYPE = "text.process"
MAX_TEXT_LENGTH = 10_000

_HORIZONTAL_WHITESPACE = re.compile(r"[ \t\f\v]+")
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")
_SENTENCE_SEPARATOR = re.compile(r"[.!?]+")


def clean_text(text: str) -> str:
    """Normalize whitespace in ``text`` without changing any other character."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _HORIZONTAL_WHITESPACE.sub(" ", normalized)
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    normalized = _EXTRA_BLANK_LINES.sub("\n\n", normalized)
    return normalized.strip()


def count_sentences(text: str) -> int:
    """Count sentence segments, ignoring empty fragments between terminators."""
    if not text:
        return 0
    segments = _SENTENCE_SEPARATOR.split(text)
    return len([segment for segment in segments if segment.strip()])


def process_text(text: str) -> dict[str, Any]:
    """Return the word/character/sentence/line counts and cleaned text."""
    if not isinstance(text, str):
        raise TypeError("payload.text must be a string")
    if not text.strip():
        raise ValueError("text must not be empty")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError(f"text must be at most {MAX_TEXT_LENGTH} characters")

    cleaned = clean_text(text)
    return {
        "words": len(cleaned.split()),
        "characters": len(cleaned),
        "sentences": count_sentences(cleaned),
        "lines": len(cleaned.split("\n")) if cleaned else 0,
        "cleaned_text": cleaned,
    }
