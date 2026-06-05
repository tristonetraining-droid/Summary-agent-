"""Thin Anthropic Claude wrapper with tool_use for structured Pydantic output."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Type, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

from . import config

T = TypeVar("T", bound=BaseModel)

_client: Anthropic | None = None


def client() -> Anthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _pydantic_to_tool(model: Type[BaseModel], name: str = "emit", description: str = "") -> dict:
    schema = model.model_json_schema()
    # Anthropic tool input_schema must be JSON-Schema-like; strip $defs cycles minimally.
    return {
        "name": name,
        "description": description or f"Emit a {model.__name__} object.",
        "input_schema": schema,
    }


def load_tone() -> str:
    return (config.PROMPTS_DIR / "tone_rules.txt").read_text(encoding="utf-8")


def load_prompt(filename: str) -> str:
    return (config.PROMPTS_DIR / filename).read_text(encoding="utf-8")


def call_structured(
    *,
    model: str,
    system: str,
    user: str,
    schema: Type[T],
    max_tokens: int = 4000,
    temperature: float = 0.2,
    extra_user_blocks: list[dict] | None = None,
) -> T:
    """Call Claude with a forced tool_use that matches the Pydantic schema."""
    tool = _pydantic_to_tool(schema, name="emit_" + schema.__name__.lower())
    content: list[dict] = [{"type": "text", "text": user}]
    if extra_user_blocks:
        content.extend(extra_user_blocks)

    resp = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": content}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return schema.model_validate(block.input)
    # Fallback: parse last text block as JSON
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            try:
                return schema.model_validate(json.loads(block.text))
            except Exception:
                continue
    raise RuntimeError(f"No structured tool_use returned for {schema.__name__}")


def call_json(
    *,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 4000,
    temperature: float = 0.2,
) -> Any:
    """Call Claude and parse a single JSON object out of the response text."""
    resp = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError(f"No JSON object in response: {text[:200]}")
    return json.loads(text[start : end + 1])
