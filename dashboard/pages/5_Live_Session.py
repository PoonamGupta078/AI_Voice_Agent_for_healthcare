"""
Page 5: Live Session — text-based check-in with CareLoop agent
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import yaml
from careloop.conversation.session_manager import SessionManager
from careloop.providers.mock import MockLLMClient

st.set_page_config(page_title="Live Session — CareLoop", page_icon="💬", layout="wide")
st.title("💬 Live Check-in Session")
st.caption("Text-based session with the CareLoop agent. (Mock LLM — offline mode)")

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

profiles_raw = load_yaml(os.path.join(BASE, "profiles.yaml"))
persona_options = {p["name"]: pid for pid, p in profiles_raw.items()}
selected_name = st.sidebar.selectbox("Select Patient", list(persona_options.keys()))
selected_pid = persona_options[selected_name]
profile = profiles_raw[selected_pid]

# Session state management
if "session" not in st.session_state or st.sidebar.button("🔄 New Session"):
    llm = MockLLMClient()
    session = SessionManager(selected_pid, profile, llm, session_type="daily")
    greeting = session.start()
    st.session_state.session = session
    st.session_state.chat_history = [{"role": "assistant", "content": greeting}]
    st.session_state.flags = []
    st.session_state.latency_log = []

session: SessionManager = st.session_state.session

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Sidebar metrics
st.sidebar.markdown("---")
st.sidebar.metric("Slot Coverage", f"{session.slot_store.coverage_rate():.0%}")
st.sidebar.metric("Questions Asked", session.questions_asked)
st.sidebar.metric("Flags Raised", len(session.flags_raised))

# Input
if not session.session_closed:
    user_input = st.chat_input("Type your response here...")
    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("CareLoop is thinking..."):
            result = session.turn(user_input)

        reply = result["reply"]
        with st.chat_message("assistant"):
            st.markdown(reply)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})

        # Show new flags
        for flag in result.get("new_flags", []):
            level = flag.get("level", "yellow")
            if level == "red":
                st.error(f"🔴 **RED FLAG**: {flag['message']} → Routed to: `{flag.get('routed_to', 'care team')}`")
            elif level == "yellow":
                st.warning(f"🟡 **Yellow Flag**: {flag['message']}")
            elif level == "green":
                st.success(f"🟢 **Positive**: {flag['message']}")

        # Latency info
        lat = result.get("latency", {})
        if lat:
            with st.expander("⏱️ Latency breakdown"):
                cols = st.columns(4)
                cols[0].metric("Total", f"{lat.get('total_ms', 0)}ms")
                cols[1].metric("Lexical Net", f"{lat.get('lexical_ms', 0)}ms")
                cols[2].metric("Extraction", f"{lat.get('extraction_ms', 0)}ms")
                cols[3].metric("LLM Reply", f"{lat.get('llm_ms', 0)}ms")

        st.rerun()
else:
    st.success("✅ Session closed. Navigate to **Report** to see the clinician summary.")
    if st.button("View Session Summary"):
        summary = session.close()
        st.json(summary)
