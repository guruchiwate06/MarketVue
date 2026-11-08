# MarketView - Portfolio Analytics Agent

MarketView is an AI-powered conversational portfolio analytics assistant. It translates natural language questions into secure SQL database queries and quantitative sector exposure calculations, presenting financial answers with executive reasoning.

---

## 1. About the Project

In investment management and equity research, analysts and portfolio managers constantly need to inspect fund holdings, risk metrics, asset allocations, and historical performance. Writing SQL queries manually takes time, and non-technical stakeholders often cannot write SQL at all.

MarketView solves this problem by allowing users to ask plain English questions about their portfolios. The agent determines whether to query the database using a security-hardened SQL engine or calculate sector exposures using an equity holding calculator, and returns both structured data and natural-language financial interpretations.

---

## 2. Why I Built It

I built this project as part of an AI Engineering take-home challenge for institutional investment research. The goal was to build a reliable, secure prototype that connects Large Language Models to local financial databases without hallucinating numbers or executing unsafe database commands.

The project demonstrates:
- How LLMs can act as intelligent database routers.
- How to enforce read-only database sandboxing to prevent SQL injection or data corruption.
- How to perform accurate mathematical aggregations for equity sector exposures.
- How to provide an executive reasoning layer that explains the financial context behind numbers.

---

## 3. How It Works

When a user asks a question, MarketView processes it through a five-stage pipeline:

1. **Tool Routing:** Google Gemini inspects the user question and the available portfolio names to decide which tool to call:
   - `sql`: for database lookups, aggregations, filtering, joins, rankings, and comparisons.
   - `exposure_calculator`: for calculating the sector breakdown of an individual portfolio.
   - `unsupported`: for questions outside financial portfolio data.
2. **SQL Generation (if SQL selected):** Gemini translates the question into a single read-only SQLite query adhering to the database schema.
3. **Execution & Security Validation:**
   - The query passes through `sql_tool.py`, which enforces a read-only SQLite connection (`?mode=ro`).
   - A SQLite authorizer callback blocks any modification commands (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) and prevents access to system catalogs.
4. **Sector Exposure Calculation (if Exposure Calculator selected):**
   - `exposure_calculator.py` extracts all holdings for the specified fund.
   - It filters out fixed-income holdings (bonds) to focus purely on equities (`Stock`).
   - It maps securities to GICS sectors and sums the weights to compute exact sector concentrations.
5. **Dynamic Reasoning & Presentation:**
   - A reasoning layer analyzes the returned records, explains the financial takeaways, and distinguishes valid zero-record results from errors.
   - Results are rendered in clean tabular form in the web interface and command-line interface.

---

## 4. Technologies Used

- **Python 3.11+**: Core programming language.
- **SQLite**: Local relational database engine holding 9 structured tables.
- **Google Gemini API (`google-genai` SDK)**: Powers tool routing, SQL generation, and dynamic financial reasoning with multi-model failover (`gemini-3.5-flash`, `gemini-3.1-flash-lite`, `gemini-flash-latest`).
- **Pydantic**: Enforces strict structured JSON schema validation on LLM responses.
- **Streamlit**: Powers the clean, institutional web dashboard (MarketView).
- **Pandas**: Used for tabular data formatting and CSV loading.
- **python-dotenv**: Manages local environment variables securely.

---

## 5. Database Architecture

The local database (`portfolio.db`) is structured into nine relational tables:

1. `portfolios`: 13 investment funds with names, inception dates, target risk levels, AUM, and benchmark symbols.
2. `securities`: 30 equities and bonds with tickers, company names, asset types, sector IDs, and current market prices.
3. `sectors`: 10 GICS industry sectors with descriptions.
4. `holdings`: 95 portfolio holding records linking funds to securities with quantities, purchase prices, current weights, and cost bases.
5. `transactions`: 24 trade execution logs recording BUY and SELL orders, prices, quantities, and execution dates.
6. `historical_prices`: 330 daily price records with open, high, low, close, and volume.
7. `portfolio_performance`: 44 monthly historical performance snapshots tracking NAV, total returns (1m, 3m, 6m, 1y), volatility, Sharpe ratio, and maximum drawdown.
8. `risk_metrics`: 44 monthly risk calculations including Value at Risk (VaR 95/99), beta, correlation to S&P 500, and tracking error.
9. `benchmarks`: Metadata for 13 market benchmark indices.

---

## 6. Project Files

