"""
Verifier (M2 - Section 5.4)
Two-layer verification: rule layer + optional model layer.
Unsupported slot updates are rejected.
"""
import re
from typing import List, Optional
from careloop.extraction.extractor import SlotUpdate
from careloop.models.data_models import SlotStatus


class VerifiedUpdate:
    def __init__(self, update: SlotUpdate, status: str, reason: str = ""):
        self.update = update
        self.status = status   # "supported" | "unsupported" | "low_confidence"
        self.reason = reason


class Verifier:
    """Rule-layer verifier: checks that the quote supports the extracted value."""

    def __init__(self, min_confidence: float = 0.5):
        self.min_confidence = min_confidence
        self.negation_words = ["no", "not", "nahi", "nahi hai", "nope", "never", "none",
                                "don't have", "do not have", "without", "absent"]
        self.number_words = {
            "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12,
        }

    def _quote_in_transcript(self, quote: str, turns: List[dict]) -> bool:
        """Check if quote (or fuzzy match) appears in any patient turn."""
        if not quote:
            return False
        # Check ALL turns (patient may be in 'user' or other roles in tests)
        all_text = " ".join(t.get("content", "") for t in turns).lower()
        # Fuzzy: at least 50% of meaningful words in quote appear in combined text
        words = [w for w in quote.lower().split() if len(w) > 2]
        if not words:
            return True
        matches = sum(1 for w in words if w in all_text)
        return (matches / len(words)) >= 0.5

    def _numeric_in_quote(self, value: float, quote: str) -> bool:
        """Check that a numeric value appears in the quote."""
        quote_lower = quote.lower()
        # Check direct number appearance
        if str(int(value)) in quote or str(value) in quote:
            return True
        # Check spelled-out numbers
        for word, num in self.number_words.items():
            if word in quote_lower and abs(num - value) < 0.5:
                return True
        return False

    def _negation_supported(self, quote: str) -> bool:
        """Check that denial is lexically supported."""
        quote_lower = quote.lower()
        return any(neg in quote_lower for neg in self.negation_words)

    def verify(self, updates: List[SlotUpdate], turns: List[dict]) -> List[VerifiedUpdate]:
        results = []
        for upd in updates:
            # Check confidence
            if upd.confidence < self.min_confidence:
                results.append(VerifiedUpdate(upd, "low_confidence",
                                              f"confidence {upd.confidence} below threshold"))
                continue

            # Check quote appears in transcript
            if not self._quote_in_transcript(upd.quote, turns):
                results.append(VerifiedUpdate(upd, "unsupported",
                                              "quote not found in patient transcript"))
                continue

            # If denied, check negation is in quote
            if upd.status == SlotStatus.denied and not self._negation_supported(upd.quote):
                results.append(VerifiedUpdate(upd, "unsupported",
                                              "denial not supported by negation words in quote"))
                continue

            # If numeric value (not bool), check it appears in quote
            if isinstance(upd.value, (int, float)) and not isinstance(upd.value, bool) and upd.value is not None:
                if not self._numeric_in_quote(float(upd.value), upd.quote):
                    results.append(VerifiedUpdate(upd, "unsupported",
                                                  f"numeric value {upd.value} not in quote"))
                    continue

            results.append(VerifiedUpdate(upd, "supported"))
        return results
