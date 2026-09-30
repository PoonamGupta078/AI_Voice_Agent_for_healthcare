"""
Page 2: Clinician Report — DYNAMIC, built from real live session data OR persona ground truth
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import yaml
from datetime import date, datetime
from careloop.config import load_slots
from careloop.state.slot_store import SlotStore, EvidenceStore
from careloop.flags.engine import FlagEngine
from careloop.trends.analyzer import TrendAnalyzer
from careloop.reports.claim_builder import ReportBuilder
from careloop.providers.mock import MockLLMClient
from careloop.models.data_models import SlotStatus
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Clinician Report — CareLoop", page_icon="📋", layout="wide")
st.title("📋 Clinician Report")
st.caption("Evidence-grounded. All thresholds are illustrative. Does not replace clinical judgment.")


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

# ─── Check if a real completed session is available ───────────────────────────
completed = st.session_state.get("completed_session")

if completed:
    # ══ LIVE SESSION MODE ══
    st.success("🟢 **Live Session Report** — built from your actual conversation just now.")
    
    selected_pid = completed["patient_id"]
    profile = completed["profile"]
    store = completed["slot_store"]
    evidence_store = completed["evidence_store"]
    flags_from_session = completed["flags_raised"]
    turns = completed["turns"]
    summary = completed["summary"]
    
    # Show conversation transcript in expander
    with st.expander("💬 Full Conversation Transcript", expanded=False):
        for turn in turns:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "assistant":
                st.markdown(f"🤖 **CareLoop:** {content}")
            else:
                st.markdown(f"👤 **Patient:** {content}")
            st.markdown("---")
    
    # Build report from real session data
    llm_key = os.environ.get("GOOGLE_API_KEY", "")
    if llm_key:
        from careloop.providers.google_llm import GoogleLLMClient
        llm = GoogleLLMClient(model_name="gemini-3.5-flash-lite")
    else:
        llm = MockLLMClient()
    
    builder = ReportBuilder(llm)
    today = date.today()
    report = builder.build(
        store, flags_from_session, {}, evidence_store, selected_pid,
        (today, today)
    )
    
    # Session metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Slot Coverage", f"{store.coverage_rate():.0%}")
    col2.metric("Questions Asked", summary.get("questions_asked", 0))
    col3.metric("Flags Raised", len(flags_from_session))
    col4.metric("Total Turns", summary.get("turns", 0))

elif "session" in st.session_state:
    live_session = st.session_state.session
    if live_session.session_closed:
        st.info("Session has ended. Please navigate back to the Live Session page to close it properly.")
        st.stop()
    else:
        st.warning("⚠️ The check-in session is still ongoing. This is a partial report based on what has been collected so far.")
        selected_pid = live_session.patient_id
        profile = live_session.profile
        store = live_session.slot_store
        evidence_store = live_session.evidence_store
        flags_from_session = live_session.flags_raised
        turns = live_session.turns
        summary = {"questions_asked": live_session.questions_asked, "turns": len(turns)}
        
        with st.expander("💬 Conversation So Far", expanded=False):
            for turn in turns:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role == "assistant":
                    st.markdown(f"🤖 **CareLoop:** {content}")
                else:
                    st.markdown(f"👤 **Patient:** {content}")
                st.markdown("---")
        
        llm_key = os.environ.get("GOOGLE_API_KEY", "")
        if llm_key:
            from careloop.providers.google_llm import GoogleLLMClient
            llm = GoogleLLMClient(model_name="gemini-3.5-flash-lite")
        else:
            llm = MockLLMClient()
        
        builder = ReportBuilder(llm)
        today = date.today()
        report = builder.build(store, flags_from_session, {}, evidence_store, selected_pid, (today, today))
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Slot Coverage", f"{store.coverage_rate():.0%}")
        col2.metric("Questions Asked", summary.get("questions_asked", 0))
        col3.metric("Flags Raised", len(flags_from_session))
        col4.metric("Turns", summary.get("turns", 0))

else:
    st.info("No session data found. Please start a Live Session to generate a real report.")
    if st.button("▶️ Go to Live Session"):
        st.switch_page("pages/5_Live_Session.py")
    st.stop()


# ─── RENDER REPORT (shared between live and static modes) ──────────────────────
st.markdown("---")
st.markdown(f"## 📄 Report: **{profile['name']}**")
fallback_count = report.verification.get("fallbacks_used", 0)
verification_text = "✅ Passed" if report.verification.get("passed") else f"⚠️ {fallback_count} fallback(s)"
st.markdown(f"*Generated at: {report.generated_at.strftime('%Y-%m-%d %H:%M')} UTC* | **Verification:** {verification_text}")

# Patient Overview
if report.sections.get("overview"):
    with st.expander("📊 Patient Overview", expanded=True):
        for item in report.sections["overview"]:
            st.markdown(f"- {item['sentence']}")

# Red Flags
st.markdown("### 🔴 Red Flags")
if report.sections.get("red"):
    for item in report.sections["red"]:
        st.error(f"🔴 {item['sentence']}")
        if item.get("evidence_ids"):
            with st.expander(f"📎 Evidence ({', '.join(item['evidence_ids'])})"):
                for eid in item["evidence_ids"]:
                    rec = evidence_store.get_by_id(eid)
                    if rec:
                        st.code(f'[{rec.slot_id}] "{rec.quote}"', language=None)
else:
    st.success("✅ No red flags.")

# Also show real flags from session engine
real_reds = [f for f in flags_from_session if f.level == "red"]
if real_reds:
    for f in real_reds:
        st.error(f"🔴 **FLAG ENGINE**: {f.message} → `{f.routed_to}`")

# Yellow Flags
st.markdown("### 🟡 Yellow Flags")
if report.sections.get("yellow"):
    for item in report.sections["yellow"]:
        st.warning(f"🟡 {item['sentence']}")
else:
    st.info("No yellow flags.")

real_yellows = [f for f in flags_from_session if f.level == "yellow"]
for f in real_yellows:
    st.warning(f"🟡 **FLAG ENGINE**: {f.message}")

# Green
if report.sections.get("green"):
    st.markdown("### 🟢 Positive Progress")
    for item in report.sections["green"]:
        st.success(f"🟢 {item['sentence']}")

# Trends
if report.sections.get("trends"):
    st.markdown("### 📈 Trends")
    for item in report.sections["trends"]:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"- {item['sentence']}")
        with col2:
            sev = item.get("severity")
            if sev == "red": st.error("🔴")
            elif sev == "yellow": st.warning("🟡")
            elif sev == "green": st.success("🟢")

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

# Slot Coverage Table
st.markdown("### 🗂️ Slot Data Collected")
rows = []
for slot_id, state in store.states.items():
    if state.status.value not in ("not_asked",):
        rows.append({
            "Slot": slot_id,
            "Status": state.status.value,
            "Value": str(state.value) if state.value is not None else "—",
            "Confidence": f"{state.confidence:.0%}" if state.confidence else "—",
            "Quote": state.quote or "—",
        })
if rows:
    st.dataframe(rows, use_container_width=True)
else:
    st.caption("No slots collected yet.")

# Follow-up
st.markdown("### 📌 Follow-up Suggestions")
concerns_state = store.get("patient_concerns")
if concerns_state and concerns_state.value:
    st.markdown("- Review patient concerns listed above with the care team.")
apt_day = profile.get("upcoming_appointment_day")
if apt_day:
    st.markdown(f"- Appointment scheduled for Day {apt_day} — prepare consultation notes.")
if report.sections.get("gaps"):
    st.markdown("### ℹ️ Information Gaps")
    st.caption("Slots not asked or answers were unclear.")
    for item in report.sections["gaps"]:
        st.markdown(f"- {item['sentence']}")

# Disclaimer
st.markdown("---")
st.caption(f"*{report.disclaimer}*")

# Clear session button
if completed:
    if st.button("🗑️ Clear Session & Start New"):
        del st.session_state["completed_session"]
        st.switch_page("pages/5_Live_Session.py")
