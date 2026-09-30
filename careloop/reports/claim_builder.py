"""
Evidence-Grounded Report Builder (M5)
Claim Builder -> LLM Verbalizer -> Report Verifier -> ClinicianReport
"""
from datetime import datetime
from typing import Any

from careloop.models.data_models import (
    ClinicianReport,
    FlagEvent,
    ReportClaim,
    SlotStatus,
)
from careloop.providers.base import LLMClient
from careloop.state.slot_store import EvidenceStore, SlotStore

DISCLAIMER = (
    "Automated summary from patient-reported conversations. "
    "It does not replace clinical judgment. "
    "All thresholds are prototype/illustrative."
)


class ClaimBuilder:
    """Deterministically builds ReportClaim objects from state, flags, and trends."""

    def build(
        self,
        store: SlotStore,
        flags: list[FlagEvent],
        trends: dict[str, Any],
        evidence_store: EvidenceStore,
        patient_id: str,
    ) -> list[ReportClaim]:
        claims: list[ReportClaim] = []
        claim_idx = 0

        def new_id():
            nonlocal claim_idx
            claim_idx += 1
            return f"C{claim_idx:02d}"

        # --- Red / Yellow / Green flags ---
        for flag in flags:
            section = {"red": "red", "yellow": "yellow", "green": "green"}.get(flag.level, "yellow")
            claims.append(ReportClaim(
                claim_id=new_id(),
                section=section,
                type="flag",
                facts={"flag_id": flag.flag_id, "message": flag.message,
                       "routed_to": flag.routed_to, "raised_at": str(flag.raised_at)},
                evidence_ids=flag.evidence_ids,
                severity=flag.level,
            ))

        # --- Trends ---
        for metric, trend in trends.items():
            if hasattr(trend, "direction") and trend.delta is not None:
                section = "trends"
                severity = None
                if abs(trend.delta) > 0 and trend.direction in ("worsening",):
                    severity = "yellow"
                claims.append(ReportClaim(
                    claim_id=new_id(),
                    section=section,
                    type="metric_change",
                    facts={
                        "metric": metric,
                        "baseline": trend.baseline,
                        "latest": trend.latest,
                        "delta": round(trend.delta, 2),
                        "direction": trend.direction,
                        "window_days": trend.window_days,
                    },
                    evidence_ids=trend.evidence_ids,
                    severity=severity,
                ))
            elif isinstance(trend, dict):
                # Adherence dict
                pct = trend.get("pct_7d")
                missed = trend.get("missed_7d", 0)
                if pct is not None:
                    sev = "green" if pct >= 0.9 else ("yellow" if missed >= 2 else None)
                    claims.append(ReportClaim(
                        claim_id=new_id(),
                        section="trends",
                        type="adherence",
                        facts={"pct_7d": round(pct, 2), "missed_7d": missed},
                        evidence_ids=[],
                        severity=sev,
                    ))

        # --- Patient concerns ---
        concerns_state = store.get("patient_concerns")
        if concerns_state.status == SlotStatus.answered and concerns_state.value:
            concerns = concerns_state.value if isinstance(concerns_state.value, list) \
                else [str(concerns_state.value)]
            for concern in concerns:
                ev_ids = [e.evidence_id for e in evidence_store.get_for_slot("patient_concerns")]
                claims.append(ReportClaim(
                    claim_id=new_id(),
                    section="concerns",
                    type="concern",
                    facts={"concern": concern},
                    evidence_ids=ev_ids,
                ))

        # --- Information gaps ---
        for slot_id, state in store.all_states().items():
            spec = store.catalogue.get(slot_id)
            if spec and spec.tier in (1, 2) and \
                    state.status in (SlotStatus.not_asked, SlotStatus.asked_unclear):
                reason = state.unclear_reason or (
                    "not asked" if state.status == SlotStatus.not_asked else "answer unclear"
                )
                claims.append(ReportClaim(
                    claim_id=new_id(),
                    section="gaps",
                    type="gap",
                    facts={"slot_id": slot_id, "reason": reason, "asked_count": state.asked_count},
                    evidence_ids=[],
                ))

        # --- Overview claim ---
        coverage = store.coverage_rate()
        claims.insert(0, ReportClaim(
            claim_id="C00",
            section="overview",
            type="summary",
            facts={"slot_coverage": round(coverage, 2), "flags_total": len(flags)},
            evidence_ids=[],
        ))

        return claims


