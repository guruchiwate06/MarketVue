# MarketVue - Portfolio Analytics Agent

MarketVue is an AI-powered portfolio analytics agent that translates natural-language financial questions into read-only SQL queries and deterministic sector exposure calculations. It combines structured SQLite data retrieval with a dynamic reasoning layer to deliver clear, verifiable analytical responses.

---

## System Architecture & Workflow

The agent processes incoming queries through a five-stage pipeline:

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
                  (MarketVue UI / Terminal)
```

### Execution Flow

1. **Query Routing**: The Gemini Tool Router evaluates user intent. Questions requesting portfolio sector breakdowns route to the Exposure Calculator; general analytical queries, comparisons, and database lookups route to the SQL Query Tool.
2. **Deterministic Exposure Calculation**: Fund sector weights are computed programmatically using predefined equity-weighting logic (`asset_type = 'Stock'`), eliminating SQL generation errors for sector allocations.
3. **Safe SQL Execution**: Queries run against SQLite using a read-only URI (`?mode=ro`) and an authorizer hook that blocks write operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`) and internal table probing.
4. **Dynamic Reasoning**: A dedicated Gemini reasoning pass interprets query results, contextualizes financial metrics, explains conditions when zero records match, and separates SQL execution errors from empty datasets.
5. **Presentation**: Results, generated SQL, execution metadata, and reasoning are presented cleanly through the MarketVue web dashboard or command line.

---

## Core Components

- **`portfolio_agent.py`**: Primary orchestrator. Implements query routing, multi-model failover (`gemini-3.5-flash`, `gemini-3.1-flash-lite`, `gemini-flash-latest`), and dynamic reasoning generation.
- **`sql_tool.py`**: Secure SQLite execution harness with read-only connection limits, step execution boundaries, and authorizer callbacks.
- **`exposure_calculator.py`**: Deterministic calculator for portfolio sector allocations. Filters out fixed-income assets and returns position-level audit logs.
- **`database.py`**: Database initialization script that loads and normalizes raw CSV datasets into indexed SQLite tables.
- **`app.py`**: Streamlit web interface with suggested analytical queries, technical detail expanders, session history, and session query limits (10 queries/session).

---

## Database Schema

The SQLite database (`portfolio.db`) is structured across nine tables:

| Table | Description |
|:---|:---|
| `portfolios` | Portfolio metadata, strategy type, and AUM |
| `securities` | Equities and bonds, tickers, and current prices |
| `sectors` | GICS industry sector classifications |
| `holdings` | Portfolio positions, quantities, and cost basis |
| `transactions` | Historical buy and sell trade records |
| `historical_prices`| Daily OHLCV price histories |
| `portfolio_performance` | Monthly returns, Sharpe ratios, volatility, and drawdowns |
| `risk_metrics` | Monthly VaR (95/99), beta, correlation, and tracking error |
| `benchmarks` | Benchmark indices and tracking metadata |

---

## Getting Started

### 1. Installation

```bash
git clone https://github.com/guruchiwate06/MarketVue.git
cd MarketVue

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the root directory:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Initialize Database

```bash
python database.py
```

### 4. Run the Application

**Web Dashboard (MarketVue):**
```bash
streamlit run app.py
```

**Command-Line Interface:**
```bash
python portfolio_agent.py
```

---

## Evaluation & Testing Summary

The system's capabilities have been tested across both functional benchmark datasets and offline unit/reliability test suites:

- **Official Benchmark (10 questions)**: 10/10 passed (100% recorded accuracy across basic and intermediate SQL & exposure routing).
- **Extended Test Suite (30 questions)**: 26/30 passed (86.67% recorded accuracy across 6 analytical categories).
- **Offline Reliability Test Suite (22 unit tests)**: 22/22 tests passing in `test_reliability.py`, validating:
  - Error classification across quota exhaustion, authentication failures, network timeouts, and missing API keys.
  - Non-destructive failure isolation (preserving SQL results and deterministic sector exposure when dynamic reasoning is paused).
  - SQL security barriers (prohibiting DML/DDL modifications, blocking `sqlite_master` probes, rejecting multi-statement queries).
  - Session question limit counters (threshold warning at 7 queries, blocking at 10 queries).

Run the tests:
```bash
# Offline reliability and security suite (zero API calls)
python -m unittest test_reliability.py

# Benchmark evaluation scripts (require active Gemini API credentials)
python evaluate.py
python evaluate_extended.py
```

---

## Session Usage Limits & API Protection

Because MarketVue is deployed as a publicly accessible demonstration application sharing a common API credential, a per-session limit is enforced:

- **Per-Session Limit**: Maximum of 10 AI-powered queries per Streamlit browser session.
- **Warning Threshold**: A warning notice appears after question 7, displaying remaining queries.
- **Graceful Blocking**: After question 10, new AI queries are paused. Users retain full access to dashboard metrics, dataset tables, and previously answered query results.
- **Scope & Limitations**: This limit is an in-memory session-state control designed to prevent runaway automated loops from a single client. It is not a global quota management system and does not protect against concurrent usage across separate independent sessions.
