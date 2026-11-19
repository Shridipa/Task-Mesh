"""Deterministic JSON validation workload used by the TaskMesh demo.

``json.validate`` parses the submitted document with Python's strict ``json``
decoder (``NaN``/``Infinity`` are rejected, as they are not valid JSON) and
reports either

* the canonical, indented rendering of the document plus structural statistics
  (root type, object/array/key/value counts, nesting depth), or
* the decoder's message with its 1-based line and column.

Invalid input is a ``JobInputError``: the job fails once with a readable reason
instead of being retried or reported as completed.
"""

from __future__ import annotations

import json
from typing import Any

from .errors import JobInputError

JSON_JOB_TYPE = "json.validate"
MAX_JSON_LENGTH = 100_000

_ROOT_TYPES = {
    dict: "object",
    list: "array",
    str: "string",
    bool: "boolean",
    int: "number",
    float: "number",
    type(None): "null",
}


def _reject_constant(name: str) -> Any:
    raise JobInputError(f"Invalid JSON: {name} is not valid JSON")


def _root_type(value: Any) -> str:
    for python_type, name in _ROOT_TYPES.items():
        if isinstance(value, python_type):
            return name
    return "unknown"


def summarize(value: Any) -> tuple[dict[str, int], int]:
    """Count nodes of ``value`` and return ``(counts, max_depth)``.

    The traversal uses an explicit stack so deeply nested documents cannot
    exhaust the interpreter's recursion limit.
    """
    counts = {
        "objects": 0,
        "arrays": 0,
        "keys": 0,
        "strings": 0,
        "numbers": 0,
        "booleans": 0,
        "nulls": 0,
    }
    max_depth = 1
    stack: list[tuple[Any, int]] = [(value, 1)]

    while stack:
        current, depth = stack.pop()
        max_depth = max(max_depth, depth)

        if isinstance(current, dict):
            counts["objects"] += 1
            counts["keys"] += len(current)
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            counts["arrays"] += 1
            stack.extend((child, depth + 1) for child in current)
        elif isinstance(current, str):
            counts["strings"] += 1
        elif isinstance(current, bool):
            # bool is a subclass of int, so it has to be checked first.
            counts["booleans"] += 1
        elif isinstance(current, (int, float)):
            counts["numbers"] += 1
        elif current is None:
            counts["nulls"] += 1

    return counts, max_depth


def validate_json(text: str) -> dict[str, Any]:
    """Return the validation report for ``text`` or raise ``JobInputError``."""
    if not isinstance(text, str):
        raise JobInputError("payload.content must be a string")
    if not text.strip():
        raise JobInputError("JSON input must not be empty")
    if len(text) > MAX_JSON_LENGTH:
        raise JobInputError(f"JSON input must be at most {MAX_JSON_LENGTH} characters")

    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise JobInputError(
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    counts, max_depth = summarize(value)
    return {
        "valid": True,
        "formatted": json.dumps(value, indent=2, ensure_ascii=False),
        "root_type": _root_type(value),
        "counts": counts,
        "max_depth": max_depth,
        "size": len(text),
    }
