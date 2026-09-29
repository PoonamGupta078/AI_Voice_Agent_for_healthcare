"""
Page 7: Evaluation Results
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Eval Results — CareLoop", page_icon="📊", layout="wide")
st.title("📊 Evaluation Results")
st.caption("Mock-provider results — for real results, configure API keys and run `python -m eval.run_eval`.")

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "results")

csv_mini = os.path.join(RESULTS_DIR, "eval_mini.csv")
csv_full = os.path.join(RESULTS_DIR, "eval_full.csv")

if os.path.exists(csv_mini) or os.path.exists(csv_full):
    csv_path = csv_full if os.path.exists(csv_full) else csv_mini
    df = pd.read_csv(csv_path)

    tag = "FULL" if os.path.exists(csv_full) else "MINI"
    st.info(f"Showing {tag} evaluation results ({len(df)} rows). All results from MOCK providers.")

    # Summary by system
    st.markdown("### Summary by System")
    summary = df.groupby("system").agg(
        coverage=("coverage", "mean"),
        ig=("ig", "mean"),
        uqr=("uqr", "mean"),
        extraction_f1=("extraction_f1", "mean"),
        questions_asked=("questions_asked", "mean"),
    ).round(3).reset_index()
    summary.columns = ["System", "Avg Coverage", "Avg IG/Q", "Avg UQR", "Avg Extraction F1", "Avg Questions"]
    st.dataframe(summary, use_container_width=True)

    # Coverage by volunteer_prob chart
    st.markdown("### Coverage vs Volunteer Probability (H1)")
    chart_data = df.groupby(["system", "volunteer_prob"])["coverage"].mean().reset_index()
    chart = alt.Chart(chart_data).mark_line(point=True).encode(
        x=alt.X("volunteer_prob:Q", title="Volunteer Probability (p)"),
        y=alt.Y("coverage:Q", title="Avg Slot Coverage", scale=alt.Scale(zero=False)),
        color=alt.Color("system:N", title="System"),
        strokeDash=alt.condition(
            alt.datum.system == "P", alt.value([1, 0]), alt.value([4, 4])
        ),
    ).properties(title="Slot Coverage vs Disclosure Probability — CareLoop vs Baselines", height=350)
    st.altair_chart(chart, use_container_width=True)

    # F1 by volunteer_prob
    st.markdown("### Extraction F1 vs Volunteer Probability (H2)")
    f1_data = df.groupby(["system", "volunteer_prob"])["extraction_f1"].mean().reset_index()
    chart2 = alt.Chart(f1_data).mark_line(point=True).encode(
        x=alt.X("volunteer_prob:Q", title="Volunteer Probability (p)"),
        y=alt.Y("extraction_f1:Q", title="Avg Extraction F1", scale=alt.Scale(zero=False)),
        color="system:N",
    ).properties(title="Extraction F1 vs Disclosure Probability", height=300)
    st.altair_chart(chart2, use_container_width=True)

    # Full results table
    with st.expander("📋 Full Results Table"):
        st.dataframe(df, use_container_width=True)

    st.markdown("---")
    st.warning("⚠️ These are MOCK results demonstrating pipeline correctness. "
               "Configure real LLM/STT providers for meaningful metric values.")
else:
    st.warning("No evaluation results found. Run the evaluation first:")
    st.code("python -m eval.run_eval --mini", language="bash")
    if st.button("▶️ Run Mini Evaluation Now"):
        with st.spinner("Running evaluation... (may take a moment)"):
            try:
                from eval.run_eval import run_eval
                results = run_eval(mini=True)
                st.success(f"Done! {len(results)} result rows generated.")
                st.rerun()
            except Exception as e:
                st.error(f"Evaluation failed: {e}")
