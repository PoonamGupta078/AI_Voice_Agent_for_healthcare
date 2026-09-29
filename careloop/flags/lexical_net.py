"""
Lexical Safety Net (M3)
Scans raw text for critical phrases before extraction.
Fires even when extractor fails.
"""
import re
import yaml
import os
from typing import Dict, List, Optional


LEXICAL_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config", "lexical_safety.yaml"
)


def _load_config() -> Dict:
    if os.path.exists(LEXICAL_CONFIG_PATH):
        with open(LEXICAL_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


# Hard-coded fallback phrases (also configurable via lexical_safety.yaml)
CRITICAL_PHRASES = {
    "chest_pain": [
        r"\bchest pain\b", r"\bchest tight\b", r"\bchest pressure\b",
        r"\bsina dard\b", r"\bsine mein dard\b",
    ],
    "breathlessness": [
        r"\bcannot breathe\b", r"\bcan't breathe\b", r"\bshort of breath\b",
        r"\bbreathless\b", r"\bsaans nahi\b", r"\bsaans lene mein takleef\b",
    ],
    "fall": [
        r"\bi fell\b", r"\bfall\b", r"\bgir gaya\b", r"\bgir gayi\b", r"\bgir pada\b",
        r"\bcannot get up\b", r"\bcouldn't get up\b", r"\butha nahi\b",
    ],
    "fainting": [
        r"\bfainted\b", r"\bblacked out\b", r"\bunconsciou\b", r"\bhosh kho diya\b",
        r"\bbehoshi\b",
    ],
    "self_harm": [
        r"\bwant to die\b", r"\bend my life\b", r"\bhurt myself\b",
        r"\bkill myself\b", r"\bjeena nahi\b", r"\bji nahi chahta\b",
    ],
    "stroke": [
        r"\bface drooping\b", r"\barm weakness\b", r"\bspeech slurred\b",
        r"\bsudden numbness\b", r"\bstroke\b",
    ],
}


class LexicalSafetyNet:
    """
    Scans text for critical safety phrases.
    Fires regardless of extractor state — defence in depth.
    """

    def __init__(self):
        cfg = _load_config()
        self.phrases = CRITICAL_PHRASES.copy()
        # Merge from config
        for category, patterns in cfg.get("phrases", {}).items():
            if category not in self.phrases:
                self.phrases[category] = []
            self.phrases[category].extend(patterns)

    def scan(self, text: str) -> Dict[str, bool]:
        """Returns dict of category -> True if matched."""
        results: Dict[str, bool] = {}
        text_lower = text.lower()
        for category, patterns in self.phrases.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    results[category] = True
                    break
        return results

    def is_critical(self, text: str) -> bool:
        """Returns True if any critical category is triggered."""
        matches = self.scan(text)
        return bool(matches)

    def get_triggered_categories(self, text: str) -> List[str]:
        return list(self.scan(text).keys())
