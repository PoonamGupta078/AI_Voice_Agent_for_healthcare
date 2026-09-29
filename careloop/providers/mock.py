import json
from typing import Any, Dict, List, Optional
from careloop.providers.base import STTClient, LLMClient, TTSClient, EmbeddingClient, Transcript, LLMResult

class MockSTTClient(STTClient):
    def transcribe(self, audio: bytes) -> Transcript:
        return Transcript(text="mock transcript", words=["mock", "transcript"], confidence=0.99, latency_ms=100)

class MockLLMClient(LLMClient):
    def generate(self, messages: List[Dict[str, str]], *, json_schema: Optional[Dict[str, Any]] = None, temperature: float = 0.0, max_tokens: int = 1000, stream: bool = False) -> LLMResult:
        if json_schema:
            return LLMResult(json_data={"mock_key": "mock_value"}, usage={"total_tokens": 10}, latency_ms=150)
        return LLMResult(text="Mock response from LLM", usage={"total_tokens": 10}, latency_ms=150)

class MockTTSClient(TTSClient):
    def synthesize(self, text: str, *, rate: float = 1.0, voice: str = "default") -> bytes:
        return b"mock_audio_data"

class MockEmbeddingClient(EmbeddingClient):
    def embed(self, text: str) -> List[float]:
        return [0.0] * 128
