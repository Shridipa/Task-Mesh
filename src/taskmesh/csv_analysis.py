"""Deterministic CSV analysis workload used by the TaskMesh demo.

``csv.analyze`` reads the document with Python's strict ``csv`` reader, so
quoted values, commas inside quotes, escaped quotes and newlines inside quoted
fields all behave like a spreadsheet export. It reports:

* row, column and column-name counts (blank or duplicate headers are made
  unique rather than silently dropping a column),
* missing-value counts, per column and in total,
* numeric columns with count/mean/median/min/max,
* duplicate row count and the number of rows whose width differs from the
  header.

Rows shorter than the header are padded with empty values; rows longer than the
header keep their extra fields and are counted in ``ragged_rows`` so nothing is
dropped silently. Unparseable documents raise ``JobInputError``.
"""

from __future__ import annotations

import csv
import io
import statistics
from typing import Any

from .errors import JobInputError

CSV_JOB_TYPE = "csv.analyze"
MAX_CSV_LENGTH = 200_000
PREVIEW_ROWS = 5


def _unique_columns(header: list[str]) -> list[str]:
    """Strip header names and make duplicates unique (``name``, ``name_2``…)."""
    names: list[str] = []
    seen: dict[str, int] = {}

    for index, raw in enumerate(header):
        base = raw.strip() or f"column_{index + 1}"
        seen[base] = seen.get(base, 0) + 1
        names.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return names


def _is_missing(value: str | None) -> bool:
    return value is None or not str(value).strip()


def _numeric_stats(values: list[str]) -> dict[str, Any] | None:
    """Return statistics for the column, or ``None`` when it is not numeric."""
    numbers: list[float] = []
    for value in values:
        try:
            numbers.append(float(value.strip()))
        except ValueError:
            return None

    if not numbers:
        return None

    return {
        "count": len(numbers),
        "mean": round(statistics.fmean(numbers), 6),
        "median": round(statistics.median(numbers), 6),
        "min": round(min(numbers), 6),
        "max": round(max(numbers), 6),
    }


def analyze_csv(text: str) -> dict[str, Any]:
    """Return the analysis report for ``text`` or raise ``JobInputError``."""
    if not isinstance(text, str):
        raise JobInputError("payload.content must be a string")
    if not text.strip():
        raise JobInputError("CSV input must not be empty")
    if len(text) > MAX_CSV_LENGTH:
        raise JobInputError(f"CSV input must be at most {MAX_CSV_LENGTH} characters")

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        rows = list(reader)
    except csv.Error as exc:
        raise JobInputError(f"Invalid CSV near line {reader.line_num}: {exc}") from exc

    # A trailing blank line produces an empty row; drop only those.
    while rows and rows[-1] == []:
        rows.pop()

    if not rows:
        raise JobInputError("CSV input must contain a header row")

    columns = _unique_columns(rows[0])
    data_rows = rows[1:]
    width = len(columns)

    missing_by_column = {name: 0 for name in columns}
    column_values: dict[str, list[str]] = {name: [] for name in columns}
    duplicate_rows = 0
    ragged_rows = 0
    seen_rows: set[tuple[str, ...]] = set()
    preview: list[dict[str, str]] = []

    for row in data_rows:
        if len(row) != width:
            ragged_rows += 1

        padded = list(row[:width]) + [""] * max(width - len(row), 0)
        key = tuple(padded)
        if key in seen_rows:
            duplicate_rows += 1
        else:
            seen_rows.add(key)

        for index, name in enumerate(columns):
            value = padded[index]
            column_values[name].append(value)
            if _is_missing(value):
                missing_by_column[name] += 1

        if len(preview) < PREVIEW_ROWS:
            preview.append({name: padded[index] for index, name in enumerate(columns)})

    statistics_by_column: dict[str, dict[str, Any]] = {}
    numeric_columns: list[str] = []
    for name in columns:
        present = [value for value in column_values[name] if not _is_missing(value)]
        stats = _numeric_stats(present)
        if stats is not None:
            numeric_columns.append(name)
            statistics_by_column[name] = stats

    return {
        "rows": len(data_rows),
        "columns": width,
        "column_names": columns,
        "missing_values": {
            "total": sum(missing_by_column.values()),
            "by_column": missing_by_column,
        },
        "numeric_columns": numeric_columns,
        "statistics": statistics_by_column,
        "duplicate_rows": duplicate_rows,
        "ragged_rows": ragged_rows,
        "preview": preview,
    }