- `app.py`: The single-page Streamlit web dashboard for MarketView.
- `portfolio_agent.py`: Core agent coordinator handling tool routing, SQL generation, dynamic reasoning, and terminal CLI.
- `sql_tool.py`: Secure SQL execution harness with authorizer hooks, execution step limits, and truncation handling.
- `exposure_calculator.py`: Sector exposure engine that calculates equity allocations and excludes bonds.
- `database.py`: Builds the SQLite database from CSV datasets and applies database indexes.
- `database_schema.sql`: DDL schema definitions and indexes for the 9 tables.
- `evaluate.py`: Official evaluation script testing the agent against the original 10 ground truth questions.
- `evaluate_extended.py`: Extended evaluation script testing 30 unseen questions across 6 analytical categories.
- `ground_truth_dataset.json`: Official benchmark dataset with 10 questions.
- `extended_test_dataset.json`: Extended benchmark dataset with 30 validated questions.
- `requirements.txt`: Python package dependencies.
- `.streamlit/config.toml`: Custom theme configuration for the MarketView web dashboard.
- `docs/PROJECT_DOCUMENTATION.md`: Comprehensive 16-section technical documentation.
- `docs/ORIGINAL_ASSIGNMENT.md`: Archived copy of the original take-home assignment brief.

---

## 7. Installation and Setup

### Prerequisites
- Python 3.10 or higher
- A Google Gemini API Key from Google AI Studio

### Step 1: Clone the Repository
```bash
git clone https://github.com/guruchiwate06/PL_Capital_Project.git
cd PL_Capital_Project
```

### Step 2: Create and Activate a Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Your API Key
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### Step 5: Build the Database
```bash
python database.py
```
This loads the CSV files into `portfolio.db` and applies all indexes.

---

## 8. How to Use

### A. Run the MarketView Web Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`. You can click on the suggested query pills or type your own natural language questions.

### B. Run the Terminal Command-Line Interface
```bash
python portfolio_agent.py
```
Type any question at the prompt or type `exit` to quit.

### Example Questions
- "What is the total AUM across all portfolios?"
- "Which sector has the highest exposure in Growth Equity Fund?"
- "Which portfolio has the highest recorded volatility?"
- "Show the five most recent transactions."
- "Which stocks are common across the highest number of portfolios?"
- "Compare the average beta and tracking error between Growth Equity Fund and Conservative Income Fund."

---

## 9. Testing and Evaluation

The project includes two independent evaluation benchmarks:

### Official 10-Question Benchmark
```bash
python evaluate.py
```
- **Total Questions:** 10
- **Passed:** 10
- **Failed:** 0
- **Accuracy:** 100.00%
- Covers SQL lookups, aggregations, multiple CTE joins, diversification ratios, and exposure calculator breakdowns.

### Extended 30-Question Benchmark
```bash
python evaluate_extended.py
```
- **Total Questions:** 30
- **Passed:** 26
- **Failed:** 4
- **Accuracy:** 86.67%
- Evaluates 6 categories: Portfolio Information, Holdings & Securities, Sector Exposure, Risk Analysis, Performance, and Transactions.

### Security and Tool Self-Tests
```bash
python sql_tool.py
python exposure_calculator.py
```
Confirms that read-only enforcement, CTE handling, and bond-exclusion filters function properly.

---

## 10. Deployment to Streamlit Community Cloud

1. Push your repository to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io).
3. Click **New app**, select your repository and `main` branch, and set the main file path to `app.py`.
4. Under **Settings** > **Secrets**, enter your Gemini API key:
   ```toml
   GEMINI_API_KEY = "your-actual-api-key"
   ```
5. Click **Deploy**. The application automatically initializes `portfolio.db` on first startup from the bundled CSV datasets if the database file is not present.

---

## 11. Current Limitations and Future Improvements

1. **Benchmark Time-Series:** The database schema tracks benchmark index names and symbols, but does not include daily historical benchmark price series. Historical outperformance relative to a benchmark cannot be computed without adding benchmark return data.
2. **Session-Scoped Memory:** Conversation history is stored in Streamlit session state and resets on a browser refresh. Adding persistent session storage (such as SQLite-backed conversation logs) could allow multi-session tracking.
3. **Multi-Turn Disambiguation:** If a user specifies an incomplete question without naming a fund, the router currently requests clarification. Future versions could leverage previous conversation context to infer the portfolio under discussion.
