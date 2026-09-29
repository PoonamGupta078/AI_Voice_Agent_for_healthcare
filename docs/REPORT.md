# CareLoop: A Stateful, Evidence-Grounded, Safety-Constrained Voice Agent for Longitudinal Health Check-ins with Older Adults

**Version:** 1.0 | **Date:** 29 Sept 2026
**Author / Team:** Antigravity

---

## Abstract

Older adults (55+) often struggle with typing and complex app navigation, so routine health check-ins collected through apps are incomplete, while clinicians lack concise, trustworthy information between visits. Voice conversation is a natural interface, but a naive "speech-to-text plus LLM" agent has three weaknesses: it only learns what the patient volunteers, it can hallucinate or silently assume facts, and it cannot be audited for safety. We present CareLoop, a voice agent for daily and weekly health and wellness check-ins built as a **stateful, evidence-grounded, safety-constrained** system rather than a single LLM. A slot-based patient state distinguishes *not asked*, *asked but unclear*, *answered* and *denied*; a question planner decides what must be asked next while the LLM only phrases it warmly; an extractor with a verifier turns speech into structured, transcript-supported facts; a deterministic, configurable rule engine raises red and yellow flags in real time; a statistical trend analyzer tracks change over days; and an evidence-grounded report builder produces a one-page clinician report in which every claim links to its evidence. We propose a controlled evaluation on synthetic older-adult personas with planted clinical events, comparing the full system against unconstrained LLM baselines and component ablations on slot coverage, extraction F1, unsupported-claim rate, flag recall and precision, latency, questions per session, empathy and clinician-rated usefulness. The system supports the clinician and does not replace clinical judgment.

*(Note: This is a placeholder report. Results and metrics will be updated upon completion of the evaluation phase.)*

---

## 1. Introduction

### 1.1 Problem
The assignment asks for a voice agent for adults 55+ that runs check-ins (medication adherence and side effects; symptoms, wellbeing, sleep, activity, nutrition, hydration), documents concerns, asks follow-ups, gives approved education, helps prepare for appointments, identifies predefined red/yellow flags, escalates to the care team, and converts everything into concise, actionable clinician reports. Primary focus: conversational quality, empathy, low latency, reliability, and usefulness to clinicians.

### 1.2 Gap
- **Volunteered-information bias.** Patients report what they think matters. Absence of a mention is not absence of a symptom, yet a free-form LLM cannot tell the two apart.
- **Hallucination and silent assumption.** A generated report can contain facts the patient never said.
- **Un-auditable safety.** If the same model converses, judges severity and writes the report, there is no independent safety layer.
- **Transcript overload.** Raw transcripts do not help a time-pressed clinician.

### 1.3 Research question and hypotheses
**RQ:** Can explicit patient-state tracking and planner-driven questioning improve required-information coverage and evidence-grounded reporting, while maintaining conversational quality and low latency, in longitudinal voice health check-ins for older adults, compared with an unconstrained conversational LLM?

- **H1 (completeness):** A state-aware planner achieves higher required-slot coverage and extraction recall than an unconstrained LLM, at a comparable or lower number of questions per session, with higher information gain per question and fewer unnecessary (repeated) questions.
- **H2 (faithfulness):** Extraction verification plus evidence-grounded report building lowers the unsupported-claim rate in clinician reports.
- **H3 (safety):** A deterministic flag engine gives higher and more consistent flag recall and precision, and earlier time-to-flag, than delegating flag decisions to the LLM.
- **H4 (usability):** The added machinery does not degrade latency beyond the target budget or perceived empathy.

### 1.4 Contributions
1. A **four-state slot representation** (not_asked / asked_unclear / answered / denied) that separates "never asked" from "asked and denied".
2. A **question planner** that decides *what* to ask (priority, staleness, recent change, fatigue budget) while the LLM decides only *how* to say it.
3. An **extract-then-verify** pipeline that marks unsupported values as unknown.
4. A **configurable deterministic flag engine** with a real-time path (mid-call escalation) and an end-of-call path (trend-based flags).
5. **Evidence-grounded clinician reporting**: claims are built from structured evidence, verbalized by an LLM under constraints, then verified.
6. A **reproducible evaluation harness** with synthetic personas, planted events, a disclosure-controlled patient simulator, baselines and ablations.

### 1.5 Scope and non-goals
In scope: text-first core pipeline, turn-based voice demo, clinician dashboard, evaluation harness. Stretch: real-time streaming voice with barge-in. **Out of scope:** diagnosis, treatment advice, real EHR integration, real patient data, regulatory approval. Future work: vision (photo attach, meter-display OCR), prosody as a soft signal, multilingual expansion, FHIR integration.

---

*(Full sections 2-9 from the specification will be included and updated here)*
