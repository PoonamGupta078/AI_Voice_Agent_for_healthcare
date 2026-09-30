"""
Unit tests for Verifier (M2)
"""
import pytest

from careloop.extraction.extractor import SlotUpdate
from careloop.extraction.verifier import Verifier
from careloop.models.data_models import SlotStatus


@pytest.fixture
def verifier():
    return Verifier(min_confidence=0.5)


def make_turns(patient_text):
    return [{"role": "user", "content": patient_text, "turn_id": "t1"}]


def test_supported_boolean_answer(verifier):
    updates = [SlotUpdate(slot_id="chest_pain", status=SlotStatus.answered,
                          value=True, confidence=0.9, quote="yes I have chest pain")]
    turns = make_turns("yes I have chest pain today")
    results = verifier.verify(updates, turns)
    assert results[0].status == "supported"


def test_unsupported_when_quote_not_in_transcript(verifier):
    updates = [SlotUpdate(slot_id="chest_pain", status=SlotStatus.answered,
                          value=True, confidence=0.9, quote="severe crushing chest pain")]
    turns = make_turns("I feel fine today")
    results = verifier.verify(updates, turns)
    assert results[0].status == "unsupported"


def test_denial_supported_with_negation(verifier):
    updates = [SlotUpdate(slot_id="chest_pain", status=SlotStatus.denied,
                          value=False, confidence=0.9, quote="no chest pain")]
    turns = make_turns("no I don't have any chest pain")
    results = verifier.verify(updates, turns)
    assert results[0].status == "supported"


def test_denial_rejected_without_negation(verifier):
    updates = [SlotUpdate(slot_id="chest_pain", status=SlotStatus.denied,
                          value=False, confidence=0.9, quote="chest is fine")]
    turns = make_turns("my chest is fine")
    results = verifier.verify(updates, turns)
    # "fine" does not contain a negation word
    assert results[0].status == "unsupported"


def test_numeric_in_quote(verifier):
    updates = [SlotUpdate(slot_id="sleep_hours", status=SlotStatus.answered,
                          value=6.0, confidence=0.9, quote="I slept 6 hours")]
    turns = make_turns("I slept 6 hours last night")
    results = verifier.verify(updates, turns)
    assert results[0].status == "supported"


def test_numeric_not_in_quote_rejected(verifier):
    updates = [SlotUpdate(slot_id="sleep_hours", status=SlotStatus.answered,
                          value=8.0, confidence=0.9, quote="I slept well")]
    turns = make_turns("I slept well last night")
    results = verifier.verify(updates, turns)
    assert results[0].status == "unsupported"


def test_low_confidence_rejected(verifier):
    updates = [SlotUpdate(slot_id="sleep_hours", status=SlotStatus.answered,
                          value=7.0, confidence=0.3, quote="slept 7 hours")]
    turns = make_turns("I slept 7 hours")
    results = verifier.verify(updates, turns)
    assert results[0].status == "low_confidence"
