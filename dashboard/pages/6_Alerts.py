"""
Page 6: Alerts — escalation events
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


import streamlit as st
import yaml

from careloop.config import load_slots
from careloop.flags.engine import FlagEngine
from careloop.models.data_models import SlotStatus
from careloop.state.slot_store import SlotStore

st.set_page_config(page_title="Alerts — CareLoop", page_icon="🚨", layout="wide")
st.title("🚨 Alerts & Escalations")
st.caption("Deterministic flag engine — no LLM involvement in safety decisions.")

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

profiles_raw = load_yaml(os.path.join(BASE, "profiles.yaml"))
persona_options = {p["name"]: pid for pid, p in profiles_raw.items()}

# Simulate ALL planted events across all personas and days
all_alerts = []
for pid, profile in profiles_raw.items():
    truth = load_yaml(os.path.join(BASE, f"{pid}_truth.yaml"))
    for i, day_data in enumerate(truth["days"]):
        day = i + 1
        fact_sheet = day_data["slots"]
        planted = day_data.get("planted_events", [])

        slots = load_slots()
        store = SlotStore(slots)
        for slot_id, val in fact_sheet.items():
            if store.catalogue.get(slot_id) is None:
                continue
            if isinstance(val, bool):
                status = SlotStatus.answered if val else SlotStatus.denied
            elif val is not None:
                status = SlotStatus.answered
            else:
                continue
            store.update(slot_id, status, val, 0.9, "t1", f"reported: {val}")

        engine = FlagEngine()
        flags = engine.evaluate(store, "realtime", f"{pid}_day{day}")
        flags += engine.evaluate(store, "end_of_session", f"{pid}_day{day}")

        for flag in flags:
            all_alerts.append({
                "persona": profile["name"],
                "day": day,
                "flag_id": flag.flag_id,
                "level": flag.level,
                "message": flag.message,
                "routed_to": flag.routed_to or "care team",
                "raised_at": str(flag.raised_at)[:19],
            })

# Summary counts
red_count = sum(1 for a in all_alerts if a["level"] == "red")
yellow_count = sum(1 for a in all_alerts if a["level"] == "yellow")
green_count = sum(1 for a in all_alerts if a["level"] == "green")

col1, col2, col3 = st.columns(3)
col1.metric("🔴 Red Flags", red_count)
col2.metric("🟡 Yellow Flags", yellow_count)
col3.metric("🟢 Positive", green_count)

st.markdown("---")

# Filter
level_filter = st.multiselect("Filter by level", ["red", "yellow", "green"], default=["red", "yellow"])
persona_filter = st.multiselect("Filter by patient", list({a["persona"] for a in all_alerts}))

filtered = all_alerts
if level_filter:
    filtered = [a for a in filtered if a["level"] in level_filter]
if persona_filter:
    filtered = [a for a in filtered if a["persona"] in persona_filter]

for alert in sorted(filtered, key=lambda x: (x["level"] != "red", x["day"])):
    badge = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(alert["level"], "⚪")
    if alert["level"] == "red":
        with st.container():
            st.error(f"{badge} **{alert['persona']}** — Day {alert['day']} | `{alert['flag_id']}`")
            st.markdown(f"  {alert['message']} → **Route:** `{alert['routed_to']}`")
    elif alert["level"] == "yellow":
        with st.container():
            st.warning(f"{badge} **{alert['persona']}** — Day {alert['day']} | `{alert['flag_id']}`")
            st.caption(f"  Route: `{alert['routed_to']}`")
    else:
        st.success(f"{badge} **{alert['persona']}** — Day {alert['day']} | `{alert['flag_id']}`")

if not filtered:
    st.info("No alerts match the current filter.")
