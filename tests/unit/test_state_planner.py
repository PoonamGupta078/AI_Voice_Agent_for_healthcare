"""
Unit tests for State Tracker and Planner (M2)
"""
import pytest

from careloop.config import load_slots
from careloop.models.data_models import SlotStatus
from careloop.planner.planner import QuestionPlanner
from careloop.state.slot_store import EvidenceStore, SlotStore


@pytest.fixture
def store():
    slots = load_slots()
    return SlotStore(slots)


@pytest.fixture
def planner():
    slots = load_slots()
    return QuestionPlanner(slots, session_type="daily")


def test_initial_state_is_not_asked(store):
    state = store.get("chest_pain")
    assert state.status == SlotStatus.not_asked


def test_update_slot_to_answered(store):
    store.update("chest_pain", SlotStatus.answered, value=False,
                 quote="no chest pain", source_turn_id="t1")
    state = store.get("chest_pain")
    assert state.status == SlotStatus.answered
    assert state.value is False


def test_no_downgrade_answered_to_unclear(store):
    store.update("chest_pain", SlotStatus.answered, value=False, quote="no chest pain")
    changed = store.update("chest_pain", SlotStatus.asked_unclear)
    assert not changed
    assert store.get("chest_pain").status == SlotStatus.answered


def test_coverage_rate_empty(store):
    assert store.coverage_rate() == 0.0


def test_coverage_rate_after_answers(store):
    required = store.get_required_slots()
    for slot in required[:3]:
        store.update(slot.slot_id, SlotStatus.answered, value=True, quote="yes")
    rate = store.coverage_rate()
    assert rate > 0.0


def test_planner_asks_t1_first(planner, store):
    """T1 safety slots must be asked before T3."""
    action = planner.next_action(store, questions_asked=0)
    assert action.slot_id in ["chest_pain", "breathlessness", "recent_fall", "severe_dizziness_fainting"]


def test_planner_no_repeat_questions(planner, store):
    """Already answered slot must not be asked again."""
    store.update("chest_pain", SlotStatus.answered, value=False, quote="no chest pain")
    store.update("breathlessness", SlotStatus.answered, value=False, quote="no breathlessness")
    store.update("recent_fall", SlotStatus.answered, value=False, quote="no falls")
    store.update("severe_dizziness_fainting", SlotStatus.answered, value=False, quote="no dizziness")

    asked_slots = set()
    for _ in range(8):
        action = planner.next_action(store, questions_asked=len(asked_slots))
        if action.type in ("ask_slot", "followup") and action.slot_id:
            assert action.slot_id not in asked_slots, f"Slot {action.slot_id} asked twice!"
            asked_slots.add(action.slot_id)
            store.update(action.slot_id, SlotStatus.answered, value=False, quote="no")


def test_planner_closes_session(planner, store):
    """After budget exhausted, planner should close."""
    # Fill all slots
    for spec in store.catalogue.values():
        store.update(spec.slot_id, SlotStatus.answered, value=False, quote="answered")
    # Planner may ask patient_concerns first (mandatory before close)
    action = planner.next_action(store, questions_asked=12)
    if action.type == "ask_slot" and action.slot_id == "patient_concerns":
        # Mark it as answered and ask again
        store.update("patient_concerns", SlotStatus.answered, value="no concerns", quote="no concerns")
        planner._concerns_asked = True
        action = planner.next_action(store, questions_asked=13)
    assert action.type == "close"


def test_evidence_store_add_and_retrieve():
    es = EvidenceStore()
    ev_id = es.add("patient_1", "session_1", "chest_pain", False,
                   "no chest pain", "patient_statement", "t1")
    assert ev_id == "E1"
    record = es.get_by_id("E1")
    assert record is not None
    assert record.slot_id == "chest_pain"
