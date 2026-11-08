"""
Portfolio Analytics - Web Application
A clean, professional interface for conversational portfolio analytics and quantitative research.
"""

import os
from pathlib import Path
import streamlit as st
import pandas as pd

# --------------------------------------------------
# Page Configuration
# --------------------------------------------------

st.set_page_config(
    page_title="MarketView",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent

# --------------------------------------------------
# Environment & Deployment Secrets Support
# --------------------------------------------------

# Silently load API key from Streamlit secrets if deployed
try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

# Ensure SQLite database is created from CSV datasets if deployed without portfolio.db
def ensure_database():
    """Ensure the SQLite database is initialized from CSV files if not present."""
    db_path = BASE_DIR / "portfolio.db"
    if not db_path.exists():
        with st.spinner("Initializing portfolio database from datasets..."):
            from database import create_database
            create_database()

ensure_database()

# Import the existing backend agent
from portfolio_agent import run_agent, format_response


# --------------------------------------------------
# Custom Styling (Minimalist Institutional Aesthetic)
# --------------------------------------------------

CUSTOM_CSS = """
<style>
    /* Global layout & typography */
    .main {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* Executive Header */
    .header-box {
        background: #0f2b48;
        color: #ffffff;
        padding: 1.75rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        border-bottom: 3px solid #1e5aa8;
    }
    .header-box h1 {
        color: #ffffff;
        margin: 0 0 0.35rem 0;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .header-box p {
        color: #94a3b8;
        margin: 0;
        font-size: 1rem;
        font-weight: 400;
    }
    
    /* Clean status badge */
    .status-badge {
        display: inline-block;
        background-color: rgba(255, 255, 255, 0.08);
        color: #e2e8f0;
        padding: 0.25rem 0.65rem;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 500;
        margin-top: 0.75rem;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }

    /* Analysis Callout Card */
    .analysis-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #0f2b48;
        padding: 1rem 1.25rem;
        border-radius: 6px;
        margin-bottom: 1.25rem;
        color: #0f172a;
        font-size: 0.95rem;
        line-height: 1.6;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
    }
    .analysis-title {
        display: block;
        font-weight: 700;
        color: #0f2b48;
        font-size: 0.88rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.35rem;
    }

    /* Single Metric Pill */
    .metric-pill {
        display: inline-block;
        background-color: #f1f5f9;
        color: #0f2b48;
        border: 1px solid #cbd5e1;
        padding: 0.4rem 0.85rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.75rem;
    }

    /* Clean query question title */
    .query-header {
        font-size: 1.15rem;
        font-weight: 600;
        color: #0f2b48;
        margin-top: 1rem;
        margin-bottom: 0.75rem;
        padding-bottom: 0.35rem;
        border-bottom: 1px solid #e2e8f0;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# --------------------------------------------------
# Session State Initialization
# --------------------------------------------------

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# --------------------------------------------------
# Sidebar: Dataset Specifications & Controls
# --------------------------------------------------

with st.sidebar:
    st.markdown("### Portfolio Dataset")
    st.markdown("""
    - **Portfolios:** 13 Funds
    - **Securities:** 30 Equities & Bonds
    - **Sectors:** 10 GICS Sectors
    - **Price History:** 330 Daily Records
    - **Transactions:** 24 Execution Records
    - **Performance Snapshots:** 44 Monthly Records
    """)
    
    st.markdown("---")
    st.markdown("### Session Controls")
    if st.button("Clear Session History", use_container_width=True):
        st.session_state.conversation_history = []
        st.session_state.pending_question = None
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<small style='color: #64748b;'>MarketView Analytics Platform<br>Institutional Quantitative Research</small>",
        unsafe_allow_html=True
    )


# --------------------------------------------------
# Application Header
# --------------------------------------------------

st.markdown("""
<div class="header-box">
    <h1>MarketView</h1>
    <p>An intelligent assistant for portfolio insights and financial analysis.</p>
    <div class="status-badge">System Status: Connected to SQLite Engine | Quantitative Reasoning Active</div>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------
# Suggested Query Pills
# --------------------------------------------------

st.markdown("**Suggested Queries**")

example_col1, example_col2, example_col3, example_col4 = st.columns(4)

EXAMPLES = [
    "What is the total AUM across all portfolios?",
    "Which sector has the highest exposure in Growth Equity Fund?",
    "Which portfolio has the highest recorded volatility?",
    "Show the five most recent transactions."
]

if example_col1.button(EXAMPLES[0], key="ex1", use_container_width=True):
    st.session_state.pending_question = EXAMPLES[0]
    st.rerun()

if example_col2.button(EXAMPLES[1], key="ex2", use_container_width=True):
    st.session_state.pending_question = EXAMPLES[1]
    st.rerun()

if example_col3.button(EXAMPLES[2], key="ex3", use_container_width=True):
    st.session_state.pending_question = EXAMPLES[2]
    st.rerun()

if example_col4.button(EXAMPLES[3], key="ex4", use_container_width=True):
    st.session_state.pending_question = EXAMPLES[3]
    st.rerun()


# --------------------------------------------------
# Main Input Box & Submission
# --------------------------------------------------

with st.form(key="question_form", clear_on_submit=False):
    default_text = st.session_state.pending_question if st.session_state.pending_question else ""
    user_query = st.text_input(
        "Enter a question regarding portfolios, holdings, risk metrics, or transactions:",
        value=default_text,
        placeholder="e.g., Which stocks are common across the highest number of portfolios?",
        key="query_input"
    )
    col_submit, _ = st.columns([1, 5])
    submit_clicked = col_submit.form_submit_button("Ask Agent", use_container_width=True)

# Determine the question to process
question_to_process = None
if submit_clicked and user_query.strip():
    question_to_process = user_query.strip()
    st.session_state.pending_question = None
elif st.session_state.pending_question:
    question_to_process = st.session_state.pending_question
    st.session_state.pending_question = None


# --------------------------------------------------
# Question Processing
# --------------------------------------------------

if question_to_process:
    with st.spinner("Analyzing query and executing quantitative analysis..."):
        agent_result = run_agent(question_to_process)
        
        # Save to session conversation history (newest at the beginning)
        st.session_state.conversation_history.insert(0, {
            "question": question_to_process,
            "result": agent_result
        })


# --------------------------------------------------
# Response Rendering Function
# --------------------------------------------------

def render_result_entry(item, is_latest=False):
    """Render one question and its structured agent response with executive styling."""
    question = item["question"]
    result = item["result"]

    st.markdown(f"<div class='query-header'>Query: {question}</div>", unsafe_allow_html=True)

    if not result:
        st.error("The agent returned no response.")
        return

    # Display dynamic reasoning / analytical interpretation
    explanation = result.get("explanation")
    if explanation:
        st.markdown(f"""
        <div class="analysis-card">
            <span class="analysis-title">Executive Summary & Analysis</span>
            {explanation}
        </div>
        """, unsafe_allow_html=True)

    # Check for empty input or basic error
    if not result.get("success"):
        tool = result.get("tool")
        if tool == "unsupported":
            reason = result.get("reason", "This request falls outside available portfolio analytics capabilities.")
            if not explanation:
                st.warning(f"Scope Notice: {reason}")
        else:
            error_msg = result.get("error", "An error occurred during query execution.")
            st.error(f"Execution Notice: {error_msg}")

        if result.get("sql"):
            with st.expander("Technical Details & Attempted SQL"):
                st.code(result.get("sql"), language="sql")
        return

    tool = result.get("tool")

    # 1. SQL Result Presentation
    if tool == "sql":
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        row_count = result.get("row_count", len(rows))
        truncated = result.get("truncated", False)

        if not rows:
            st.info("The query completed successfully. Zero records met the specified criteria.")
        else:
            # Single value display (1 column, 1 row)
            if len(columns) == 1 and len(rows) == 1:
                val = rows[0][0]
                col_name = columns[0]
                formatted_val = f"${val:,.2f}" if isinstance(val, (int, float)) and ("aum" in col_name.lower() or "cost" in col_name.lower() or "price" in col_name.lower() or "value" in col_name.lower()) else str(val)
                st.markdown(f"<div class='metric-pill'>{col_name}: {formatted_val}</div>", unsafe_allow_html=True)
            else:
                # Tabular display
                df = pd.DataFrame(rows, columns=columns)
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )
                if truncated:
                    st.caption("Note: Results were truncated to the maximum limit of 1,000 records.")
                else:
                    st.caption(f"Displaying {row_count} record{'s' if row_count != 1 else ''}.")

        # Technical Details Expander
        with st.expander("Technical Details & SQL Execution"):
            st.markdown(f"**Tool Invoked:** `{tool}`")
            st.markdown(f"**Records Returned:** {row_count}")
            st.markdown("**Executed SQL Query:**")
            st.code(result.get("sql", ""), language="sql")

    # 2. Exposure Calculator Presentation
    elif tool == "exposure_calculator":
        res_data = result.get("result", {})
        portfolio_name = res_data.get("portfolio_name", "Portfolio")
        exposures = res_data.get("sector_exposure", {})
        total_weight = res_data.get("total_equity_weight", 0.0)
        raw_holdings = res_data.get("raw_holdings", [])
        sql_used = res_data.get("sql_query") or res_data.get("sql_used", "")
        sql_params = res_data.get("sql_parameters") or res_data.get("sql_params", {})

        st.markdown(f"**Sector Exposure Breakdown: {portfolio_name}**")

        # Metric summary
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Active Equity Sectors", len(exposures))
        col_m2.metric("Total Equity Weight", f"{total_weight * 100:.2f}%")

        # Breakdown Table
        if exposures:
            exp_list = [
                {"Sector": sec, "Exposure Weight": f"{wt * 100:.2f}%"}
                for sec, wt in sorted(exposures.items(), key=lambda x: x[1], reverse=True)
            ]
            exp_df = pd.DataFrame(exp_list)
            st.dataframe(exp_df, use_container_width=True, hide_index=True)

        # Raw holdings table
        if raw_holdings:
            st.markdown("##### Underlying Equity Holdings")
            h_df = pd.DataFrame(raw_holdings)
            display_cols = [c for c in ["symbol", "company_name", "sector", "quantity", "current_weight"] if c in h_df.columns]
            rename_map = {
                "symbol": "Symbol",
                "company_name": "Company",
                "sector": "Sector",
                "quantity": "Quantity",
                "current_weight": "Weight"
            }
            if display_cols:
                h_df_display = h_df[display_cols].rename(columns=rename_map)
                st.dataframe(h_df_display, use_container_width=True, hide_index=True)

        # Technical Details Expander
        with st.expander("Technical Details & Calculation Parameters"):
            st.markdown(f"**Tool Invoked:** `{tool}`")
            st.markdown(f"**Portfolio:** {portfolio_name} (Identifier: {res_data.get('portfolio_id')})")
            st.markdown(f"**Equity Weight Aggregation:** {total_weight:.4f}")
            if sql_used:
                st.markdown("**Underlying Holdings Query:**")
                st.code(sql_used, language="sql")
                st.json(sql_params)

    st.markdown("---")


# --------------------------------------------------
# Display Session History
# --------------------------------------------------

if st.session_state.conversation_history:
    st.markdown("### Analysis Results & History")
    for idx, item in enumerate(st.session_state.conversation_history):
        render_result_entry(item, is_latest=(idx == 0))
else:
    st.info("Submit a question above or select a suggested query to begin.")
