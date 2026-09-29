"""
CareLoop Streamlit Dashboard (M7)
Multi-page: Patients, Report, Trends, Evidence, Alerts, Live Session, Eval Results
"""
import streamlit as st

st.set_page_config(
    page_title="CareLoop — Health Check-in Dashboard",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
st.sidebar.image("https://img.icons8.com/fluency/96/stethoscope.png", width=64)
st.sidebar.title("🩺 CareLoop")
st.sidebar.markdown("**AI Voice Agent for Older Adults**")
st.sidebar.markdown("---")
st.sidebar.caption("⚠️ This is a research prototype using synthetic data only. "
                   "All thresholds are illustrative and not medical recommendations.")

# Navigation is handled by pages/
st.title("Welcome to CareLoop")
st.markdown("""
### AI-Powered Voice Check-in for Older Adults

CareLoop is a **stateful, evidence-grounded, safety-constrained** voice agent for daily health check-ins.

| What it does | How |
|---|---|
| 📋 Daily/weekly health check-ins | Slot-based state tracking |
| 💊 Medication adherence | Deterministic question planner |
| 🔴 Red flag detection | Rule engine (no LLM decisions) |
| 📊 Trend analysis | Statistical analysis over 7-14 days |
| 📝 Clinician reports | Evidence-grounded, every claim cited |

---

**→ Navigate using the sidebar to see the full dashboard.**

> *Prototype only. Not for clinical use. Synthetic patient data.*
""")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Personas", "3", help="Synthetic patient personas")
with col2:
    st.metric("Days Simulated", "14", help="Days of conversation per persona")
with col3:
    st.metric("Flag Rules", "9", help="Deterministic safety rules")
