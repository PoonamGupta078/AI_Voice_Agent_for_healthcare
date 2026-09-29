"""
Page 1: Patients Overview
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import yaml

st.set_page_config(page_title="Patients — CareLoop", page_icon="👥", layout="wide")
st.title("👥 Patient Overview")
st.caption("Synthetic patient personas only — no real data.")


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

try:
    profiles = load_yaml(os.path.join(BASE, "profiles.yaml"))
except Exception as e:
    st.error(f"Could not load personas: {e}")
    st.stop()

for pid, profile in profiles.items():
    with st.expander(f"🧑‍⚕️ {profile['name']} — Age {profile['age']}", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Conditions:** {', '.join(profile.get('conditions', []))}")
            st.markdown(f"**Language:** {profile.get('language', 'en')}")
        with col2:
            meds = profile.get("medications", [])
            for m in meds:
                st.markdown(f"💊 `{m['name']}` — {m['dose']} ({m['schedule']})")
        with col3:
            baselines = profile.get("baselines", {})
            for k, v in baselines.items():
                st.metric(k.replace("_", " ").title(), v)
        goals = profile.get("goals", [])
        if goals:
            st.markdown("**Goals:** " + " | ".join(f"`{g}`" for g in goals))
        apt = profile.get("upcoming_appointment_day")
        if apt:
            st.info(f"📅 Next appointment: Day {apt}")
