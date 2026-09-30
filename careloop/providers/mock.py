from typing import Any

from careloop.providers.base import (
    EmbeddingClient,
    LLMClient,
    LLMResult,
    STTClient,
    Transcript,
    TTSClient,
)


class MockSTTClient(STTClient):
    def transcribe(self, audio: bytes) -> Transcript:
        return Transcript(text="mock transcript", words=["mock", "transcript"], confidence=0.99, latency_ms=100)

class MockLLMClient(LLMClient):
    def generate(self, messages: list[dict[str, str]], *, json_schema: dict[str, Any] | None = None, temperature: float = 0.0, max_tokens: int = 1000, stream: bool = False) -> LLMResult:
        if json_schema:
            return LLMResult(json_data={"mock_key": "mock_value"}, usage={"total_tokens": 10}, latency_ms=150)
        
        # Make the conversational mock feel "live" by checking the planner action
        action_msg = ""
        for m in reversed(messages):
            if "PLANNER_ACTION" in m.get("content", ""):
                action_msg = m["content"].replace("PLANNER_ACTION: ", "").strip()
                break
        
        # Also check what the user just said
        user_msg = "that"
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "").strip()
                break
                
        if action_msg:
            # Create a somewhat dynamic sounding response
            if "close" in action_msg.lower():
                reply = "Thank you for checking in with me today. Have a wonderful rest of your day, and remember to call your doctor if you need anything!"
            elif "escalate" in action_msg.lower() or "red flag" in action_msg.lower():
                reply = f"I'm sorry you're experiencing that. I'm going to notify your care team so they can follow up with you. (Action: {action_msg})"
            elif "confirm" in action_msg.lower():
                reply = f"Just to confirm, you said: '{user_msg}'. Is that correct?"
            else:
                reply = f"I see. (Simulated agent focusing on: {action_msg})"
        else:
            reply = "I understand. How are you feeling otherwise?"
            
        return LLMResult(text=reply, usage={"total_tokens": 10}, latency_ms=150)

class MockTTSClient(TTSClient):
    def synthesize(self, text: str, *, rate: float = 1.0, voice: str = "default") -> bytes:
        return b"mock_audio_data"

class MockEmbeddingClient(EmbeddingClient):
    def embed(self, text: str) -> list[float]:
        return [0.0] * 128
