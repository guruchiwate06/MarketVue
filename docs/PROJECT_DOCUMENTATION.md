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

## 3. Repository File Directory & Descriptions

The following table provides an exhaustive breakdown of every file in the repository, its purpose, and its architectural role:

| File / Path | Category | Purpose and Technical Description |
|:---|:---:|:---|
| **`app.py`** | Application Frontend | Streamlit web interface for MarketVue. Handles user interaction, suggested query buttons, responsive data rendering, technical detail expanders, session-based usage counters (10-query limit with warning at 7), and zero-configuration cloud database initialization. |
| **`portfolio_agent.py`** | Core Agent | Main orchestrator for natural-language query resolution. Implements the tool routing logic (`select_tool`), SQL generation prompt (`generate_sql`), dynamic reasoning synthesis (`generate_reasoning`), model failover across `ACTIVE_MODELS`, and response formatting (`format_response`). |
| **`sql_tool.py`** | Data Retrieval Tool | Secure SQLite execution harness. Enforces read-only database connections (`?mode=ro`), keyword validation, low-level SQLite authorizer callbacks (blocking non-whitelisted tables and system catalogs), step execution boundaries, and row output limits (1,000 max rows). |
| **`exposure_calculator.py`** | Quantitative Calculator | Deterministic sector allocation calculator. Performs Python-based mathematical aggregation of portfolio holdings strictly filtered for equity securities (`asset_type = 'Stock'`), returning sector exposure percentages, total equity weights, and position audit trails. |
| **`database.py`** | Database Loader | Database setup and ingestion script. Uses `database_schema.sql` as the single source of truth, enables foreign key enforcement (`PRAGMA foreign_keys = ON;`), and populates all nine tables from CSV files in foreign-key dependency order within an atomic transaction. |
| **`database_schema.sql`** | Database Schema | Definitive DDL schema defining all 9 tables, primary keys, foreign-key relationships, unique constraints, check constraints (`asset_type IN ('Stock', 'Bond')`), and composite indexes for query optimization. |
| **`test_reliability.py`** | Offline Test Suite | 22 unit and integration tests verifying error classification, graceful failure isolation (preserving SQL/exposure results when reasoning is paused), SQL security barriers, and session limit counter logic without making live Gemini API calls. |
| **`evaluate.py`** | Benchmark Evaluator | Automated evaluation harness for the official 10-question ground truth dataset. Compares agent-generated outputs against reference queries with numeric tolerance handling and ordering checks. |
| **`evaluate_extended.py`** | Benchmark Evaluator | Automated evaluation harness for the extended 30-question test dataset across 6 quantitative portfolio research categories. |
| **`ground_truth_dataset.json`**| Dataset | Official benchmark dataset containing 10 reference questions, expected tool selections, reference SQL queries, and expected answers. |
| **`extended_test_dataset.json`**| Dataset | Extended evaluation dataset containing 30 diverse financial questions spanning fund metadata, holdings, risk, performance, transactions, and exposure. |
| **`data/*.csv`** (9 files) | Seed Datasets | Raw financial datasets: `benchmarks.csv`, `historical_prices.csv`, `holdings.csv`, `portfolios.csv`, `portfolio_performance.csv`, `risk_metrics.csv`, `sectors.csv`, `securities.csv`, and `transactions.csv`. |
| **`requirements.txt`** | Dependency Config | Declares runtime dependencies: `streamlit`, `google-genai`, `python-dotenv`, `pydantic`, `pandas`, and testing utilities. |
| **`.streamlit/config.toml`** | Deployment Config | Streamlit server and theme configuration (headless execution, custom porting, institutional color palette). |
| **`.gitignore`** | Git Configuration | Excludes local virtual environments (`venv/`), environment secrets (`.env`), cached binaries (`__pycache__/`), and local SQLite database files (`portfolio.db`). |
| **`README.md`** | Project Overview | High-level repository documentation providing architecture overviews, installation guides, evaluation summaries, and usage limit details. |
| **`docs/PROJECT_DOCUMENTATION.md`** | Technical Documentation | In-depth technical specification (this document) covering system architecture, database design, file roles, and evaluation methodology. |
| **`docs/ORIGINAL_ASSIGNMENT.md`** | Assignment Reference | Original specifications and assignment prompt provided for the project. |

---

## 4. Database Schema and Storage

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

## 5. Implemented Features & Modules

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
- **Model Redundancy**: Configured with failover handling across `ACTIVE_MODELS`: `gemini-3.5-flash`, `gemini-3.1-flash-lite`, and `gemini-flash-latest`.
- **Structured Pydantic Schemas**: Enforces strongly-typed responses (`ToolDecision`, `SQLResponse`, `ReasoningResponse`).
- **Dynamic Reasoning**: Evaluates results to generate executive commentary and clear explanations for empty queries.

### D. Streamlit Web Interface (`app.py`)
- **Executive Styling**: Modern institutional styling with custom CSS, dark navy accents, and clear typography.
- **Interactive Information Popovers**: Informational popover buttons (`ℹ️`) on both the sidebar and near suggested queries explain the 10-query session limit.
- **Session State Management**: Keeps conversation history and usage state across runs without external database overhead.
- **Zero-Config Database Initialization**: Automatically builds `portfolio.db` from CSV datasets on cloud startup if the database file is absent.

---

## 6. Session Usage Limits & API Protection

To mitigate rapid exhaustion of shared API keys in public deployments, MarketVue implements client-side session guardrails:

- **10-Query Session Limit**: Users are limited to 10 AI-powered queries per Streamlit browser session.
- **Proactive Warnings**: A warning banner appears after 7 queries indicating remaining calls.
- **Graceful Blocking**: When the 10-query limit is reached, new AI inputs are paused while full access to dashboard statistics, portfolio dataset tables, and previously generated results is maintained.
- **Limitations**: This is an in-memory session-state control that prevents individual browser sessions from generating excessive API calls. It does not provide global multi-tenant quota management across independent concurrent visitors.

---

## 7. Verification and Evaluation Results

The application's analytical accuracy and software reliability have been benchmarked across both automated functional evaluations and offline test suites:

### Benchmark Summary
- **Official Benchmark (`evaluate.py`)**: **10/10 Passed (100% recorded accuracy)** covering natural-language SQL generation, CTE aggregations, and deterministic sector exposure.
- **Extended Evaluation (`evaluate_extended.py`)**: **26/30 Passed (86.7% recorded accuracy)** across 6 distinct quantitative portfolio research categories.
- **Reliability & Security Test Suite (`test_reliability.py`)**: **22/22 Tests Passing** (offline execution with mocked API calls), validating:
  - Error classification across quota exhaustion, authentication failures, network timeouts, and missing credentials.
  - Graceful degradation (preserving underlying database records and exposure calculations when reasoning is unavailable).
  - SQL security barriers (rejection of non-SELECT statements, multi-statements, and system catalog probing).
  - Session usage state counters and threshold enforcement (warning at 7 queries, blocking at 10 queries).

---

## 8. Setup and Execution

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
