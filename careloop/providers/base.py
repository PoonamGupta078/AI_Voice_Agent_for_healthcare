from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class Transcript(BaseModel):
    text: str
    words: List[str]
    confidence: float
    latency_ms: int

class LLMResult(BaseModel):
    text: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = None
    usage: Dict[str, int]
    latency_ms: int

class STTClient(ABC):
    @abstractmethod
    def transcribe(self, audio: bytes) -> Transcript:
        pass

class LLMClient(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], *, json_schema: Optional[Dict[str, Any]] = None, temperature: float = 0.0, max_tokens: int = 1000, stream: bool = False) -> LLMResult:
        pass

class TTSClient(ABC):
    @abstractmethod
    def synthesize(self, text: str, *, rate: float = 1.0, voice: str = "default") -> bytes:
        pass

class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        pass
