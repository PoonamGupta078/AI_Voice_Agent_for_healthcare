# CareLoop Architecture

## System Architecture

```
                              PATIENT (voice/text)
                                      |
                           +----------v-----------+
                           | VAD + Streaming STT  |  <-- MockSTTClient (offline)
                           +----------+-----------+
                                      | transcript turn t
         +----------------------------v-------------------------------+
         |                    CONVERSATION STATE                       |
         |  patient profile | last k turns | slots (4-state store)    |
         |  trend summary   | session budget | evidence store          |
         +----+-------------------+---------------------+------------+
              |                   |                     |
              v                   v                     v
    +------------------+  +-------------------+  +------------------+
    | Lexical Safety   |  | Extractor LLM     |  | Question Planner |
    | Net (regex, YAML)|  | (schema-constrained|  | (DETERMINISTIC)  |
    | No LLM involved  |  | JSON, temperature0)|  | weights from YAML|
    +--------+---------+  +--------+----------+  +--------+---------+
             |                     v                      |
             |               +------------+               |
             |               |  Verifier  |               |
             |               | (rule-layer|               |
             |               |  quote check)              |
             |               +------+-----+               |
             |                      v                     |
             |             State Update + Evidence ID     |
             |                      |                     |
             +-----------> +--------v--------+            |
                           | FLAG ENGINE     | ---> RED FLAG: interrupt + escalate
                           | (simpleeval,    |      YELLOW: end-of-session
                           |  config YAML,   |      GREEN: longitudinal
                           |  NO Python eval)|
                           +--------+--------+
                                    |
          next_slot + tone -----> +-v----------------+     +--------------------+
          from planner            | Conversation LLM |<----| RAG Retriever      |
                                  | (phrasing only)  |     | (KB/*.md, keyword) |
                                  +-------+----------+     +--------------------+
                                          |
                                    Guardrail check
                                          |
                                    Streaming TTS ----> PATIENT

    ─────────────── end of session / scheduled ────────────────────
    Slots + Flags + Trend Analyzer + Evidence Store
                     |
                     v
           Claim Builder (DETERMINISTIC)
                     |
                     v
           LLM Verbalizer (constrained, temperature 0)
                     |
                     v
           Report Verifier (numeric consistency)
                     |
                     v
           CLINICIAN DASHBOARD (7 sections + information gaps)
```

## Component Design

### Non-negotiable Safety Properties

1. **LLM never decides flags** — `FlagEngine` uses `simpleeval`, rules from `config/flag_rules.yaml`
2. **Every fact traces to evidence** — `EvidenceRecord` links slot → turn → quote
3. **Unknown ≠ Normal** — `not_asked` and `asked_unclear` are distinct states, surfaced as gaps
4. **Thresholds in config** — all numeric thresholds in `config/flag_rules.yaml`, labelled prototype/illustrative
5. **No real patient data** — synthetic personas only

### Four-State Slot Semantics

| State | Meaning | Report treatment |
|---|---|---|
| `not_asked` | Never asked | **Information gap** |
| `asked_unclear` | Asked, answer ambiguous | **Information gap** + reason |
| `answered` | Clear value with evidence | Normal reporting |
| `denied` | Explicit absence confirmed | **Pertinent negative** |
| `declined` | Patient refuses | Reported as declined |

### Planner (Deterministic)

```python
score(s) = w_tier * tier_weight(s)           # T1 safety > T2 clinical > T3 lifestyle
         + w_change * recent_change(s)        # trend-driven staleness
         + w_unclear * [state=asked_unclear]  # retry once
         - w_fatigue * asked_count_this_session(s)  # avoid repetition
```

Hard rules always override scores:
- Safety T1 slots first
- Follow-up trees fire before moving on
- Never re-ask answered/denied
- Mandatory close: patient_concerns

### Evidence-Grounded Reporting Pipeline

```
SlotStore + Flags + Trends
         ↓
   ClaimBuilder (code, deterministic)
         ↓
   LLM Verbalizer (temperature=0, max 30 words/sentence)
         ↓
   ReportVerifier (numeric consistency check)
         ↓  fails → template fallback
   ClinicianReport (7 sections + gaps + disclaimer)
```

## Model Selection Rationale

| Component | Choice (prototype) | Criteria |
|---|---|---|
| STT | Mock / Whisper (configurable) | Streaming latency, WER on older speech |
| Conversation LLM | Mock / GPT-4o / Gemini (configurable) | Low TTFT, warmth, instruction following |
| Extractor LLM | Same LLM, temperature=0 | Schema reliability, low cost |
| Verifier | Rule-based (quote matching) | No self-preference bias |
| Report Verbalizer | Same LLM, temperature=0 | Faithfulness |
| TTS | Mock / ElevenLabs (configurable) | Naturalness, streaming |
| Embeddings | Keyword matching (offline) | No API key needed for prototype |

**Rule:** small/fast for conversation → schema-reliable for extraction → deterministic for safety → different model family for judging.

## Latency Budget (Design Targets)

| Stage | Target |
|---|---|
| End-of-speech detection | 600-1000ms (tolerant) |
| STT finalization | ≤400ms |
| LLM time-to-first-token | ≤500ms |
| TTS time-to-first-byte | ≤300ms |
| **Time-to-first-audio (Mode B)** | ~1.0-1.5s |

## Provider Configuration

All providers are selected via `config/providers.yaml` and implemented as thin adapters in `careloop/providers/`. The mock providers ensure full offline operation.
