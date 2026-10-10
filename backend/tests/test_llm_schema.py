# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from pydantic import BaseModel, Field

from app.llm.schema import to_strict_schema
import pytest

from app.models import RunSummary, TestSnippet


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


@pytest.mark.parametrize("model", [TestSnippet, RunSummary])
def test_every_object_is_strict(model):
    schema = to_strict_schema(model)
    objects = [n for n in walk(schema) if n.get("type") == "object"]
    assert objects, "expected object nodes"
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert sorted(obj["required"]) == sorted(obj["properties"])


def test_unsupported_keywords_removed_but_property_names_kept():
    class M(BaseModel):
        title: str = Field(default="x", min_length=1, title="Title")
        description: list[str] = Field(default_factory=list, max_length=3)

    schema = to_strict_schema(M)
    assert set(schema["properties"]) == {"title", "description"}
    flat = list(walk(schema))
    for banned in ("default", "minLength", "maxItems", "title"):
        assert not any(banned in n and n is not schema["properties"] for n in flat), banned
