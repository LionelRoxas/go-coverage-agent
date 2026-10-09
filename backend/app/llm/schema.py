# AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"""Convert a Pydantic JSON Schema into the subset Groq strict mode accepts."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

_UNSUPPORTED = {"title", "default", "minLength", "maxLength", "minItems", "maxItems",
                "pattern", "format", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}


def _walk(node: Any) -> Any:
    if isinstance(node, list):
        return [_walk(v) for v in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED:
            continue
        if key in ("properties", "$defs"):
            out[key] = {name: _walk(sub) for name, sub in value.items()}  # keep names, clean bodies
        else:
            out[key] = _walk(value)
    if out.get("type") == "object" and "properties" in out:
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    return out


def to_strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    return _walk(model.model_json_schema())
