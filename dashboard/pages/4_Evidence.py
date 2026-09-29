"""
Page 4: Evidence — click a claim to see the transcript evidence
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import yaml
from datetime import date
from careloop.config import load_slots
from careloop.state.slot_store import SlotStore, EvidenceStore
from careloop.models.data_models import SlotStatus

st.set_page_config(page_title="Evidence — CareLoop", page_icon="🔍", layout="wide")
st.title("🔍 Evidence Explorer")
st.caption("Every claim links back to a transcript turn.")

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

profiles_raw = load_yaml(os.path.join(BASE, "profiles.yaml"))
persona_options = {p["name"]: pid for pid, p in profiles_raw.items()}
selected_name = st.sidebar.selectbox("Select Patient", list(persona_options.keys()))
selected_pid = persona_options[selected_name]
truth = load_yaml(os.path.join(BASE, f"{selected_pid}_truth.yaml"))

day_options = list(range(1, len(truth["days"]) + 1))
selected_day = st.sidebar.selectbox("Select Day", day_options, index=len(day_options) - 1)
day_data = truth["days"][selected_day - 1]
fact_sheet = day_data["slots"]

# Build evidence store from fact sheet
slots = load_slots()
store = SlotStore(slots)
evidence_store = EvidenceStore()

for slot_id, val in fact_sheet.items():
    spec = store.catalogue.get(slot_id)
    if spec is None:
        continue
    if isinstance(val, bool):
        status = SlotStatus.answered if val else SlotStatus.denied
        quote = f"Patient said: {'yes' if val else 'no'}, {slot_id.replace('_', ' ')}"
    elif val is not None:
        status = SlotStatus.answered
        quote = f"Patient reported {slot_id.replace('_', ' ')}: {val}"
    else:
        continue
    store.update(slot_id, status, val, 0.9, "t1", quote)
    evidence_store.add(selected_pid, f"day{selected_day}", slot_id, val, quote, "patient_statement", "t1")

st.markdown(f"### Evidence Records for **{profiles_raw[selected_pid]['name']}** — Day {selected_day}")

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
