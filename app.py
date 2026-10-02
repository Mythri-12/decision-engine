import os, subprocess, sys
import pandas as pd
import streamlit as st

if not os.path.exists("data.db"):
    subprocess.run([sys.executable, "load_data.py"], check=True)

from engine import ask, recommend

st.set_page_config(page_title="AI Decision Engine", layout="wide")
st.title("AI Decision Engine for Business Data")
st.caption("Ask a question. Every insight links back to its SQL and supporting rows.")

EXAMPLES = ["Which product categories drive the most revenue?", "Show monthly revenue trend", "Which region has the lowest revenue?"]
cols = st.columns(len(EXAMPLES))
for c, ex in zip(cols, EXAMPLES):
    if c.button(ex):
        st.session_state["q"] = ex

question = st.text_input("Your question", key="q", placeholder="e.g. Which product categories drive the most revenue?")

if (st.button("Analyse") or st.session_state.get("q")) and question.strip():
    with st.spinner("Thinking..."):
        try:
            res = ask(question)
        except RuntimeError as error:
            st.error(str(error))
            st.stop()

    if not res["answerable"]:
        st.warning("The available data can't answer that. " + res.get("explanation", ""))
    elif res.get("df") is None:
        st.error("Couldn't produce a valid query: " + res.get("error", "unknown error"))
        st.code(res["sql"], language="sql")
    else:
        df: pd.DataFrame = res["df"]
        st.write(res["explanation"])
        with st.expander("SQL used", expanded=True):
            st.code(res["sql"], language="sql")
        if df.empty:
            st.info("The query ran but returned no rows.")
        else:
            st.dataframe(df, use_container_width=True)
            if df.shape[1] == 2 and pd.api.types.is_numeric_dtype(df.iloc[:, 1]):
                chart_df = df.set_index(df.columns[0])
                is_time = any(k in df.columns[0].lower() for k in ("date", "month", "year", "week"))
                (st.line_chart if is_time else st.bar_chart)(chart_df)

            st.subheader("Recommendations")
            try:
                recommendations = recommend(question, res["sql"], df)
            except RuntimeError as error:
                st.error(str(error))
            else:
                for it in recommendations:
                    st.markdown(f"**Insight:** {it['insight']}")
                    st.markdown(f"**Action:** {it['action']}")
                    st.caption(f"Evidence: {it['evidence']}")
                    if it["ungrounded"]:
                        st.warning(f"Numbers not found in the result rows: {', '.join(it['ungrounded'])}")
