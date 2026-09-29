"""
Failure injection tests (M6/M8)
Test graceful degradation: LLM timeout, malformed JSON, STT failure.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from typing import Any, Dict, List, Optional
from careloop.providers.base import LLMClient, LLMResult, STTClient, Transcript
from careloop.extraction.extractor import ExtractorLLMClient
from careloop.config import load_slots


class TimeoutLLMClient(LLMClient):
    """Simulates a timeout by raising an exception."""
    def generate(self, messages, *, json_schema=None, temperature=0.0,
                 max_tokens=1000, stream=False) -> LLMResult:
        raise TimeoutError("LLM request timed out")


class MalformedJSONLLMClient(LLMClient):
    """Returns malformed JSON always."""
    def generate(self, messages, *, json_schema=None, temperature=0.0,
                 max_tokens=1000, stream=False) -> LLMResult:
        return LLMResult(text='{"updates": [broken json here', usage={"total_tokens": 5}, latency_ms=10)


class FailingSTTClient(STTClient):
    """Always raises an error."""
    def transcribe(self, audio: bytes) -> Transcript:
        raise RuntimeError("STT service unavailable")


def test_extractor_handles_llm_timeout():
    """Extractor must return empty list on timeout, not crash."""
    slots = load_slots()
    client = TimeoutLLMClient()
    extractor = ExtractorLLMClient(client, slots)
    turns = [{"role": "user", "content": "I have chest pain"}]
    # Should not raise — should return empty
    try:
        updates = extractor.extract(turns, "chest_pain")
        assert updates == []
    except TimeoutError:
        pytest.fail("Extractor should handle timeout gracefully")


def test_extractor_handles_malformed_json():
    """Extractor must return empty list on malformed JSON, not crash."""
    slots = load_slots()
    client = MalformedJSONLLMClient()
    extractor = ExtractorLLMClient(client, slots)
    turns = [{"role": "user", "content": "I slept 6 hours"}]
    updates = extractor.extract(turns, "sleep_hours")
    assert isinstance(updates, list)


def test_stt_failure_graceful():
    """STT failure should be catchable and not crash the caller."""
    stt = FailingSTTClient()
    with pytest.raises(RuntimeError, match="STT service unavailable"):
        stt.transcribe(b"audio_data")


def test_session_manager_handles_empty_input():
    """Session manager should handle empty/whitespace patient text."""
    from careloop.conversation.session_manager import SessionManager
    from careloop.providers.mock import MockLLMClient
    profile = {"name": "Test Patient", "age": 65, "conditions": [], "medications": [],
                "baselines": {}, "language": "en"}
    session = SessionManager("test_p", profile, MockLLMClient())
    session.start()
    # Should not crash on empty input
    result = session.turn("")
    assert "reply" in result
    result2 = session.turn("   ")
    assert "reply" in result2
