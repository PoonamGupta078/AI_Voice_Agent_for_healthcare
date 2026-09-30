from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel


class LLMErrorKind(str, Enum):
    per_minute_limit = "per_minute_limit"   # 429 TPM/RPM — retry with backoff
    daily_quota      = "daily_quota"         # 429 RPD     — do NOT retry, use fallback
    server_error     = "server_error"        # 503         — retry with backoff
    unknown          = "unknown"


class LLMQuotaError(Exception):
    """Raised by LLMClient when a rate-limit or quota error is received."""
    def __init__(self, kind: LLMErrorKind, message: str, retry_after_s: int = 0):
        super().__init__(message)
        self.kind = kind
        self.retry_after_s = retry_after_s


class Transcript(BaseModel):
    text: str
    words: list[str]
    confidence: float
    latency_ms: int


class LLMResult(BaseModel):
    text: str | None = None
    json_data: dict[str, Any] | None = None
    usage: dict[str, int]
    latency_ms: int


class STTClient(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes) -> Transcript:
        pass


class LLMClient(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        stream: bool = False,
    ) -> LLMResult:
        pass


class TTSClient(ABC):
    @abstractmethod
    def synthesize(self, text: str, *, rate: float = 1.0, voice: str = "default") -> bytes:
        pass


class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass
