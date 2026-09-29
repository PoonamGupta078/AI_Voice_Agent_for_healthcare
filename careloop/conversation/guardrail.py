"""
Output Guardrail (M9)
Blocks or rewrites agent replies containing diagnosis, dose advice, lab interpretation.
"""
import re
import yaml
import os
from typing import Optional, Tuple

GUARDRAILS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config", "guardrails.yaml"
)


def _load_guardrails() -> dict:
    with open(GUARDRAILS_PATH) as f:
        return yaml.safe_load(f)


class Guardrail:
    """
    Checks agent output against blocked patterns.
    Returns (is_safe, reason, fallback_message or original).
    """

    def __init__(self):
        cfg = _load_guardrails()
        self.patterns = cfg.get("blocked_patterns", [])
        self.deferral = cfg.get("deferral_message",
                                "I'll note that for your doctor.")

    def check(self, text: str) -> Tuple[bool, Optional[str], str]:
        """
        Returns (safe, reason_if_blocked, text_to_use).
        If blocked: text_to_use is the fallback.
        If safe: text_to_use is the original.
        """
        text_lower = text.lower()
        for rule in self.patterns:
            pattern = rule.get("pattern", "")
            reason = rule.get("reason", "unknown")
            fallback = rule.get("fallback", self.deferral)
            try:
                if re.search(pattern, text_lower):
                    return False, reason, fallback
            except re.error:
                continue
        return True, None, text

    def apply(self, text: str) -> str:
        """Return safe text — either original or fallback."""
        safe, reason, result = self.check(text)
        return result
