"""
Session State and Slot Store (M2)
Four-state slot tracking: not_asked / asked_unclear / answered / denied / declined
"""
from datetime import datetime
from typing import Any

from careloop.models.data_models import EvidenceRecord, SlotSpec, SlotState, SlotStatus


class SlotStore:
    """Manages the four-state slot store for a session."""

    def __init__(self, slot_catalogue: list[SlotSpec]):
        self.catalogue: dict[str, SlotSpec] = {s.slot_id: s for s in slot_catalogue}
        self.states: dict[str, SlotState] = {
            s.slot_id: SlotState(slot_id=s.slot_id) for s in slot_catalogue
        }

    def get(self, slot_id: str) -> SlotState:
        return self.states.get(slot_id, SlotState(slot_id=slot_id))

    def update(self, slot_id: str, status: SlotStatus, value: Any = None,
               confidence: float = 1.0, source_turn_id: str | None = None,
               quote: str | None = None, unclear_reason: str | None = None) -> bool:
        """Returns True if state was actually updated."""
        if slot_id not in self.states:
            self.states[slot_id] = SlotState(slot_id=slot_id)
        current = self.states[slot_id]

        # Never downgrade answered/denied to unclear unless asked
        if current.status in (SlotStatus.answered, SlotStatus.denied) and \
           status == SlotStatus.asked_unclear:
            return False

        self.states[slot_id] = SlotState(
            slot_id=slot_id,
            status=status,
            value=value,
            confidence=confidence,
            source_turn_id=source_turn_id,
            quote=quote,
            asked_count=current.asked_count,
            updated_at=datetime.utcnow(),
            unclear_reason=unclear_reason,
        )
        return True

    def mark_asked(self, slot_id: str) -> None:
        if slot_id in self.states:
            self.states[slot_id].asked_count += 1
            if self.states[slot_id].status == SlotStatus.not_asked:
                self.states[slot_id].status = SlotStatus.asked_unclear

    def get_required_slots(self) -> list[SlotSpec]:
        return [s for s in self.catalogue.values() if s.frequency != "conditional"]

    def get_unanswered_required(self) -> list[SlotSpec]:
        return [
            s for s in self.get_required_slots()
            if self.states[s.slot_id].status in (SlotStatus.not_asked, SlotStatus.asked_unclear)
        ]

    def coverage_rate(self) -> float:
        required = self.get_required_slots()
        if not required:
            return 1.0
        answered = sum(
            1 for s in required
            if self.states[s.slot_id].status in (SlotStatus.answered, SlotStatus.denied)
        )
        return answered / len(required)

    def all_states(self) -> dict[str, SlotState]:
        return dict(self.states)


class EvidenceStore:
    """Stores evidence records linking slot values to transcript turns."""

    def __init__(self):
        self.records: list[EvidenceRecord] = []

    def add(self, patient_id: str, session_id: str, slot_id: str, value: Any,
            quote: str | None, source_type: str, turn_id: str | None = None) -> str:
        ev_id = f"E{len(self.records) + 1}"
        self.records.append(EvidenceRecord(
            evidence_id=ev_id,
            patient_id=patient_id,
            session_id=session_id,
            turn_id=turn_id,
            slot_id=slot_id,
            value=value,
            quote=quote,
            source_type=source_type,
            timestamp=datetime.utcnow(),
        ))
        return ev_id

    def get_by_id(self, ev_id: str) -> EvidenceRecord | None:
        return next((r for r in self.records if r.evidence_id == ev_id), None)

    def get_for_slot(self, slot_id: str) -> list[EvidenceRecord]:
        return [r for r in self.records if r.slot_id == slot_id]
