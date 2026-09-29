# CareLoop 🩺

> **AI Voice Agent for Older Adults** — Stateful · Evidence-Grounded · Safety-Constrained

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org)
![Status: Research Prototype](https://img.shields.io/badge/status-research%20prototype-orange)
![Data: Synthetic Only](https://img.shields.io/badge/data-synthetic%20only-green)

CareLoop is a **research prototype** of an AI-powered voice agent for daily health check-ins with older adults (55+). It demonstrates a **stateful, evidence-grounded, safety-constrained** approach to structured patient data collection and clinician reporting.

> ⚠️ **This is a research prototype using synthetic data only. All clinical thresholds are illustrative, not medical recommendations. Not for real clinical use.**

---

## Quickstart (Text-Only, No API Keys Needed)

### 1. Clone and Install

```bash
git clone <repo_url>
cd careloop
pip install -e ".[dev]"
```

### 2. Run Tests

```bash
# Windows (set PYTHONPATH first)
$env:PYTHONPATH="C:\path\to\careloop"
pytest tests/
```

### 3. Run the Dashboard

```bash
$env:PYTHONPATH="C:\path\to\careloop"
streamlit run dashboard/app.py
```

### 4. Run Mini Evaluation (M2b gate)

```bash
$env:PYTHONPATH="C:\path\to\careloop"
python -m eval.run_eval --mini
```

### 5. Run Full Evaluation

```bash
python -m eval.run_eval
```

### 6. Run Sim Demo (M1)

```bash
python -m eval.simulator.run
```

---

## Architecture Overview

```
Patient Voice → STT → Lexical Safety Net
                         ↓
                    State Tracker (4-state slots)
                         ↓
                 Extractor → Verifier
                         ↓
               Deterministic Flag Engine → Escalation
                         ↓
              Question Planner → Conversation LLM → TTS → Patient
                         ↓
                  Trend Analyzer → Claim Builder
                         ↓
              LLM Verbalizer → Report Verifier
                         ↓
                  Clinician Dashboard
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full component diagram.

---

## Key Features

| Feature | Implementation |
|---|---|
| **4-state slot tracker** | `not_asked / asked_unclear / answered / denied` |
| **Deterministic flag engine** | `simpleeval` — never `eval()` — rules from config YAML |
| **Evidence-grounded reports** | Every sentence cites a transcript evidence ID |
| **Extract-then-verify** | Quote must appear in transcript; numerics must be in quote |
| **Lexical safety net** | Fires even when LLM/extractor fails — defence in depth |
| **Mock providers** | Full pipeline runs offline, deterministically, no API keys |
| **Adversarial test suite** | ~30 prompts testing guardrail + red-flag detection |

---

## Using Real AI Providers

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
# Edit .env with your keys
```

Then update `config/providers.yaml` to use `openai` or `google` instead of `mock`.

---

## Project Structure

```
careloop/
  careloop/           # Main package
    models/           # Pydantic data models
    state/            # Slot store + evidence store
    planner/          # Deterministic question planner
    extraction/       # Extractor + verifier
    flags/            # Flag engine + lexical net
    trends/           # Trend analyzer
    reports/          # Claim builder + verbalizer + verifier
    conversation/     # Session manager + guardrail
    rag/              # Knowledge base + retriever
  config/             # All YAML configuration
  eval/               # Personas, simulator, metrics, baselines
  dashboard/          # Streamlit pages
  tests/              # Unit, safety, integration, failure injection
  docs/REPORT.md      # Full research report and specification
```

---

## Milestones Completed

| Milestone | Status |
|-----------|--------|
| M0 Skeleton | ✅ Done |
| M1 Personas + Simulator | ✅ Done |
| M2 State + Planner + Extractor + Verifier | ✅ Done |
| M2b Baselines + Eval Mini | ✅ Done |
| M3 Flag Engine + Lexical Net | ✅ Done |
| M4 Trend Analyzer | ✅ Done |
| M5 Evidence-Grounded Reports | ✅ Done |
| M6 Full Eval Harness | ✅ Done |
| M7 Streamlit Dashboard | ✅ Done |
| M8 Turn-Based Voice (text fallback) | ✅ Done (text mode) |
| M9 RAG + Guardrails | ✅ Done |
| M10 Real-time streaming | ❌ Out of scope |
| M11 Docs | ✅ Done |

---

## Limitations

- Results from mock providers demonstrate pipeline correctness, not real NLP quality
- Thresholds are prototype/illustrative — must be validated by a care team
- Voice mode uses text fallback in the dashboard (no browser audio API in current Streamlit version)
- Evaluation uses synthetic patient simulator, not real older adults
- 3 personas is a small set — results show design effects, not statistical significance

---

## Demo Script (5 minutes)

1. Show pipeline diagram (ARCHITECTURE.md)
2. Open dashboard → **Alerts** page → show RED flag for Persona C Day 12
3. Open **Report** page → Persona C Day 12 → see red/yellow/green + evidence drill-down
4. Open **Trends** page → show weight gain trend
5. Open **Live Session** → text chat with the agent → trigger red flag
6. Open **Eval Results** → run mini eval → show Coverage/F1 comparison table

---

## Citations (from docs/REPORT.md Appendix H)

Verify all citations against original papers before use in submissions.
See `docs/REPORT.md` for the complete reference list.

---

*Research prototype. Synthetic data only. Not for clinical use.*
