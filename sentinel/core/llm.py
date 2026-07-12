from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(Protocol):
    async def complete(self, messages: list[dict[str, Any]],
                        tools: list[dict[str, Any]]) -> LLMResponse: ...


class MockLLM:
    """Deterministic LLM that returns scripted responses in order."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def complete(self, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]]) -> LLMResponse:
        if self._index >= len(self._responses):
            raise RuntimeError("no more scripted responses")
        r = self._responses[self._index]
        self._index += 1
        return r
