from __future__ import annotations
import json
from typing import Any

import httpx

from sentinel.core.llm import LLMProvider, LLMResponse


class OpenAIProvider:
    """LLM provider using raw httpx calls to the OpenAI chat completions API."""

    def __init__(self, api_key: str, model: str,
                 base_url: str | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url or "https://api.openai.com"
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url, timeout=60.0)

    async def complete(self, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]]) -> LLMResponse:
        resp = await self._client.post(
            "/v1/chat/completions",
            json={"model": self._model, "messages": messages},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"openai api error {resp.status_code}: {resp.text}")
        data = resp.json()
        msg = data["choices"][0]["message"]
        text = msg.get("content") or ""
        tool_calls: list[dict[str, Any]] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc["function"]
            tool_calls.append({
                "tool": fn["name"],
                "args": json.loads(fn["arguments"]),
            })
        return LLMResponse(text=text, tool_calls=tool_calls)


class AnthropicProvider:
    """LLM provider using raw httpx calls to the Anthropic messages API."""

    def __init__(self, api_key: str, model: str,
                 base_url: str | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url or "https://api.anthropic.com"
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url, timeout=60.0)

    async def complete(self, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]]) -> LLMResponse:
        resp = await self._client.post(
            "/v1/messages",
            json={"model": self._model, "messages": messages,
                  "max_tokens": 4096},
            headers={"x-api-key": self._api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"anthropic api error {resp.status_code}: {resp.text}")
        data = resp.json()
        text = ""
        tool_calls: list[dict[str, Any]] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "tool": block["name"],
                    "args": block.get("input", {}),
                })
        return LLMResponse(text=text, tool_calls=tool_calls)
