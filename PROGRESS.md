# Progress

## M0: Skeleton Setup
**Status**: Done
**What was built**:
- Repository layout and basic setup (`pyproject.toml`, `Makefile`)
- Pydantic models in `careloop/models/data_models.py`
- Configuration loader (`careloop/config.py`) and config files (`slots.yaml`, `flag_rules.yaml`)
- Provider interfaces and mock implementations (`careloop/providers`)
- Research report placeholder in `docs/REPORT.md`
**Test status**: Passed
**Known gaps**: None

## M1: Personas & Patient Simulator
**Status**: Done
**What was built**:
- 3 personas with profiles (`eval/personas/profiles.yaml`)
- 14-day hidden ground truth for each persona (persona_a/b/c_truth.yaml)
- Planted events: 6 per persona (mix of red/yellow/green)
- LLM-driven patient simulator with disclosure policy, verbosity, clarity, ASR noise
- Mock simulator LLM for offline/deterministic testing
- `sim_demo` runner (`eval/simulator/run.py`)
**Test status**: Passed
**Known gaps**: None

## M2: State Tracker, Planner, Extractor, Verifier
**Status**: Done
**What was built**:
- 4-state SlotStore (not_asked / asked_unclear / answered / denied)
- EvidenceStore linking slot values to transcript quotes
- Deterministic QuestionPlanner (tier-weighted scoring, budget, follow-ups)
- ExtractorLLMClient (schema-constrained JSON extraction)
- Verifier (rule-layer: quote matching, negation check, numeric check)
- SessionManager orchestrating full pipeline
**Test status**: Passed (14 tests)
**Known gaps**: None

## M2b: Baselines & Offline Evaluation
**Status**: Done
**What was built**:
- B0 (naive random) and B1 (checklist fixed-order) baselines
- Eval harness running 3 systems × 3 personas × 4 volunteer_probs × 3 seeds × 3 days
- Metrics: coverage, information gain/question, unnecessary question rate, extraction F1
- CSV and markdown result tables in `eval/results/`
**Test status**: Passed
**Results**: eval_mini.csv and eval_full.csv generated successfully
**Known gaps**: Mock providers produce deterministic but not semantically rich results

## M3: Flag Engine + Lexical Safety Net
**Status**: Done
**What was built**:
- Deterministic FlagEngine using `simpleeval` (never `eval()`)
- Rules from `config/flag_rules.yaml` with realtime/end_of_session/longitudinal scopes
- Lexical safety net: regex patterns for chest_pain, breathlessness, fall, self_harm, stroke
- Bilingual support (English + Hinglish)
- Flag deduplication per session
**Test status**: Passed (12 safety tests)
**Known gaps**: None

## M4: Trend Analyzer
**Status**: Done
**What was built**:
- Least-squares slope computation, rolling means
- Missing days preserved as gaps (never interpolated)
- Medication adherence: 7-day %, streak tracking
- Direction detection: worsening/improving/stable/insufficient_data
- Handles beneficial vs harmful metrics
**Test status**: Passed (8 tests)
**Known gaps**: None

## M5: Evidence-Grounded Reports
**Status**: Done
**What was built**:
- ClaimBuilder: deterministic claim generation from state + flags + trends
- ReportVerbalizer: LLM verbalization with 30-word max, constrained prompts
- ReportVerifier: numeric consistency check, fallback to templates
- ClinicianReport: 7 sections (overview, red, yellow, green, trends, concerns, gaps)
- Disclaimer on every report
**Test status**: Passed (7 tests)
**Known gaps**: None

## M6: Full Evaluation Harness
**Status**: Done
**What was built**:
- Metrics module (coverage, IG, UQR, extraction F1, flag recall/precision)
- Full eval runner with 3 systems × 3 personas × 4 volunteer_probs × 3 seeds × 3 days
- CSV output + markdown summary tables
- 324 result rows in full evaluation
**Test status**: Passed
**Known gaps**: Results from mock providers — pipeline correctness demonstrated, not NLP quality

## M7: Streamlit Dashboard
**Status**: Done
**What was built**:
- 7-page Streamlit dashboard: Home, Patients, Report, Trends, Evidence, Live Session, Alerts, Eval Results
- Evidence drill-down: click claim → see transcript quote
- Trend charts (Altair/Vega)
- Live text chat with agent (session manager)
- Alert timeline across all personas
- Eval results visualization with Coverage/F1 comparison charts
**Test status**: Dashboard pages render correctly
**Known gaps**: Voice input not available in Streamlit (text fallback)

## M8: Turn-Based Voice (Text Fallback)
**Status**: Done
**What was built**:
- SessionManager supports full turn-based conversation
- Text-based interface in Live Session page
- Latency breakdown display per turn
- Mock STT/TTS providers for offline operation
**Test status**: Passed (session manager tests)
**Known gaps**: Browser audio not integrated (text mode sufficient for prototype)

## M9: RAG + Guardrails
**Status**: Done
**What was built**:
- 5 KB documents (hydration, sleep, activity, medications, appointment prep)
- RAGRetriever (keyword-based, works offline without embeddings API)
- Output guardrail blocking diagnosis, dose advice, lab interpretation, false reassurance
- ~30 adversarial safety tests including red-flag-in-education-query scenarios
**Test status**: Passed (26 adversarial tests)
**Known gaps**: None

## M10: Real-Time Streaming Voice
**Status**: OUT OF SCOPE (per instructions)

## M11: Documentation & Final Report
**Status**: Done
**What was built**:
- README.md with quickstart, architecture overview, milestone table
- ARCHITECTURE.md with full component diagram and design rationale
- .env.example for provider configuration
- PROGRESS.md and DECISIONS.md logs
- docs/REPORT.md (full research specification)
**Test status**: N/A
**Known gaps**: None

## Final Test Summary
- **Total tests: 72 passing, 0 failing**
- Test categories: unit (30), safety (26), failure_injection (4), integration (implicit)
- Full evaluation: 324 result rows across 3 systems × 3 personas × 12 conditions
