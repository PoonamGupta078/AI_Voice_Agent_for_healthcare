"""
Question Planner (M2 - Appendix C)
Deterministic: decides WHAT to ask. LLM only decides HOW to say it.
"""
import yaml
import os
from typing import Any, Dict, List, Optional
from careloop.models.data_models import SlotSpec, SlotStatus, PlannerAction
from careloop.state.slot_store import SlotStore


PLANNER_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "planner.yaml"
)


def _load_planner_config() -> Dict[str, Any]:
    if os.path.exists(PLANNER_CONFIG_PATH):
        with open(PLANNER_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {
        "weights": {"tier": 3.0, "relevance": 1.0, "staleness": 0.5, "change": 1.5, "unclear": 1.0, "fatigue": 2.0},
        "budgets": {"daily": 10, "weekly": 18, "short": 5},
    }


class QuestionPlanner:
    """
    Deterministic question planner.
    Selects the next slot to ask based on priority score.
    """

    def __init__(self, slot_catalogue: List[SlotSpec], session_type: str = "daily"):
        self.catalogue = {s.slot_id: s for s in slot_catalogue}
        self.session_type = session_type
        self.cfg = _load_planner_config()
        self.w = self.cfg.get("weights", {})
        budgets = self.cfg.get("budgets", {})
        self.budget = budgets.get(session_type, 10)
        self._followup_queue: List[str] = []
        self._pending_interrupt: bool = False
        self._concerns_asked: bool = False

    def set_interrupt(self) -> None:
        self._pending_interrupt = True

    def queue_followups(self, followup_ids: List[str]) -> None:
        for fid in followup_ids:
            if fid not in self._followup_queue:
                self._followup_queue.append(fid)

    def _score(self, slot: SlotSpec, store: SlotStore, trends: Optional[Dict] = None) -> float:
        state = store.get(slot.slot_id)
        tier_weights = {1: 3.0, 2: 2.0, 3: 1.0}
        score = self.w.get("tier", 3.0) * tier_weights.get(slot.tier, 1.0)
        score -= self.w.get("fatigue", 2.0) * state.asked_count
        if state.status == SlotStatus.asked_unclear and state.asked_count < 2:
            score += self.w.get("unclear", 1.0)
        if trends and slot.slot_id in trends:
            score += self.w.get("change", 1.5)
        return score

    def next_action(
        self,
        store: SlotStore,
        questions_asked: int,
        profile: Optional[Dict] = None,
        trends: Optional[Dict] = None,
    ) -> PlannerAction:
        # 1. Handle interrupt (red flag)
        if self._pending_interrupt:
            self._pending_interrupt = False
            return PlannerAction(type="escalate_message", tone_hint="reassuring")

        # 2. Follow-up queue
        while self._followup_queue:
            fid = self._followup_queue.pop(0)
            state = store.get(fid)
            if state.status in (SlotStatus.not_asked, SlotStatus.asked_unclear):
                spec = self.catalogue.get(fid)
                intent = spec.ask_intents[0] if spec and spec.ask_intents else f"ask about {fid}"
                return PlannerAction(
                    type="followup", slot_id=fid, intent=intent, tone_hint="warm",
                    must_confirm=self.catalogue.get(fid, SlotSpec(
                        slot_id=fid, domain="symptom", value_type="bool", tier=2,
                        frequency="daily", ask_intents=[]
                    )).tier == 1
                )

        # 3. Safety screen (T1 slots) - always ask first if not done
        tier1 = [s for s in self.catalogue.values() if s.tier == 1]
        for slot in tier1:
            state = store.get(slot.slot_id)
            if state.status == SlotStatus.not_asked:
                store.mark_asked(slot.slot_id)
                return PlannerAction(
                    type="ask_slot", slot_id=slot.slot_id,
                    intent=slot.ask_intents[0] if slot.ask_intents else f"ask about {slot.slot_id}",
                    tone_hint="warm", must_confirm=True
                )

        # 4. Budget check
        if questions_asked >= self.budget:
            if not self._concerns_asked:
                self._concerns_asked = True
                return PlannerAction(
                    type="ask_slot", slot_id="patient_concerns",
                    intent="ask if patient has any concerns",
                    tone_hint="warm"
                )
            return PlannerAction(type="close", tone_hint="warm")

        # 5. Concerns (mandatory at close)
        if questions_asked >= self.budget - 2 and not self._concerns_asked:
            self._concerns_asked = True
            return PlannerAction(
                type="ask_slot", slot_id="patient_concerns",
                intent="ask if patient has any concerns",
                tone_hint="warm"
            )

        # 6. Score remaining slots
        candidates = []
        for slot in self.catalogue.values():
            state = store.get(slot.slot_id)
            if state.status in (SlotStatus.answered, SlotStatus.denied, SlotStatus.declined):
                continue
            if state.status == SlotStatus.asked_unclear and state.asked_count >= 2:
                continue
            score = self._score(slot, store, trends)
            candidates.append((score, slot))

        if not candidates:
            if not self._concerns_asked:
                self._concerns_asked = True
                return PlannerAction(
                    type="ask_slot", slot_id="patient_concerns",
                    intent="ask if patient has any concerns",
                    tone_hint="warm"
                )
            return PlannerAction(type="close", tone_hint="warm")

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, best = candidates[0]
        store.mark_asked(best.slot_id)
        intent = best.ask_intents[0] if best.ask_intents else f"ask about {best.slot_id}"

        # Queue follow-ups if a positive is already in state
        state = store.get(best.slot_id)
        if state.value is True and best.followups:
            self.queue_followups(best.followups)

        return PlannerAction(
            type="ask_slot", slot_id=best.slot_id, intent=intent,
            tone_hint="warm", must_confirm=(best.tier == 1)
        )
