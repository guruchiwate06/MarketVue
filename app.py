"""
Portfolio Analytics - Streamlit Web Application
A clean, professional interface for conversational portfolio analytics and financial analysis.
"""

import os
from pathlib import Path
import streamlit as st
import pandas as pd

# --------------------------------------------------
# Page Configuration & Visual Theme
# --------------------------------------------------

st.set_page_config(
    page_title="Portfolio Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent

# --------------------------------------------------
# Deployment & Environment Secrets Support
# --------------------------------------------------

# Support Streamlit Community Cloud secrets
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
# Custom Styling (Financial Services Aesthetic)
# --------------------------------------------------

CUSTOM_CSS = """
<style>
    /* Main container background and typography */
    .main {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* Header card */
    .header-box {
        background: linear-gradient(135deg, #0f2b48 0%, #1e3a5f 100%);
        color: #ffffff;
        padding: 1.75rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(15, 43, 72, 0.08);
    }
    .header-box h1 {
        color: #ffffff;
        margin: 0 0 0.4rem 0;
        font-size: 2.1rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .header-box p {
        color: #cbd5e1;
        margin: 0;
        font-size: 1.05rem;
        font-weight: 400;
    }
    
    /* Subtle status badge */
    .status-badge {
        display: inline-block;
        background-color: rgba(255, 255, 255, 0.15);
        color: #f1f5f9;
        padding: 0.25rem 0.65rem;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 500;
        margin-top: 0.75rem;
    }

    /* Example questions cards */
    .example-btn {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.6rem 0.9rem;
        margin-bottom: 0.5rem;
        color: #1e3a5f;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .example-btn:hover {
        background-color: #f1f5f9;
        border-color: #cbd5e1;
    }

    /* Card styling for results */
    .result-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
    }
    
    /* Metric pill */
    .metric-pill {
        display: inline-block;
        background-color: #eff6ff;
        color: #1e40af;
        border: 1px solid #dbeafe;
        padding: 0.35rem 0.75rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.88rem;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
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
# Sidebar: Settings & System Information
# --------------------------------------------------

with st.sidebar:
    st.markdown("### ⚙️ System Settings")
    
    current_key = os.getenv("GEMINI_API_KEY", "")
    masked_key = f"{current_key[:6]}...{current_key[-4:]}" if len(current_key) >= 12 else ("Configured" if current_key else "Missing")
    
    if not current_key:
        user_key = st.text_input(
            "Gemini API Key",
            type="password",
            help="Enter your Gemini API key if not set in environment or secrets."
        )
        if user_key:
            os.environ["GEMINI_API_KEY"] = user_key.strip()
            st.success("API Key updated for this session.")
    else:
        st.markdown(f"**Gemini API Key:** `{masked_key}`")
    
    st.markdown("---")
    st.markdown("### 📁 Database Metrics")
    st.markdown("""
    - **Portfolios:** 13 funds
    - **Securities:** 30 equities & bonds
    - **Sectors:** 10 GICS sectors
    - **Price History:** 330 records
    - **Transactions:** 24 trade logs
    - **Performance Snapshots:** 44 months
    """)
    
    st.markdown("---")
    if st.button("🗑️ Clear Conversation History", use_container_width=True):
        st.session_state.conversation_history = []
        st.session_state.pending_question = None
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<small style='color: #64748b;'>Portfolio Analytics v1.0<br>Built for quantitative and institutional analysis.</small>",
        unsafe_allow_html=True
    )


# --------------------------------------------------
# Application Header
# --------------------------------------------------

st.markdown("""
<div class="header-box">
    <h1>Portfolio Analytics</h1>
    <p>An intelligent assistant for portfolio insights and financial analysis.</p>
    <div class="status-badge">● SQLite Database Connected &nbsp;|&nbsp; Gemini AI Active</div>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------
# Example Questions Area
# --------------------------------------------------

st.markdown("##### Suggested Queries")

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
# Main Input Box & Ask Form
# --------------------------------------------------

with st.form(key="question_form", clear_on_submit=False):
    default_text = st.session_state.pending_question if st.session_state.pending_question else ""
    user_query = st.text_input(
        "Ask a question about portfolios, securities, risk metrics, or transactions:",
        value=default_text,
        placeholder="e.g., What are the top 5 holdings by cost basis in Growth Equity Fund?",
        key="query_input"
    )
    col_submit, col_spacer = st.columns([1, 5])
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
    with st.spinner("Analyzing question and querying database..."):
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
    """Render one question and its structured agent response."""
    question = item["question"]
    result = item["result"]

    st.markdown(f"#### 💬 {question}")

    if not result:
        st.error("The agent returned no response.")
        return

    # Display dynamic reasoning / analytical interpretation if available
    explanation = result.get("explanation")
    if explanation:
        st.markdown(f"""
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #1e3a5f; padding: 0.9rem 1.15rem; border-radius: 6px; margin-bottom: 1rem; color: #0f172a; font-size: 0.95rem; line-height: 1.55;">
            <strong style="color: #1e3a5f;">💡 Financial Analysis:</strong><br>{explanation}
        </div>
        """, unsafe_allow_html=True)

    # Check for empty input or basic error
    if not result.get("success"):
        tool = result.get("tool")
        if tool == "unsupported":
            reason = result.get("reason", "This question is outside the agent's capabilities.")
            if not explanation:
                st.warning(f"**Unsupported Query:** {reason}")
        else:
            error_msg = result.get("error", "An error occurred during processing.")
            st.error(f"**Error Details:** {error_msg}")

        # If SQL was generated before failing, show technical details
        if result.get("sql"):
            with st.expander("🛠️ Technical Details & Attempted SQL"):
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
            st.info("The query executed successfully, but 0 matching records were found for the specified criteria.")
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
                    st.caption("⚠️ Note: Results were truncated to the maximum limit of 1,000 rows.")
                else:
                    st.caption(f"Displaying {row_count} record{'s' if row_count != 1 else ''}.")

        # Technical Details Expander
        with st.expander("🛠️ Technical Details & SQL Execution"):
            st.markdown(f"**Tool Used:** `{tool}`")
            st.markdown(f"**Records Returned:** {row_count}")
            st.markdown("**Generated SQL Query:**")
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

        st.markdown(f"**Sector Exposure Breakdown for {portfolio_name}**")

        # Metric summary
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("Active Equity Sectors", len(exposures))
        col_m2.metric("Total Equity Weight", f"{total_weight * 100:.2f}%")

        # Breakdown Table
        if exposures:
            exp_list = [
                {"Sector": sec, "Exposure Weight": f"{wt * 100:.2f}%", "Weight Value": wt}
                for sec, wt in sorted(exposures.items(), key=lambda x: x[1], reverse=True)
            ]
            exp_df = pd.DataFrame(exp_list)[["Sector", "Exposure Weight"]]
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
        with st.expander("🛠️ Technical Details & Calculation Parameters"):
            st.markdown(f"**Tool Used:** `{tool}`")
            st.markdown(f"**Portfolio Name:** {portfolio_name} (ID: {res_data.get('portfolio_id')})")
            st.markdown(f"**Equity Weight Aggregation:** {total_weight:.4f}")
            if sql_used:
                st.markdown("**Underlying Holdings Query:**")
                st.code(sql_used, language="sql")
                st.json(sql_params)

    st.markdown("---")


# --------------------------------------------------
# Display Conversation History
# --------------------------------------------------

if st.session_state.conversation_history:
    st.markdown("### 📜 Results & Session History")
    for idx, item in enumerate(st.session_state.conversation_history):
        render_result_entry(item, is_latest=(idx == 0))
else:
    st.info("Enter a question above or select one of the suggested queries to begin.")
