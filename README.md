# MarketView - Portfolio Analytics Agent

MarketView is an AI-powered portfolio analytics system that converts natural-language financial questions into secure SQL database queries and quantitative sector exposure calculations. It pairs structured data retrieval with dynamic financial reasoning to deliver clear, verifiable investment insights.

---

## Architecture & System Workflow

The application routes and processes user queries through a five-stage pipeline:

```
                          [ User Question ]
                                 |
                                 v
                     +-----------------------+
                     | Gemini Tool Router    |
                     | (select_tool)         |
                     +-----------------------+
                                 |
                 +---------------+---------------+
                 |                               |
                 v                               v
    [ exposure_calculator ]                   [ sql ]
                 |                               |
                 v                               v
    +-------------------------+     +-------------------------+
    | Exposure Calculator     |     | SQL Generation          |
    | - Identifies portfolio  |     | - Text-to-SQL via LLM   |
    | - Filters Stock assets  |     | - Schema constraints    |
    | - Aggregates by sector  |     +-------------------------+
    +-------------------------+                  |
                 |                               v
                 |                  +-------------------------+
                 |                  | SQL Execution Harness   |
                 |                  | - Read-only SQLite URI  |
                 |                  | - Authorizer hook       |
                 |                  | - Blocks DDL / DML      |
                 |                  +-------------------------+
                 |                               |
                 +---------------+---------------+
                                 |
                                 v
                     +-----------------------+
                     | Dynamic Reasoning     |
                     | Layer                 |
                     | - Contextualizes data |
                     | - Explains 0-matches  |
                     | - Distinguishes errors|
                     +-----------------------+
                                 |
                                 v
                     +-----------------------+
                     | Executive Presentation|
                     | (Streamlit UI / CLI)  |
                     +-----------------------+
```

---

## Core Components

### 1. Tool Router (`portfolio_agent.py`)
- Analyzes natural-language queries against available portfolio names.
- Routes queries to `sql` for database metrics, lookups, and comparisons, or to `exposure_calculator` for specific fund sector breakdowns.
- Flags out-of-scope requests (e.g., speculative future price predictions).

### 2. SQL Query Tool (`sql_tool.py`)
- Enforces strict read-only access using SQLite connection flags (`mode=ro`).
- Implements an authorizer callback that intercepts and rejects modification statements (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) and blocks internal schema catalog probing.
- Sets query execution step limits and handles row truncation at 1,000 records.

### 3. Sector Exposure Calculator (`exposure_calculator.py`)
- Calculates equity sector allocations for any designated portfolio.
- Excludes fixed-income holdings (bonds) to compute sector weights based strictly on equity assets (`asset_type = 'Stock'`).
- Returns holding-level audit evidence alongside sector aggregation percentages.

### 4. Dynamic Reasoning Layer (`portfolio_agent.py`)
- Dynamically interprets query outputs rather than displaying raw database rows.
- Explains the financial significance of aggregations, rankings, and comparisons.
- Identifies specific query conditions when zero records match, clarifying why data was not returned.
- Built-in multi-model failover (`gemini-3.5-flash`, `gemini-3.1-flash-lite`, `gemini-flash-latest`) ensures reliable uptime against free-tier API quotas.

### 5. Web Interface (`app.py`)
- Clean, institutional dashboard styled with an executive financial palette.
- Completely free of emojis and exposed credentials.
- Automatic database initialization ensures cloud deployments build the SQLite database directly from source CSV files if missing.

---

## Database Schema

The database (`portfolio.db`) is normalized across nine tables:

| Table | Description | Records |
|:---|:---|:---:|
| `portfolios` | Portfolio metadata, AUM, risk profile, benchmark symbol | 13 |
| `securities` | Equities and bonds, tickers, company names, current prices | 30 |
| `sectors` | GICS sector classifications and descriptions | 10 |
| `holdings` | Portfolio positions, quantities, purchase prices, weights, cost basis | 95 |
| `transactions` | Historical execution records (BUY/SELL), prices, dates | 24 |
| `historical_prices`| Daily OHLCV price history records | 330 |
| `portfolio_performance` | Monthly snapshots of NAV, multi-period returns, volatility, Sharpe ratio, drawdown | 44 |
| `risk_metrics` | Monthly risk figures: VaR (95/99), beta, S&P 500 correlation, tracking error | 44 |
| `benchmarks` | Benchmark index metadata and symbols | 13 |

---

## Quick Start

### 1. Installation
```bash
git clone https://github.com/guruchiwate06/PL_Capital_Project.git
cd PL_Capital_Project

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Setup
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Initialize Database
```bash
python database.py
```

### 4. Run the Application

**Web Dashboard (MarketView):**
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

**Command-Line Interface:**
```bash
python portfolio_agent.py
```

---

## Evaluation & Benchmark Results

The system was evaluated against two independent test suites:

### 1. Official Ground Truth Benchmark (10 Questions)
Tests baseline text-to-SQL generation, CTE joins, and exposure calculations.
```bash
python evaluate.py
```
- **Total Questions:** 10
- **Passed:** 10
- **Accuracy:** 100.00%

### 2. Extended Benchmark (30 Questions)
Tests edge cases across 6 analytical categories (Portfolio Info, Holdings, Sectors, Risk, Returns, Transactions).
```bash
python evaluate_extended.py
```
- **Total Questions:** 30
- **Passed:** 26
- **Accuracy:** 86.67% (Raw, unforced evaluation)

---

## Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io) and create a **New app**.
3. Set the main file path to `app.py`.
4. Add your API key in **Settings** > **Secrets**:
   ```toml
   GEMINI_API_KEY = "your-api-key"
   ```
5. Deploy. The application automatically initializes `portfolio.db` from source CSV files on first launch.

---

## Limitations

- **Benchmark Time Series:** The database tracks benchmark symbols and metadata, but does not contain historical price series for benchmarks. Alpha and outperformance calculations require adding historical benchmark price series.
- **Session Memory:** Conversation history is stored in Streamlit session state and clears upon browser reload.