class ReportVerbalizer:
    """Converts ReportClaims into human-readable sentences using LLM."""

    FALLBACK_TEMPLATES = {
        "flag": "Flag {flag_id}: {message}",
        "metric_change": "Metric {metric}: changed from {baseline} to {latest} (delta {delta}).",
        "adherence": "Medication adherence: {pct_7d:.0%} over 7 days; {missed_7d} missed doses.",
        "concern": "Patient concern: {concern}",
        "gap": "Information gap: {slot_id} was {reason}.",
        "summary": "Session coverage: {slot_coverage:.0%} of required slots. Flags: {flags_total}.",
    }

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def verbalize(self, claims: list[ReportClaim]) -> dict[str, str]:
        sentences: dict[str, str] = {}
        for claim in claims:
            try:
                sentence = self._verbalize_one(claim)
            except Exception:
                sentence = self._fallback(claim)
            sentences[claim.claim_id] = sentence
        return sentences

    def _verbalize_one(self, claim: ReportClaim) -> str:
        prompt = (
            "Write ONE concise sentence for a clinician based ONLY on these facts. "
            "Do not diagnose, speculate, or recommend treatment. Neutral clinical tone. Max 30 words.\n"
            f"Type: {claim.type}\nSection: {claim.section}\nFacts: {claim.facts}"
        )
        result = self.llm.generate(
            [{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=80
        )
        text = (result.text or "").strip()
        if not text:
            return self._fallback(claim)
        return text

    def _fallback(self, claim: ReportClaim) -> str:
        template = self.FALLBACK_TEMPLATES.get(claim.type, "Claim {claim_id}: {facts}")
        try:
            return template.format(claim_id=claim.claim_id, **claim.facts)
        except Exception:
            return f"Claim {claim.claim_id}: see evidence."


class ReportVerifier:
    """Verifies that sentences are consistent with their claim facts."""

    def verify(self, claims: list[ReportClaim], sentences: dict[str, str]) -> dict[str, Any]:
        failures = []
        for claim in claims:
            sentence = sentences.get(claim.claim_id, "")
            # Numeric consistency: every number in facts must appear in sentence
            for key, val in claim.facts.items():
                if isinstance(val, float) and val != 0.0:
                    val_str = f"{val:.1f}" if val != int(val) else str(int(val))
                    if val_str not in sentence and str(val) not in sentence:
                        # Use fallback if numeric mismatch
                        failures.append({
                            "claim_id": claim.claim_id,
                            "reason": f"Numeric {val} for {key} not in sentence"
                        })
        passed = len(failures) == 0
        return {"passed": passed, "failures": failures, "fallbacks_used": len(failures)}


class ReportBuilder:
    """Orchestrates the full report building pipeline."""

    def __init__(self, llm_client: LLMClient):
        self.claim_builder = ClaimBuilder()
        self.verbalizer = ReportVerbalizer(llm_client)
        self.verifier = ReportVerifier()

    def build(
        self,
        store: SlotStore,
        flags: list[FlagEvent],
        trends: dict[str, Any],
        evidence_store: EvidenceStore,
        patient_id: str,
        period: tuple,
    ) -> ClinicianReport:
        # 1. Build claims
        claims = self.claim_builder.build(store, flags, trends, evidence_store, patient_id)

        # 2. Verbalize
        sentences = self.verbalizer.verbalize(claims)

        # 3. Verify — replace failed sentences with fallback
        verification = self.verifier.verify(claims, sentences)
        if not verification["passed"]:
            for failure in verification["failures"]:
                cid = failure["claim_id"]
                claim = next((c for c in claims if c.claim_id == cid), None)
                if claim:
                    sentences[cid] = self.verbalizer._fallback(claim)

        # 4. Organize into sections
        sections: dict[str, list[dict]] = {
            "overview": [], "red": [], "yellow": [], "green": [],
            "trends": [], "concerns": [], "followup": [], "gaps": [],
        }
        for claim in claims:
            sec = claim.section
            if sec in sections:
                sections[sec].append({
                    "claim_id": claim.claim_id,
                    "sentence": sentences.get(claim.claim_id, ""),
                    "evidence_ids": claim.evidence_ids,
                    "severity": claim.severity,
                })

        return ClinicianReport(
            patient_id=patient_id,
            period=period,
            sections=sections,
            generated_at=datetime.utcnow(),
            verification=verification,
            disclaimer=DISCLAIMER,
        )
