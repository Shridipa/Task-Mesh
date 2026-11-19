"""Dependency-light CSV analysis workload."""
from __future__ import annotations
import csv, io, statistics
from typing import Any
CSV_JOB_TYPE="csv.analyze"
MAX_CSV_LENGTH=1_000_000

def analyze_csv(raw: str) -> dict[str,Any]:
    if not isinstance(raw,str): raise TypeError("csv_text must be a string")
    if not raw.strip(): raise ValueError("CSV input must not be empty")
    if len(raw)>MAX_CSV_LENGTH: raise ValueError(f"CSV input exceeds {MAX_CSV_LENGTH} characters")
    reader=csv.DictReader(io.StringIO(raw))
    headers=reader.fieldnames
    if not headers or any(not h for h in headers): raise ValueError("CSV must have non-empty column headers")
    rows=list(reader)
    if not rows: raise ValueError("CSV must contain at least one data row")
    if any(None in row for row in rows): raise ValueError("Rows contain more fields than the header")
    missing={h:sum(row.get(h) in (None,"") for row in rows) for h in headers}
    numeric={}
    for h in headers:
        vals=[]
        for row in rows:
            v=row.get(h,"").strip()
            if not v: continue
            try: vals.append(float(v))
            except ValueError: break
        else:
            if vals: numeric[h]={"count":len(vals),"mean":statistics.mean(vals),"median":statistics.median(vals),"min":min(vals),"max":max(vals)}
    duplicate_count=len(rows)-len({tuple(row.get(h) for h in headers) for row in rows})
    return {"rows":len(rows),"columns":len(headers),"column_names":headers,"missing_values":missing,"numeric_statistics":numeric,"duplicate_rows":duplicate_count}
