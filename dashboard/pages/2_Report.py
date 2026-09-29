"""
Page 2: Clinician Report with Red/Yellow/Green/Gaps sections and evidence drill-down
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import yaml
from datetime import date, datetime
from careloop.config import load_slots
from careloop.state.slot_store import SlotStore, EvidenceStore
from careloop.flags.engine import FlagEngine
from careloop.flags.lexical_net import LexicalSafetyNet
from careloop.trends.analyzer import TrendAnalyzer
from careloop.reports.claim_builder import ReportBuilder
from careloop.providers.mock import MockLLMClient
from careloop.models.data_models import SlotStatus, FlagEvent

st.set_page_config(page_title="Clinician Report — CareLoop", page_icon="📋", layout="wide")
st.title("📋 Clinician Report")
st.caption("All thresholds are prototype/illustrative. This does not replace clinical judgment.")


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

# Persona selector
profiles_raw = load_yaml(os.path.join(BASE, "profiles.yaml"))
persona_options = {p["name"]: pid for pid, p in profiles_raw.items()}
selected_name = st.sidebar.selectbox("Select Patient", list(persona_options.keys()))
selected_pid = persona_options[selected_name]
profile = profiles_raw[selected_pid]

truth_path = os.path.join(BASE, f"{selected_pid}_truth.yaml")
truth = load_yaml(truth_path)

day_options = list(range(1, len(truth["days"]) + 1))
selected_day = st.sidebar.selectbox("Select Day", day_options, index=len(day_options) - 1)
day_data = truth["days"][selected_day - 1]
fact_sheet = day_data["slots"]
planted_events = day_data.get("planted_events", [])

st.sidebar.markdown("---")
st.sidebar.info(f"📅 Appointment: Day {profile.get('upcoming_appointment_day', 'N/A')}")

# Build a synthetic session state from the fact sheet
slots = load_slots()
store = SlotStore(slots)
evidence_store = EvidenceStore()

# Populate store from fact sheet
for slot_id, val in fact_sheet.items():
    spec = store.catalogue.get(slot_id)
    if spec is None:
        continue
    if isinstance(val, bool):
        status = SlotStatus.answered if val else SlotStatus.denied
    elif val is not None:
        status = SlotStatus.answered
    else:
        continue
    quote = f"Patient reported: {val}"
    store.update(slot_id, status, val, 0.9, "t1", quote)
    ev_id = evidence_store.add(selected_pid, f"day{selected_day}", slot_id, val, quote, "patient_statement", "t1")

# Run flag engine
engine = FlagEngine()
flags_rt = engine.evaluate(store, "realtime", f"day{selected_day}")
flags_eos = engine.evaluate(store, "end_of_session", f"day{selected_day}")
all_flags = flags_rt + flags_eos

# Trends (simplified from history up to this day)
analyzer = TrendAnalyzer()
history = []
for i, d in enumerate(truth["days"][:selected_day]):
    history.append({"date": date(2026, 9, i + 1), "slots": d["slots"]})
trends = analyzer.compute_all(history, profile.get("baselines", {}))

# Build report
llm = MockLLMClient()
builder = ReportBuilder(llm)
report = builder.build(
    store, all_flags, trends, evidence_store, selected_pid,
    (date(2026, 9, 1), date(2026, 9, selected_day))
)

# --- Render Report ---
st.markdown(f"## Report: **{profile['name']}** — Day {selected_day}")
st.markdown(f"*Generated at: {report.generated_at.strftime('%Y-%m-%d %H:%M')} UTC*")
st.markdown(f"**Verification:** {'✅ Passed' if report.verification.get('passed') else f'⚠️ {report.verification.get(\"fallbacks_used\", 0)} fallback(s) used'}")

# Overview
if report.sections.get("overview"):
    with st.expander("📊 Patient Overview", expanded=True):
        for item in report.sections["overview"]:
            st.markdown(f"- {item['sentence']}")

# Red Flags
if report.sections.get("red"):
    st.markdown("### 🔴 Red Flags")
    for item in report.sections["red"]:
        with st.error(item["sentence"]):
            pass
        if item.get("evidence_ids"):
            with st.expander(f"📎 Evidence: {', '.join(item['evidence_ids'])}"):
                for eid in item["evidence_ids"]:
                    rec = evidence_store.get_by_id(eid)
                    if rec:
                        st.code(f'[{rec.slot_id}] "{rec.quote}"', language=None)
elif planted_events and any(e["flag_level"] == "red" for e in planted_events):
    st.warning("⚠️ Red flags expected from planted events but not triggered. Check mock evaluation.")
else:
    st.success("✅ No red flags today.")

# Yellow Flags
if report.sections.get("yellow"):
    st.markdown("### 🟡 Yellow Flags")
    for item in report.sections["yellow"]:
        st.warning(item["sentence"])
else:
    st.info("No yellow flags today.")

# Green
if report.sections.get("green"):
    st.markdown("### 🟢 Positive Progress")
    for item in report.sections["green"]:
        st.success(item["sentence"])

# Trends
if report.sections.get("trends"):
    st.markdown("### 📈 Trends")
    for item in report.sections["trends"]:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"- {item['sentence']}")
        with col2:
            sev = item.get("severity")
            if sev == "red":
                st.error("🔴")
            elif sev == "yellow":
                st.warning("🟡")
            elif sev == "green":
                st.success("🟢")

# Patient Concerns
if report.sections.get("concerns"):
    st.markdown("### 💬 Patient Concerns")
    for item in report.sections["concerns"]:
        st.info(f"💬 {item['sentence']}")
        if item.get("evidence_ids"):
            with st.expander("📎 Source"):
                for eid in item["evidence_ids"]:
                    rec = evidence_store.get_by_id(eid)
                    if rec:
                        st.code(f'"{rec.quote}"', language=None)

# Follow-up
st.markdown("### 📌 Follow-up Suggestions")
concerns_state = store.get("patient_concerns")
if concerns_state.value:
    st.markdown("- Review patient concerns listed above with the care team.")
apt_day = profile.get("upcoming_appointment_day")
if apt_day and selected_day >= apt_day - 3:
    st.markdown(f"- Appointment approaching (Day {apt_day}) — prepare consultation notes.")
if any(e["flag_level"] == "red" for e in planted_events):
    st.markdown("- ⚠️ Review the escalation alert for this session.")

# Information Gaps
if report.sections.get("gaps"):
    st.markdown("### ℹ️ Information Gaps")
    st.caption("Required slots that were not asked or answers were unclear.")
    for item in report.sections["gaps"]:
        st.markdown(f"- {item['sentence']}")

# Disclaimer
st.markdown("---")
st.caption(f"*{report.disclaimer}*")

# Planted events reference
if planted_events:
    with st.expander("🔬 Ground Truth Planted Events (Evaluation Only)"):
        for ev in planted_events:
            badge = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(ev["flag_level"], "⚪")
            st.markdown(f"{badge} **{ev['event_id']}**: {ev['description']} (Rule: `{ev['flag_rule']}`)")
