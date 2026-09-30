"""
Unit tests for Report Builder and Verifier (M5)
"""
from datetime import date, datetime

import pytest

from careloop.config import load_slots
from careloop.models.data_models import FlagEvent, SlotStatus
from careloop.providers.mock import MockLLMClient
from careloop.reports.claim_builder import (
    ClaimBuilder,
    ReportBuilder,
    ReportVerifier,
)
from careloop.state.slot_store import EvidenceStore, SlotStore


@pytest.fixture
def store():
    s = SlotStore(load_slots())
    s.update("chest_pain", SlotStatus.denied, value=False, quote="no chest pain")
    s.update("sleep_hours", SlotStatus.answered, value=5.0, quote="5 hours sleep")
    s.update("patient_concerns", SlotStatus.answered,
             value=["my ankles look bigger"], quote="my ankles look bigger")
    return s


@pytest.fixture
def evidence_store(store):
    es = EvidenceStore()
    es.add("p1", "s1", "patient_concerns", ["my ankles look bigger"],
           "my ankles look bigger", "patient_statement", "t5")
    return es


@pytest.fixture
def flags():
    return [FlagEvent(
        flag_id="DEMO_RF_03",
        level="red",
        message="Urgent: breathless lying flat",
        evidence_ids=["E1"],
        rule_version="0.1",
        rule_source="prototype/illustrative",
        scope="realtime",
        routed_to="physician",
        raised_at=datetime.utcnow(),
    )]


@pytest.fixture
def trends():
    from datetime import date

    from careloop.trends.analyzer import TrendAnalyzer
    analyzer = TrendAnalyzer()
    series = [(date(2026, 9, i + 1), 70.0 + i * 0.5) for i in range(5)]
    tf = analyzer.compute_metric("weight_kg", series, baseline=70.0)
    return {"weight_kg": tf, "med_adherence": {"pct_7d": 0.85, "missed_7d": 1}}


def test_claim_builder_creates_claims(store, flags, trends, evidence_store):
    builder = ClaimBuilder()
    claims = builder.build(store, flags, trends, evidence_store, "p1")
    assert len(claims) > 0
    sections = {c.section for c in claims}
    assert "red" in sections


def test_red_flag_in_report(store, flags, trends, evidence_store):
    builder = ClaimBuilder()
    claims = builder.build(store, flags, trends, evidence_store, "p1")
    red_claims = [c for c in claims if c.section == "red"]
    assert len(red_claims) == 1
    assert red_claims[0].severity == "red"


def test_patient_concerns_in_report(store, flags, trends, evidence_store):
    builder = ClaimBuilder()
    claims = builder.build(store, flags, trends, evidence_store, "p1")
    concern_claims = [c for c in claims if c.section == "concerns"]
    assert len(concern_claims) >= 1


def test_information_gaps_listed(store, flags, trends, evidence_store):
    builder = ClaimBuilder()
    claims = builder.build(store, flags, trends, evidence_store, "p1")
    gap_claims = [c for c in claims if c.section == "gaps"]
    # Several slots were never asked
    assert len(gap_claims) > 0


def test_report_verifier_catches_numeric_error():
    """Verifier should flag if a number in facts doesn't appear in the sentence."""
    from careloop.models.data_models import ReportClaim
    verifier = ReportVerifier()
    claim = ReportClaim(
        claim_id="C01",
        section="trends",
        type="metric_change",
        facts={"metric": "weight_kg", "baseline": 70.0, "latest": 72.5, "delta": 2.5,
               "direction": "worsening", "window_days": 7},
        evidence_ids=[],
    )
    sentences = {"C01": "Weight has increased significantly."}  # Missing 72.5
    result = verifier.verify([claim], sentences)
    assert not result["passed"]
    assert len(result["failures"]) > 0


def test_report_verifier_passes_correct_sentence():
    from careloop.models.data_models import ReportClaim
    verifier = ReportVerifier()
    claim = ReportClaim(
        claim_id="C01",
        section="trends",
        type="metric_change",
        facts={"metric": "weight_kg", "baseline": 70.0, "latest": 72.5, "delta": 2.5,
               "direction": "worsening", "window_days": 7},
        evidence_ids=[],
    )
    sentences = {"C01": "Weight increased from 70.0 kg to 72.5 kg, a delta of 2.5 kg."}
    result = verifier.verify([claim], sentences)
    assert result["passed"]


def test_full_report_builder(store, flags, trends, evidence_store):
    llm = MockLLMClient()
    builder = ReportBuilder(llm)
    report = builder.build(
        store, flags, trends, evidence_store, "p1",
        (date(2026, 9, 1), date(2026, 9, 14))
    )
    assert report.patient_id == "p1"
    assert "red" in report.sections
    assert len(report.sections["red"]) > 0
    assert report.disclaimer != ""
