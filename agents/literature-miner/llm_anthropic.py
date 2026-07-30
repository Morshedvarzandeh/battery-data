#!/usr/bin/env python3
"""
Anthropic API adapter for the literature-miner.

Implements the pipeline's `LLM` protocol using plain urllib - no SDK, no
dependencies - so it runs anywhere Python does, including a bare CI image.

Structured output is enforced, not requested: every call defines a tool
whose input schema is the JSON Schema the pipeline expects, and forces the
model to call it (`tool_choice`). The API then validates the shape, which
is materially more reliable than asking for JSON in prose and parsing it.

    export ANTHROPIC_API_KEY=sk-ant-...
    from llm_anthropic import AnthropicLLM
    llm = AnthropicLLM()                       # or AnthropicLLM(model="...")
    out = llm.complete(prompt, schema=TRIAGE_SCHEMA)   # -> validated dict
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

# Cheap-and-fast is deliberate for triage volume; override per stage.
DEFAULT_MODEL = os.getenv("MINER_MODEL", "claude-3-5-haiku-latest")
EXTRACT_MODEL = os.getenv("MINER_EXTRACT_MODEL", "claude-sonnet-4-5")


class LLMError(RuntimeError):
    pass


class AnthropicLLM:
    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None,
                 max_tokens: int = 4096, temperature: float = 0.0,
                 retries: int = 4):
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.retries = retries
        if not self.api_key:
            raise LLMError(
                "ANTHROPIC_API_KEY is not set. Create a key at "
                "console.anthropic.com and export it (or add it as a GitHub "
                "Actions secret for the scheduled miner)."
            )

    # ------------------------------------------------------------------
    def complete(self, prompt: str, *, schema: dict | None = None,
                 images: list[bytes] | None = None):
        content: list[dict] = []
        for img in images or []:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png",
                           "data": base64.b64encode(img).decode()},
            })
        content.append({"type": "text", "text": prompt})

        body: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": content}],
        }

        if schema is not None:
            # Force a tool call whose input IS the required schema.
            body["tools"] = [{
                "name": "emit",
                "description": "Return the structured result.",
                "input_schema": schema,
            }]
            body["tool_choice"] = {"type": "tool", "name": "emit"}

        resp = self._post(body)

        if schema is not None:
            for block in resp.get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "emit":
                    return block["input"]
            raise LLMError(f"model returned no tool call: "
                           f"{json.dumps(resp)[:400]}")

        return "".join(b.get("text", "") for b in resp.get("content", [])
                       if b.get("type") == "text")

    # ------------------------------------------------------------------
    def _post(self, body: dict) -> dict:
        data = json.dumps(body).encode()
        last: Exception | None = None
        for attempt in range(self.retries):
            req = urllib.request.Request(
                API_URL, data=data, method="POST",
                headers={"Content-Type": "application/json",
                         "x-api-key": self.api_key,
                         "anthropic-version": API_VERSION})
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:400]
                # retry on rate limit / overload / transient server errors
                if e.code in (429, 500, 502, 503, 529) and attempt < self.retries - 1:
                    time.sleep(min(2 ** attempt * 2, 30))
                    last = LLMError(f"HTTP {e.code}: {detail}")
                    continue
                raise LLMError(f"HTTP {e.code}: {detail}") from e
            except OSError as e:
                if attempt < self.retries - 1:
                    time.sleep(2 ** attempt)
                    last = e
                    continue
                raise LLMError(f"network error: {e}") from e
        raise LLMError(f"exhausted retries: {last}")


def get_llm(stage: str = "triage"):
    """Stage-appropriate model: cheap for triage volume, stronger for
    extraction, where a mistake costs reviewer time downstream."""
    return AnthropicLLM(model=EXTRACT_MODEL if stage == "extract"
                        else DEFAULT_MODEL)
