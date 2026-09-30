"""
Mock LLM Client that returns scripted responses for simulator testing (deterministic/offline).
"""
from typing import Any

from careloop.providers.base import LLMClient, LLMResult

MOCK_PATIENT_RESPONSES = [
    "Yes, I took my morning tablet.",
    "No chest pain today.",
    "I slept about 6 hours last night.",
    "I walked for about 20 minutes.",
    "I drank about 5 glasses of water.",
    "My mood is okay, maybe 6 out of 10.",
    "No, I don't have any concerns for the doctor.",
]


class MockSimulatorLLMClient(LLMClient):
    """Returns deterministic scripted patient responses for offline testing."""

    def __init__(self, seed: int = 42):
        import random
        self.rng = random.Random(seed)
        self._call_count = 0

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        stream: bool = False,
    ) -> LLMResult:
        self._call_count += 1
        if json_schema:
            # Return a mock extraction result
            return LLMResult(
                json_data={"updates": []},
                usage={"total_tokens": 20},
                latency_ms=10,
            )
        idx = self._call_count % len(MOCK_PATIENT_RESPONSES)
        return LLMResult(
            text=MOCK_PATIENT_RESPONSES[idx],
            usage={"total_tokens": 20},
            latency_ms=10,
        )
