"""
Page 4: Evidence — click a claim to see the transcript evidence
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


import streamlit as st
import yaml

from careloop.config import load_slots
from careloop.models.data_models import SlotStatus
from careloop.state.slot_store import EvidenceStore, SlotStore

st.set_page_config(page_title="Evidence — CareLoop", page_icon="🔍", layout="wide")
st.title("🔍 Evidence Explorer")
st.caption("Every claim links back to a transcript turn.")

if "session" in st.session_state:
    session = st.session_state.session
    store = session.slot_store
    evidence_store = session.evidence_store
    st.markdown(f"### Evidence Records for **{session.profile['name']}** — Live Session")
else:
    st.info("No live session is currently active. Please start a Live Session to see evidence records.")
    st.stop()



all_records = evidence_store.records
if not all_records:
    st.info("No evidence records for this session.")
else:
    # Filter
    slot_filter = st.multiselect(
        "Filter by slot",
        options=list({r.slot_id for r in all_records}),
        default=[],
    )
    filtered = all_records if not slot_filter else [r for r in all_records if r.slot_id in slot_filter]

    for rec in filtered:
        state = store.get(rec.slot_id)
        badge = {"answered": "✅", "denied": "❌", "asked_unclear": "❓", "not_asked": "⬜"}.get(
            state.status.value, "⬜"
        )
        with st.container():
            col1, col2, col3 = st.columns([1, 3, 2])
            with col1:
                st.code(rec.evidence_id)
            with col2:
                st.markdown(f"**{badge} {rec.slot_id}**")
                st.caption(f'"{rec.quote}"')
            with col3:
                st.caption(f"Value: `{rec.value}`")
                st.caption(f"Turn: `{rec.turn_id}` | Source: `{rec.source_type}`")
        st.divider()

# Slot state summary
st.markdown("### Slot State Summary")
states_data = []
for slot_id, state in store.all_states().items():
    spec = store.catalogue.get(slot_id)
    states_data.append({
        "Slot ID": slot_id,
        "Tier": spec.tier if spec else "?",
        "Status": state.status.value,
        "Value": str(state.value) if state.value is not None else "",
        "Asked Count": state.asked_count,
    })

import pandas as pd

df = pd.DataFrame(states_data)
status_colors = {"answered": "✅", "denied": "❌", "not_asked": "⬜", "asked_unclear": "❓"}
df["Status"] = df["Status"].map(lambda x: f"{status_colors.get(x, '')} {x}")
st.dataframe(df, use_container_width=True)
