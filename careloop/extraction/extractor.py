"""
Extractor (M2 - Prompt D.2)
Extracts slot values from transcript turns using LLM with JSON schema.
"""
import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from careloop.models.data_models import SlotSpec, SlotStatus
from careloop.providers.base import LLMClient


class SlotUpdate(BaseModel):
    slot_id: str
    status: SlotStatus
    value: Optional[Any] = None
    confidence: float = 1.0
    quote: str = ""


class ExtractorLLMClient:
    """Wraps LLMClient with extraction-specific logic."""

    def __init__(self, llm_client: LLMClient, slot_catalogue: List[SlotSpec]):
        self.llm = llm_client
        self.catalogue = {s.slot_id: s for s in slot_catalogue}

    def _build_prompt(self, turns: List[Dict], last_question_slot: Optional[str]) -> List[Dict]:
        slot_subset = list(self.catalogue.values())
        slots_desc = "\n".join(
            f"  - {s.slot_id} ({s.value_type}): {s.ask_intents[0] if s.ask_intents else 'n/a'}"
            for s in slot_subset
        )
        turns_str = "\n".join(
            f"[{t.get('role','?').upper()} turn {t.get('turn_id','')}]: {t.get('content','')}"
            for t in turns[-4:]
        )
        system = (
            "Extract health information from the patient's latest turn(s) into JSON.\n"
            "Rules: (1) Only extract what the patient EXPLICITLY SAID. (2) Include exact 'quote' from patient text. "
            "(3) status: 'denied' only if patient clearly says symptom is absent; 'asked_unclear' if ambiguous; "
            "'answered' if clear. (4) NEVER infer or assume normal. (5) Numbers must appear in the quote. "
            "(6) If nothing relevant, return {\"updates\": []}.\n"
            f"SLOT CATALOGUE:\n{slots_desc}\n"
            f"LAST QUESTION SLOT: {last_question_slot}\n"
            "Return JSON: {\"updates\": [{\"slot_id\": ..., \"status\": ..., \"value\": ..., "
            "\"confidence\": 0-1, \"quote\": \"exact patient words\"}]}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"TURNS:\n{turns_str}"},
        ]

    def extract(self, turns: List[Dict], last_question_slot: Optional[str]) -> List[SlotUpdate]:
        messages = self._build_prompt(turns, last_question_slot)
        try:
            result = self.llm.generate(messages, temperature=0.0, max_tokens=600)
            text = result.text or ""
            # Try to parse JSON from the response
            match = re.search(r'\{.*"updates".*\}', text, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                data = json.loads(text) if text.strip().startswith("{") else {"updates": []}

            updates = []
            for item in data.get("updates", []):
                try:
                    updates.append(SlotUpdate(
                        slot_id=item["slot_id"],
                        status=SlotStatus(item.get("status", "answered")),
                        value=item.get("value"),
                        confidence=float(item.get("confidence", 1.0)),
                        quote=item.get("quote", ""),
                    ))
                except Exception:
                    continue
            return updates
        except Exception:
            return []
