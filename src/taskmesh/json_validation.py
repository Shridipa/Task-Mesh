"""JSON validation and formatting workload."""
from __future__ import annotations
import json
from typing import Any
JSON_JOB_TYPE = "json.validate"
MAX_JSON_LENGTH = 100_000

def validate_json(raw: str) -> dict[str, Any]:
    if not isinstance(raw,str): raise TypeError("json_text must be a string")
    if not raw.strip(): raise ValueError("JSON input must not be empty")
    if len(raw)>MAX_JSON_LENGTH: raise ValueError(f"JSON input exceeds {MAX_JSON_LENGTH} characters")
    try: value=json.loads(raw)
    except json.JSONDecodeError as exc: return {"valid":False,"error":exc.msg,"line":exc.lineno,"column":exc.colno,"formatted":None}
    formatted=json.dumps(value,indent=2,ensure_ascii=False)
    def counts(v):
        objects=arrays=keys=0
        if isinstance(v,dict):
            objects+=1; keys+=len(v)
            for x in v.values(): a,b,c=counts(x); objects+=a;arrays+=b;keys+=c
        elif isinstance(v,list):
            arrays+=1
            for x in v: a,b,c=counts(x);objects+=a;arrays+=b;keys+=c
        return objects,arrays,keys
    objects,arrays,keys=counts(value)
    return {"valid":True,"formatted":formatted,"root_type":type(value).__name__,"objects":objects,"arrays":arrays,"keys":keys}
