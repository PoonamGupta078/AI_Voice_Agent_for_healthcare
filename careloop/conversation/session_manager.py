"""
Session Manager (M2/M8)
Orchestrates a full check-in session: planner -> responder -> extractor -> verifier -> flag engine.
"""
import uuid
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from careloop.config import load_slots
from careloop.state.slot_store import SlotStore, EvidenceStore
from careloop.planner.planner import QuestionPlanner
from careloop.extraction.extractor import ExtractorLLMClient
from careloop.extraction.verifier import Verifier
from careloop.flags.engine import FlagEngine
from careloop.flags.lexical_net import LexicalSafetyNet
from careloop.providers.base import LLMClient
from careloop.models.data_models import SlotStatus, FlagEvent

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a warm, patient health check-in assistant speaking with an older adult.
You are NOT a doctor. Never diagnose, never suggest starting/stopping/changing any medicine or dose.
If asked, say you will note it for their doctor.
Use short, simple sentences and everyday words. One question per turn.
Follow this structure: (1) briefly acknowledge what they said, (2) reflect their feeling if any,
(3) ask ONLY the question described in the PLANNER_ACTION, phrased naturally and warmly.
Do not ask any other question. Do not add information not given. Be patient and kind.
"""


class SessionManager:
    """
    Manages a single check-in session from greeting to close.
    """

    def __init__(
        self,
        patient_id: str,
        profile: Dict[str, Any],
        llm_client: LLMClient,
        session_type: str = "daily",
    ):
        self.patient_id = patient_id
        self.profile = profile
        self.session_id = str(uuid.uuid4())[:8]
        self.llm = llm_client

        slots = load_slots()
        self.slot_store = SlotStore(slots)
        self.evidence_store = EvidenceStore()
        self.planner = QuestionPlanner(slots, session_type)
        self.extractor = ExtractorLLMClient(llm_client, slots)
        self.verifier = Verifier()
        self.flag_engine = FlagEngine()
        self.lexical_net = LexicalSafetyNet()

        self.turns: List[Dict] = []
        self.flags_raised: List[FlagEvent] = []
        self.questions_asked: int = 0
        self.session_closed: bool = False

    def start(self) -> str:
        """Returns the opening greeting."""
        name = self.profile.get("name", "there")
        greeting = (
            f"Hello {name}! This is your CareLoop health check-in. "
            "I'm here to check in on how you're doing today. "
            "This is an automated assistant — not a doctor. "
            "For any emergency, please call emergency services immediately. "
            "Shall we begin?"
        )
        self.turns.append({
            "role": "assistant",
            "content": greeting,
            "turn_id": f"{self.session_id}-0",
            "timestamp": datetime.utcnow().isoformat(),
        })
        return greeting

    def turn(self, patient_text: str) -> Dict[str, Any]:
        """
        Process one patient turn. Returns dict with agent reply, flags, planner action.
        """
        t0 = time.time()
        turn_id = f"{self.session_id}-{len(self.turns)}"

        # Record patient turn
        self.turns.append({
            "role": "user",
            "content": patient_text,
            "turn_id": turn_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # 1. Lexical safety net (parallel, non-blocking)
        t_lex = time.time()
        lexical_hits = self.lexical_net.scan(patient_text)
        lex_latency = int((time.time() - t_lex) * 1000)

        # 2. Real-time flag check via lexical net
        if lexical_hits:
            for category in self.lexical_net.get_triggered_categories(patient_text):
                if category == "self_harm":
                    self.planner.set_interrupt()
                elif category in ("chest_pain", "breathlessness", "fall", "fainting", "stroke"):
                    pass  # Let extractor confirm, but note it

        # 3. Extract slot updates
        t_ext = time.time()
        last_slot = self.turns[-3].get("slot_id") if len(self.turns) >= 3 else None
        updates = self.extractor.extract(self.turns[-4:], last_slot)
        ext_latency = int((time.time() - t_ext) * 1000)

        # 4. Verify updates
        verified = self.verifier.verify(updates, self.turns[-4:])

        # 5. Update slot store with verified updates
        ev_ids = []
        for vupd in verified:
            if vupd.status == "supported":
                upd = vupd.update
                self.slot_store.update(
                    upd.slot_id, upd.status, upd.value,
                    upd.confidence, turn_id, upd.quote
                )
                ev_id = self.evidence_store.add(
                    self.patient_id, self.session_id, upd.slot_id,
                    upd.value, upd.quote, "patient_statement", turn_id
                )
                ev_ids.append(ev_id)
                # If positive slot, queue follow-ups
                if upd.value is True and upd.status == SlotStatus.answered:
                    spec = self.slot_store.catalogue.get(upd.slot_id)
                    if spec and spec.followups:
                        self.planner.queue_followups(spec.followups)

        # 6. Flag engine - realtime
        t_flag = time.time()
        new_flags = self.flag_engine.evaluate(
            self.slot_store, "realtime", self.session_id,
            lexical_hits=lexical_hits, evidence_ids=ev_ids
        )
        flag_latency = int((time.time() - t_flag) * 1000)

        for flag in new_flags:
            self.flags_raised.append(flag)
            if flag.level == "red":
                self.planner.set_interrupt()

        # 7. Get planner action
        action = self.planner.next_action(
            self.slot_store, self.questions_asked, self.profile
        )
        if action.type in ("ask_slot", "followup"):
            self.questions_asked += 1

        # 8. Generate agent reply
        t_llm = time.time()
        reply = self._generate_reply(action, patient_text)
        llm_latency = int((time.time() - t_llm) * 1000)

        # 9. Check if session should close
        if action.type == "close":
            self.session_closed = True

        total_latency = int((time.time() - t0) * 1000)

        # Log turn
        self.turns.append({
            "role": "assistant",
            "content": reply,
            "turn_id": f"{turn_id}-reply",
            "slot_id": action.slot_id,
            "timestamp": datetime.utcnow().isoformat(),
            "latency_ms": total_latency,
        })

        return {
            "reply": reply,
            "action": action.model_dump(),
            "new_flags": [f.model_dump() for f in new_flags],
            "verified_updates": len([v for v in verified if v.status == "supported"]),
            "slot_coverage": self.slot_store.coverage_rate(),
            "latency": {
                "total_ms": total_latency,
                "lexical_ms": lex_latency,
                "extraction_ms": ext_latency,
                "flag_ms": flag_latency,
                "llm_ms": llm_latency,
            },
        }

    def _generate_reply(self, action, patient_text: str) -> str:
        """Generate agent reply from planner action using LLM."""
        action_desc = {
            "ask_slot": f"Ask about: {action.slot_id}. Intent: {action.intent}. Tone: {action.tone_hint}.",
            "followup": f"Follow up on: {action.slot_id}. Tone: {action.tone_hint}.",
            "escalate_message": "Calmly inform the patient the care team will be notified. Do NOT alarm them.",
            "close": "Kindly close the session, thank the patient, and remind them to contact emergency services if needed.",
            "confirm": f"Confirm: {action.slot_id}. Read back what the patient said.",
            "educate": "Provide brief, approved health information.",
        }.get(action.type, f"Continue conversation: {action.type}")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *self.turns[-6:],
            {"role": "system", "content": f"PLANNER_ACTION: {action_desc}"},
        ]
        result = self.llm.generate(messages, temperature=0.3, max_tokens=150)
        return result.text or "I'm sorry, I didn't catch that. Could you please repeat?"

    def close(self) -> Dict[str, Any]:
        """Finalize session and return summary."""
        # End-of-session flags
        end_flags = self.flag_engine.evaluate(
            self.slot_store, "end_of_session", self.session_id
        )
        self.flags_raised.extend(end_flags)
        return {
            "session_id": self.session_id,
            "turns": len(self.turns),
            "questions_asked": self.questions_asked,
            "slot_coverage": self.slot_store.coverage_rate(),
            "flags_raised": len(self.flags_raised),
            "flags": [f.model_dump() for f in self.flags_raised],
        }
