"""
Page 3: Trends — charts for all metrics over 14 days
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import yaml
import pandas as pd
import altair as alt
from datetime import date

st.set_page_config(page_title="Trends — CareLoop", page_icon="📈", layout="wide")
st.title("📈 Health Trends")

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

profiles_raw = load_yaml(os.path.join(BASE, "profiles.yaml"))
persona_options = {p["name"]: pid for pid, p in profiles_raw.items()}
selected_name = st.sidebar.selectbox("Select Patient", list(persona_options.keys()))
selected_pid = persona_options[selected_name]
profile = profiles_raw[selected_pid]

truth = load_yaml(os.path.join(BASE, f"{selected_pid}_truth.yaml"))

# Build multi-day dataframe
rows = []
for i, day_data in enumerate(truth["days"]):
    row = {"day": i + 1, "date": str(date(2026, 9, i + 1))}
    row.update(day_data["slots"])
    row["has_planted"] = len(day_data.get("planted_events", [])) > 0
    row["red_flag"] = any(e["flag_level"] == "red" for e in day_data.get("planted_events", []))
    rows.append(row)

df = pd.DataFrame(rows)

METRICS = {
    "weight_kg": "Weight (kg)",
    "sleep_hours": "Sleep (hours)",
    "activity_minutes": "Activity (minutes)",
    "mood_wellbeing": "Mood (0-10)",
    "hydration_glasses": "Hydration (glasses)",
    "glucose_reading": "Glucose (mg/dL)",
}

metric_options = [m for m in METRICS.keys() if m in df.columns]
selected_metric = st.selectbox("Metric", metric_options, format_func=lambda x: METRICS.get(x, x))

if selected_metric and selected_metric in df.columns:
    chart_df = df[["day", selected_metric, "red_flag", "has_planted"]].dropna()
    chart_df = chart_df.rename(columns={selected_metric: "value"})

    base = alt.Chart(chart_df).mark_line(point=True, color="#4F8EF7").encode(
        x=alt.X("day:Q", title="Day"),
        y=alt.Y("value:Q", title=METRICS.get(selected_metric, selected_metric)),
        tooltip=["day", "value", "red_flag"],
    ).properties(title=f"{METRICS.get(selected_metric, selected_metric)} over 14 days", height=350)

    # Highlight red flag days
    red_days = chart_df[chart_df["red_flag"] == True]
    if not red_days.empty:
        red_marks = alt.Chart(red_days).mark_point(
            color="red", size=150, shape="triangle-up"
        ).encode(x="day:Q", y="value:Q", tooltip=["day"])
        chart = base + red_marks
    else:
        chart = base

    st.altair_chart(chart, use_container_width=True)

    # Baseline reference
    baseline = profile.get("baselines", {}).get(selected_metric)
    if baseline:
        st.caption(f"📏 Baseline: **{baseline}** {selected_metric.split('_')[-1] if '_' in selected_metric else ''}")

# Summary table
st.markdown("### 📊 14-Day Summary Table")
display_cols = ["day"] + [m for m in METRICS.keys() if m in df.columns]
st.dataframe(df[display_cols].style.highlight_max(
    subset=[m for m in METRICS.keys() if m in df.columns and df[m].dtype != object], color="#ffcccc"
), use_container_width=True)

# Adherence
if "med_taken_today_morning" in df.columns:
    taken = df["med_taken_today_morning"].sum()
    total = df["med_taken_today_morning"].notna().sum()
    st.metric("Medication Adherence (Morning)", f"{int(taken)}/{int(total)} days",
              delta=f"{taken/total:.0%}" if total > 0 else "N/A")
