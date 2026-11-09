"""
Portfolio Analytics - Web Application
A clean, professional interface for conversational portfolio analytics and quantitative research.
"""

import os
import html
import sqlite3
from pathlib import Path
import streamlit as st
import pandas as pd

# --------------------------------------------------
# Page Configuration
# --------------------------------------------------

st.set_page_config(
    page_title="MarketVue",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = Path(__file__).resolve().parent

# --------------------------------------------------
# Environment & Deployment Secrets Support
# --------------------------------------------------

from dotenv import load_dotenv

# Load local environment variables from .env
load_dotenv()

secrets_format_error = None

def resolve_api_key():
    """
    Search environment variables and Streamlit Secrets across all standard candidate names,
    casing variations, and nested TOML sections.
    """
    global secrets_format_error

    # 1. Environment variables
    for env_name in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY", "API_KEY"]:
        val = os.getenv(env_name)
        if val and val.strip():
            return val.strip()

    # 2. Streamlit secrets
    try:
        if hasattr(st, "secrets"):
            # Check direct candidate keys
            candidate_keys = [
                "GEMINI_API_KEY", "gemini_api_key", "Gemini_Api_Key",
                "GOOGLE_API_KEY", "google_api_key", "Google_Api_Key",
                "GEMINI_KEY", "gemini_key",
                "API_KEY", "api_key"
            ]
            for candidate in candidate_keys:
                if candidate in st.secrets:
                    val = str(st.secrets[candidate]).strip()
                    if val:
                        return val

            # Check nested sections like [general] or [gemini]
            for sec_k, sec_v in st.secrets.items():
                if isinstance(sec_v, str) and sec_v.strip() and any(x in sec_k.lower() for x in ["gemini", "google", "api"]):
                    return sec_v.strip()
                elif hasattr(sec_v, "items"):
                    for sub_k, sub_v in sec_v.items():
                        if isinstance(sub_v, str) and sub_v.strip() and any(x in sub_k.lower() for x in ["gemini", "google", "api", "key"]):
                            return sub_v.strip()
    except Exception as exc:
        err_msg = str(exc)
        if any(term in err_msg.lower() for term in ["toml", "decode", "syntax", "parse"]):
            secrets_format_error = f"Secrets format error: Ensure format is GEMINI_API_KEY = \"your_key\" (using an '=' and double quotes)."

    return ""

# Pre-populate os.environ with resolved key
_discovered_key = resolve_api_key()
if _discovered_key:
    os.environ["GEMINI_API_KEY"] = _discovered_key

# Ensure SQLite database is created from CSV datasets if deployed without portfolio.db
def ensure_database():
    """Ensure the SQLite database is initialized from CSV files if not present."""
    db_path = BASE_DIR / "portfolio.db"
    if not db_path.exists():
        with st.spinner("Initializing portfolio database from datasets..."):
            from database import create_database
            create_database()

ensure_database()

def check_database_status():
    """Verify local SQLite database connectivity independently of Gemini."""
    try:
        db_path = BASE_DIR / "portfolio.db"
        if not db_path.exists():
            return False, "Database file not found"
        connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        portfolio_count = connection.execute("SELECT COUNT(*) FROM portfolios").fetchone()[0]
        table_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
        connection.close()
        return True, f"Connected ({table_count} tables, {portfolio_count} funds)"
    except Exception as exc:
        return False, f"Connection failed: {exc}"

# Import the backend agent
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
    
    /* Clean status badges */
    .status-container {
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
        margin-top: 0.75rem;
    }
    .status-badge {
        display: inline-block;
        background-color: rgba(255, 255, 255, 0.08);
        color: #e2e8f0;
        padding: 0.25rem 0.65rem;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 500;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .status-db {
        border-left: 3px solid #10b981;
    }
    .status-api {
        border-left: 3px solid #38bdf8;
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
    .analysis-body {
        color: #1e293b;
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
# Usage Limits Configuration
# --------------------------------------------------

MAX_SESSION_QUESTIONS = 10
WARNING_THRESHOLD = 7


# --------------------------------------------------
# Session State Initialization
# --------------------------------------------------

if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# Dynamically resolve key on every run
active_key = resolve_api_key()
current_key_present = bool(active_key)
if active_key:
    os.environ["GEMINI_API_KEY"] = active_key

if "gemini_status" not in st.session_state:
    if current_key_present:
        st.session_state.gemini_status = "Standby (Key detected, unverified)"
    else:
        st.session_state.gemini_status = "Unconfigured (API key missing)"
else:
    # Dynamically update if key was added or removed
    if current_key_present and "Unconfigured" in st.session_state.gemini_status:
        st.session_state.gemini_status = "Standby (Key detected, unverified)"
    elif not current_key_present and "Standby" in st.session_state.gemini_status:
        st.session_state.gemini_status = "Unconfigured (API key missing)"

if "question_count" not in st.session_state:
    st.session_state.question_count = 0


# --------------------------------------------------
# Sidebar: Dataset Specifications & Controls
# --------------------------------------------------

db_is_connected, db_status_msg = check_database_status()

with st.sidebar:
    st.markdown("### System Availability")
    db_indicator = "Connected" if db_is_connected else "Disconnected"
    st.markdown(f"- **Database Engine:** {db_indicator}")
    st.markdown(f"  <small style='color: #64748b;'>{html.escape(db_status_msg)}</small>", unsafe_allow_html=True)
    st.markdown(f"- **AI Reasoning Service:**")
    st.markdown(f"  <small style='color: #64748b;'>{html.escape(st.session_state.gemini_status)}</small>", unsafe_allow_html=True)
    usage_col1, usage_col2 = st.columns([3, 1])
    with usage_col1:
        st.markdown(f"- **Session Query Usage:** {st.session_state.question_count} / {MAX_SESSION_QUESTIONS}")
    with usage_col2:
        with st.popover("ℹ️", help="Click to see session query limit details"):
            st.markdown("#### Session Query Limit Policy")
            st.markdown(
                f"Each user session allows up to **{MAX_SESSION_QUESTIONS} AI-powered questions**.\n\n"
                "**Why is this limit enforced?**\n"
                "- MarketVue is hosted as a public showcase application with shared Gemini API credentials.\n"
                "- This per-session limit helps prevent accidental or repetitive query loops from quickly consuming the API quota.\n"
                "- *Note:* This is a client-side session control and does not guarantee global API quota availability if multiple users query concurrently.\n"
                "- A warning appears after **7 queries**; new AI query generation is paused after **10 queries**.\n\n"
                "All portfolio data, dashboard statistics, and previously generated session results remain fully accessible."
            )

    if "Quota Exhausted" in st.session_state.gemini_status:
        st.warning(
            "Gemini API quota is currently exhausted. New natural-language AI queries and reasoning "
            "are temporarily paused. Existing dashboard metrics, portfolio dataset statistics, and previously "
            "retrieved results remain fully accessible."
        )

    if secrets_format_error:
        st.error(secrets_format_error)
    elif not current_key_present:
        st.info("API Key Setup: In Streamlit Cloud, go to App Settings > Secrets and add:\n\nGEMINI_API_KEY = \"your_api_key\"")

    st.markdown("---")
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
        "<small style='color: #64748b;'>MarketVue Analytics Platform<br>Institutional Quantitative Research</small>",
        unsafe_allow_html=True
    )


# --------------------------------------------------
# Application Header
# --------------------------------------------------

db_badge_text = f"Database: {db_status_msg}"
api_badge_text = f"AI Reasoning: {st.session_state.gemini_status}"

st.markdown(f"""
<div class="header-box">
    <h1>MarketVue</h1>
    <p>An intelligent assistant for portfolio insights and financial analysis.</p>
    <div class="status-container">
        <div class="status-badge status-db">{html.escape(db_badge_text)}</div>
        <div class="status-badge status-api">{html.escape(api_badge_text)}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# --------------------------------------------------
# Usage Warning & Limit Notification
# --------------------------------------------------

limit_reached = st.session_state.question_count >= MAX_SESSION_QUESTIONS

if limit_reached:
    st.error(
        f"Session limit reached: You have submitted {MAX_SESSION_QUESTIONS} of {MAX_SESSION_QUESTIONS} permitted questions for this session. "
        "Additional AI-powered queries are disabled. All portfolio data, previous results, and dashboard features remain accessible below."
    )
elif st.session_state.question_count >= WARNING_THRESHOLD:
    remaining = MAX_SESSION_QUESTIONS - st.session_state.question_count
    st.warning(
        f"Session usage warning: You have submitted {st.session_state.question_count} of {MAX_SESSION_QUESTIONS} questions. "
        f"Only {remaining} question{' is' if remaining == 1 else 's are'} remaining before the session limit is reached."
    )


# --------------------------------------------------
# Suggested Query Pills & Usage Info Notice
# --------------------------------------------------

suggested_hdr_col, info_btn_col = st.columns([5, 1])
with suggested_hdr_col:
    st.markdown("**Suggested Queries**")
with info_btn_col:
    with st.popover("ℹ️ Query Limit", help="Click to view policy on session query limits"):
        st.markdown("#### Session Query Limit Policy")
        st.markdown(
            f"Each user session allows up to **{MAX_SESSION_QUESTIONS} AI queries**.\n\n"
            "**Why is this limit enforced?**\n"
            "- MarketVue is hosted on a public demonstration environment sharing API quota.\n"
            "- The per-session cap prevents individual sessions from running excessive automated or repetitive loops.\n"
            "- *Note:* This per-session limit does not provide a global quota guarantee against concurrent multi-user traffic.\n"
            "- A warning is shown after **7 questions**, and new AI queries are paused after **10 questions**.\n\n"
            "You can always view all database tables, previous question results, and calculations even after reaching the limit."
        )

example_col1, example_col2, example_col3, example_col4 = st.columns(4)

EXAMPLES = [
    "What is the total AUM across all portfolios?",
    "Which sector has the highest exposure in Growth Equity Fund?",
    "Which portfolio has the highest recorded volatility?",
    "Show the five most recent transactions."
]

if example_col1.button(EXAMPLES[0], key="ex1", use_container_width=True, disabled=limit_reached):
    st.session_state.pending_question = EXAMPLES[0]
    st.rerun()

if example_col2.button(EXAMPLES[1], key="ex2", use_container_width=True, disabled=limit_reached):
    st.session_state.pending_question = EXAMPLES[1]
    st.rerun()

if example_col3.button(EXAMPLES[2], key="ex3", use_container_width=True, disabled=limit_reached):
    st.session_state.pending_question = EXAMPLES[2]
    st.rerun()

if example_col4.button(EXAMPLES[3], key="ex4", use_container_width=True, disabled=limit_reached):
    st.session_state.pending_question = EXAMPLES[3]
    st.rerun()


# --------------------------------------------------
# Main Input Box & Submission
# --------------------------------------------------

with st.form(key="question_form", clear_on_submit=False):
    default_text = st.session_state.pending_question if (st.session_state.pending_question and not limit_reached) else ""
    user_query = st.text_input(
        "Enter a question regarding portfolios, holdings, risk metrics, or transactions:",
        value=default_text,
        placeholder="e.g., Which stocks are common across the highest number of portfolios?" if not limit_reached else "Session question limit reached.",
        key="query_input",
        disabled=limit_reached
    )
    col_submit, _ = st.columns([1, 5])
    submit_clicked = col_submit.form_submit_button("Ask Agent", use_container_width=True, disabled=limit_reached)

# Determine the question to process
question_to_process = None
if not limit_reached:
    if submit_clicked and user_query.strip():
        question_to_process = user_query.strip()
        st.session_state.pending_question = None
    elif st.session_state.pending_question:
        question_to_process = st.session_state.pending_question
        st.session_state.pending_question = None
else:
    st.session_state.pending_question = None


# --------------------------------------------------
# Question Processing
# --------------------------------------------------

if question_to_process:
    if st.session_state.question_count >= MAX_SESSION_QUESTIONS:
        st.error("Session question limit reached. Additional AI-powered queries are disabled.")
    else:
        st.session_state.question_count += 1
        with st.spinner("Analyzing query and executing quantitative analysis..."):
            agent_result = run_agent(question_to_process)
        
        # Update Gemini status based on the live response
        err_type = agent_result.get("error_type")
        r_status = agent_result.get("reasoning_status")

        if err_type == "quota_exhausted" or r_status == "quota_exhausted":
            st.session_state.gemini_status = "Quota Exhausted (Free Tier Exceeded)"
        elif err_type == "auth_error" or r_status == "auth_error":
            st.session_state.gemini_status = "Authentication Error"
        elif err_type == "network_error" or r_status == "network_error":
            st.session_state.gemini_status = "Network Unreachable"
        elif agent_result.get("explanation") and r_status == "success":
            st.session_state.gemini_status = "Active (Verified)"

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

    st.markdown(f"<div class='query-header'>Query: {html.escape(question)}</div>", unsafe_allow_html=True)

    if not result:
        st.error("The agent returned no response.")
        return

    # 1. Safely render dynamic reasoning explanation if present
    explanation = result.get("explanation")
    if explanation:
        safe_explanation = html.escape(str(explanation)).replace("\n", "<br>")
        st.markdown(f"""
        <div class="analysis-card">
            <span class="analysis-title">Executive Summary & Analysis</span>
            <div class="analysis-body">{safe_explanation}</div>
        </div>
        """, unsafe_allow_html=True)

    # 2. Inform user cleanly if reasoning was unavailable
    r_status = result.get("reasoning_status")
    if not explanation and r_status and r_status != "success":
        if r_status == "quota_exhausted":
            st.info(
                "AI Reasoning Notice: Natural-language reasoning is temporarily unavailable due to Gemini API quota limits. "
                "The structured query data results retrieved from the database are presented below."
            )
        elif r_status == "auth_error":
            st.warning("AI Reasoning Notice: Natural-language reasoning is unavailable due to an API authentication failure.")
        elif r_status == "network_error":
            st.warning("AI Reasoning Notice: Natural-language reasoning is unavailable due to a network connection timeout.")
        elif r_status == "unconfigured":
            st.info("AI Reasoning Notice: Gemini API key is not configured. Natural-language reasoning is disabled.")

    # 3. Handle failure cases (routing or execution errors)
    if not result.get("success"):
        err_type = result.get("error_type")
        tool = result.get("tool")

        if err_type == "quota_exhausted":
            st.warning(
                "API Quota Notice: The Gemini API quota is currently exhausted. New natural-language queries "
                "cannot be translated into SQL while the API is unavailable. Previously generated session results, "
                "database metrics, and portfolio datasets remain fully accessible below."
            )
        elif err_type == "auth_error":
            st.error("Authentication Error: The Gemini API rejected the credentials. Please verify your GEMINI_API_KEY.")
        elif err_type == "network_error":
            st.error("Network Error: Could not reach the Gemini API service. Please verify your internet connection.")
        elif err_type == "sql_error":
            st.error(f"Database Query Error: {result.get('error', 'SQL execution failed.')}")
        elif tool == "unsupported":
            reason = result.get("reason", "This request falls outside available portfolio analytics capabilities.")
            if not explanation:
                st.warning(f"Scope Notice: {reason}")
        else:
            error_msg = result.get("error", "An error occurred during query execution.")
            st.error(f"Execution Notice: {error_msg}")

        if result.get("sql"):
            with st.expander("Technical Details & Attempted SQL"):
                st.code(result.get("sql"), language="sql")
        if result.get("details"):
            with st.expander("Technical Error Details"):
                st.text(result.get("details"))
        return

    # 4. Handle successful execution
    tool = result.get("tool")

    # SQL Result Presentation
    if tool == "sql":
        columns = result.get("columns", [])
        rows = result.get("rows", [])
        row_count = result.get("row_count", len(rows))
        truncated = result.get("truncated", False)

        if not rows:
            st.info("Query completed successfully. Zero records met the specified criteria.")
        else:
            # Single value display (1 column, 1 row)
            if len(columns) == 1 and len(rows) == 1:
                val = rows[0][0]
                col_name = columns[0]
                formatted_val = f"${val:,.2f}" if isinstance(val, (int, float)) and any(term in col_name.lower() for term in ["aum", "cost", "price", "value"]) else str(val)
                safe_col = html.escape(str(col_name))
                safe_val = html.escape(str(formatted_val))
                st.markdown(f"<div class='metric-pill'>{safe_col}: {safe_val}</div>", unsafe_allow_html=True)
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
            st.markdown(f"**Reasoning Status:** `{r_status or 'N/A'}`")
            st.markdown("**Executed SQL Query:**")
            st.code(result.get("sql", ""), language="sql")

    # Exposure Calculator Presentation
    elif tool == "exposure_calculator":
        res_data = result.get("result", {})
        portfolio_name = res_data.get("portfolio_name", "Portfolio")
        exposures = res_data.get("sector_exposure", {})
        total_weight = res_data.get("total_equity_weight", 0.0)
        raw_holdings = res_data.get("raw_holdings", [])
        sql_used = res_data.get("sql_query") or res_data.get("sql_used", "")
        sql_params = res_data.get("sql_parameters") or res_data.get("sql_params", {})

        st.markdown(f"**Sector Exposure Breakdown: {html.escape(portfolio_name)}**")

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
            st.markdown(f"**Portfolio:** {html.escape(str(portfolio_name))} (Identifier: {res_data.get('portfolio_id')})")
            st.markdown(f"**Equity Weight Aggregation:** {total_weight:.4f}")
            st.markdown(f"**Reasoning Status:** `{r_status or 'N/A'}`")
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
