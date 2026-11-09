# MarketVue: Portfolio Analytics Agent Documentation

---

## 1. Overview and Purpose

**MarketVue** is an AI-powered portfolio analytics platform designed for investment management and quantitative research. It translates natural-language investment queries into secure SQLite SQL queries, executes deterministic sector exposure calculations, and provides executive-grade financial reasoning.

### Key Capabilities
1. **Natural Language to SQL**: Converts natural language financial queries into read-only SQL queries executed with security guardrails.
2. **Deterministic Sector Exposure**: Computes fund-level sector allocations programmatically using equity holdings (`asset_type = 'Stock'`).
3. **Dynamic Reasoning Layer**: Delivers structured financial summaries, metrics context, and explanations for zero-record conditions.
4. **Interactive Web Dashboard**: Streamlit interface featuring suggested queries, detailed audit trails, interactive session controls, and usage quotas.
5. **Session Usage Guardrails**: Configured with a 10-query limit per session to preserve shared Gemini API quota on public deployments.

---

## 2. Architecture & Execution Workflow

MarketVue routes incoming queries through an integrated pipeline:

```
                      [ User Question ]
                             |
                             v
                 +-----------------------+
                 |   Gemini Tool Router  |
                 +-----------------------+
                             |
             +---------------+---------------+
             |                               |
             v                               v
  [ Exposure Calculator ]             [ SQL Query Tool ]
  - Identifies target portfolio       - Generates schema-valid SQL
  - Filters equity holdings only      - Read-only execution URI
  - Computes sector weights           - Blocks DDL/DML modifications
             |                               |
             +---------------+---------------+
                             |
                             v
                 +-----------------------+
                 | Dynamic Reasoning     |
                 | - Synthesizes results |
                 | - Explains zero-hits  |
                 | - Clarifies metrics   |
                 +-----------------------+
                             |
                             v
                 [ Natural-Language Answer ]
                  (MarketVue Web / CLI)
```

### Execution Flow
1. **Tool Routing (`select_tool`)**: Routes sector exposure requests to the Exposure Calculator and database queries/aggregations to the SQL Query Tool.
2. **Exposure Calculator (`exposure_calculator.py`)**: Computes sector allocations using deterministic arithmetic.
3. **Safe SQL Execution (`sql_tool.py`)**: Executes read-only queries with SQLite authorizer callbacks, step limits, and table whitelisting.
4. **Dynamic Reasoning (`generate_reasoning`)**: Translates data points and table outputs into clear financial narrative summaries.
5. **Presentation**: Formats responses into responsive dataframes, metric pills, and expandable audit logs.

---

## 3. Database Schema and Storage

The SQLite database (`portfolio.db`) is initialized from normalized CSV files located in `data/`:

| Table | Records | Description | Primary Key | Key Foreign Keys |
|:---|:---:|:---|:---|:---|
| `portfolios` | 13 | Managed funds (name, strategy, target risk, AUM) | `portfolio_id` | None |
| `securities` | 30 | Equities and bonds (symbol, name, asset type, price) | `security_id` | `sector_id` |
| `sectors` | 10 | GICS Industry sectors | `sector_id` | None |
| `holdings` | 95 | Portfolio positions (shares, price, cost basis, weight) | `holding_id` | `portfolio_id`, `security_id` |
| `transactions` | 24 | Buy and sell trade records | `transaction_id` | `portfolio_id`, `security_id` |
| `historical_prices`| 330 | Daily stock price histories (OHLCV) | `price_id` | `security_id` |
| `portfolio_performance` | 44 | Monthly returns, NAV, volatility, Sharpe ratio | `performance_id` | `portfolio_id` |
| `risk_metrics` | 44 | Risk analytics (VaR 95/99, CVaR, Beta, Sortino ratio) | `risk_id` | `portfolio_id` |
| `benchmarks` | 13 | Market indices and metadata | `benchmark_id` | None |

---

## 4. Implemented Features & Modules

### A. SQL Query Engine (`sql_tool.py`)
- **Read-Only Mode**: SQLite connections are opened using `file:portfolio.db?mode=ro`.
- **Command Whitelisting**: Strict validation requiring statements to start with `SELECT` or `WITH`. Prohibits `INSERT`, `UPDATE`, `DELETE`, `DROP`, and `ALTER`.
- **SQLite Authorizer**: Low-level hook restricting actions to `SQLITE_SELECT`, `SQLITE_READ`, and `SQLITE_FUNCTION`. Blocks internal system tables (e.g., `sqlite_master`).
- **Resource Protection**: Caps queries at 1,000 returned rows and applies progress handler step limits to prevent runaway loops.

### B. Exposure Calculator (`exposure_calculator.py`)
- **Deterministic Math**: Bypasses LLM generation to compute exact sector allocations in Python.
- **Asset Filtering**: Automatically filters for `asset_type = 'Stock'`, ensuring bond holdings do not distort equity sector allocations.
- **Audit Logging**: Returns holding-level audit details alongside sector allocation percentages.

### C. Agent Orchestration (`portfolio_agent.py`)
- **Dynamic Entity Mapping**: Queries database fund names dynamically to accurately match informal user references.
- **Model Redundancy**: Configured with failover handling across `gemini-2.5-flash` and `gemini-flash-latest`.
- **Structured Pydantic Schemas**: Enforces strongly-typed responses (`ToolDecision`, `SQLResponse`, `ReasoningResponse`).
- **Dynamic Reasoning**: Evaluates results to generate executive commentary and clear explanations for empty queries.

### D. Streamlit Web Interface (`app.py`)
- **Executive Styling**: Modern institutional styling with custom CSS, dark navy accents, and clear typography.
- **Interactive Information Popovers**: Informational popover buttons (`ℹ️`) on both the sidebar and near suggested queries explain the 10-query session limit.
- **Session State Management**: Keeps conversation history and usage state across runs without external database overhead.
- **Zero-Config Database Initialization**: Automatically builds `portfolio.db` from CSV datasets on cloud startup if the database file is absent.

---

## 5. Session Usage Limits & API Protection

To prevent quota depletion in public cloud environments, MarketVue enforces session guardrails:

- **10-Query Session Limit**: Users are allocated up to 10 AI-assisted queries per session.
- **Proactive Warnings**: A warning banner appears after 7 queries indicating remaining calls.
- **Graceful Blocking**: When the 10-query limit is reached, AI inputs are disabled while access to database records, charts, and historical answers is maintained.
- **In-App Explanations**: Interactive popovers explain the policy to users upfront.

---

## 6. Verification and Evaluation Results

The application has been verified across official and extended benchmark suites:

### Benchmark Summary
- **Official Benchmark (`evaluate.py`)**: **10/10 Passed (100%)**
- **Extended Evaluation (`evaluate_extended.py`)**: **26/30 Passed (86.7%)**
- **Reliability & Security Test Suite (`test_reliability.py`)**: **22/22 Tests Passing**
- **Live Pre-Deployment Verification Run**: **10/10 Passed (100%)**

---

## 7. Setup and Execution

### Local Setup
```bash
git clone https://github.com/guruchiwate06/MarketVue.git
cd MarketVue

python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate # macOS/Linux

pip install -r requirements.txt
```

### Configuration
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Run Commands
```bash
# Initialize database
python database.py

# Launch web interface
streamlit run app.py

# Run CLI agent
python portfolio_agent.py

# Run test suites
python -m unittest test_reliability.py
python evaluate.py
```
