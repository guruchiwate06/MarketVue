# Portfolio Analytics Agent: Comprehensive Project Documentation

---

## 1. What the Assignment Asked Us to Build

The objective of this assignment is to build a prototype AI agent called **Portfolio Analytics Agent**. 

In investment management and institutional research, financial analysts regularly query portfolio holdings, risk metrics, and asset allocations. Writing SQL queries by hand takes time, and non-technical staff often cannot write them at all.

The assignment specified four main deliverables:
1. **SQL Query Tool:** A Python tool that takes a natural language question, turns it into a SQL query, runs it against a local SQLite database, and returns the data safely.
2. **Exposure Calculator:** A Python tool that calculates the sector breakdown (percentage of total equity) for a specific portfolio. It must ignore bond holdings and only calculate percentages for stocks.
3. **Portfolio Agent:** A command-line program powered by Google Gemini that decides which of the two tools to use for a user's question, runs the tool, and displays the answer with evidence.
4. **Agent Evaluator:** A test script that runs 10 provided ground truth test questions against the agent, compares actual outputs with expected results, and computes an accuracy score.

---

## 2. Project Architecture and Data Flow

Here is how data flows through the application from the moment a user asks a question to the moment the answer is displayed:

```
                  +-------------------------+
                  | User enters question    |
                  +-------------------------+
                               |
                               v
                  +-------------------------+
                  | Gemini Tool Selection   |
                  | (select_tool)           |
                  +-------------------------+
                               |
              +----------------+----------------+
              |                                 |
              v                                 v
     [ exposure_calculator ]                 [ sql ]
              |                                 |
              v                                 v
+---------------------------+     +---------------------------+
| exposure_calculator.py    |     | Gemini SQL Generation     |
| - Looks up portfolio_name |     | (generate_sql)            |
| - Retrieves stock weights |     +---------------------------+
| - Groups by sector        |                   |
+---------------------------+                   v
              |                   +---------------------------+
              |                   | sql_tool.py               |
              |                   | - Pre-checks SELECT/WITH  |
              |                   | - Read-only SQLite URI    |
              |                   | - SQLite Authorizer hook  |
              |                   | - Step limit & row caps   |
              |                   +---------------------------+
              |                                 |
              +----------------+----------------+
                               |
                               v
                  +-------------------------+
                  | format_response()       |
                  | Formats Markdown table  |
                  | and evidence (SQL, etc.)|
                  +-------------------------+
                               |
                               v
                  +-------------------------+
                  | Display to User         |
                  +-------------------------+
```

---

## 3. Database Creation and Data Storage (`database.py` & `database_schema.sql`)

### How the Database Is Built
The database is built from nine CSV files in the `data/` folder. Running `python database.py` performs the following steps:
1. Opens a connection to `portfolio.db`.
2. Creates nine tables using `CREATE TABLE IF NOT EXISTS`.
3. Reads `database_schema.sql` and creates indices for primary lookups (symbols, sectors, asset types) and join keys (portfolio_id, security_id, dates).
4. Opens an explicit database transaction (`connection.execute("BEGIN")`).
5. Clears any existing records (`DELETE FROM <table>`) so data can be cleanly refreshed.
6. Reads each CSV file using Python's `csv.DictReader`.
7. Compares CSV column headers against the database columns using SQLite's `PRAGMA table_info(table_name)`. If a column is missing or misspelled, loading halts immediately to prevent corrupted data.
8. Inserts rows in batches using `connection.executemany(...)`.
9. Commits the transaction if all tables load without error; if an error occurs, it rolls back changes (`connection.rollback()`).

### The Nine Tables and Their Record Counts

| Table Name | Records | Description | Primary Key | Key Foreign Keys |
|---|---|---|---|---|
| `benchmarks` | 13 | Market indices (e.g., S&P 500, MSCI World) | `benchmark_id` | None |
| `historical_prices`| 330 | Daily stock price records (OHLCV) | `price_id` | `security_id` |
| `holdings` | 95 | Holdings per portfolio (shares, price, cost basis, weight) | `holding_id` | `portfolio_id`, `security_id` |
| `portfolios` | 13 | Managed funds (name, strategy, target risk, AUM) | `portfolio_id` | None |
| `portfolio_performance` | 44 | Historical fund returns (1m, 3m, 6m, 1y), NAV, volatility, Sharpe ratio | `performance_id` | `portfolio_id` |
| `risk_metrics` | 44 | Risk analytics (VaR 95/99, CVaR 95, Beta, Sortino ratio) | `risk_id` | `portfolio_id` |
| `sectors` | 10 | GICS Industry sectors (Technology, Healthcare, etc.) | `sector_id` | None |
| `securities` | 30 | Stocks and bonds (symbol, company name, asset type, price) | `security_id` | `sector_id` |
| `transactions` | 24 | Buy and sell trade activity | `transaction_id` | `portfolio_id`, `security_id` |

---

## 4. SQL Tool Implementation (`sql_tool.py`)

The SQL tool executes read-only SQL queries safely. Because language models can sometimes generate unintended or unsafe commands, multiple layers of defense are implemented:

### Security Layers
1. **Read-Only Database Connection:**
   The connection is opened using a SQLite URI with read-only mode:
   ```python
   database_uri = DB_PATH.as_uri() + "?mode=ro"
   connection = sqlite3.connect(database_uri, uri=True)
   ```
2. **Command Validation (`validate_sql`):**
   Before running anything, the query text is cleaned of leading whitespace and comments (`--` or `/* */`). The very first keyword must be `SELECT` or `WITH`. Commands starting with `DELETE`, `DROP`, `UPDATE`, `INSERT`, `ALTER`, or `PRAGMA` are rejected immediately.
3. **SQLite Authorizer Hook (`set_authorizer`):**
   SQLite provides a callback mechanism that runs before any low-level action is executed.
   - Operations outside `SQLITE_SELECT`, `SQLITE_READ`, and `SQLITE_FUNCTION` are denied.
   - Any attempt to read tables outside `ALLOWED_TABLES` (such as SQLite's internal table `sqlite_master`) is blocked with `SQLITE_DENY`.
   - Dangerous SQLite functions like `load_extension`, `readfile`, and `writefile` are denied.
4. **Execution Step Limit (`set_progress_handler`):**
   To protect against queries that accidentally run infinite loops or huge Cartesian joins, `set_progress_handler` monitors execution steps and cancels the query if it exceeds 50 progress intervals.
5. **Output Pagination Limit:**
   The tool fetches at most `MAX_ROWS + 1` (where `MAX_ROWS = 1000`). If more than 1000 rows are returned, it truncates the result to 1000 rows and sets `"truncated": True`.

---

## 5. Exposure Calculator Implementation (`exposure_calculator.py`)

The Exposure Calculator is a specialized deterministic calculation tool. It does not use LLM generation to compute numbers; it uses Python and parameterized SQL to guarantee accurate math.

### How It Works
1. Accepts a portfolio name (for example, `"Tech Innovation Fund"`).
2. Runs a parameterized lookup query to get `portfolio_id`:
   ```sql
   SELECT portfolio_id, portfolio_name FROM portfolios WHERE portfolio_name = ?
   ```
3. Retrieves all equity holdings for that portfolio:
   ```sql
   SELECT
       h.holding_id,
       s.symbol,
       s.company_name,
       COALESCE(sec.sector_name, 'Unclassified') AS sector,
       h.quantity,
       h.current_weight
   FROM holdings h
   JOIN securities s ON h.security_id = s.security_id
   LEFT JOIN sectors sec ON s.sector_id = sec.sector_id
   WHERE h.portfolio_id = ?
     AND s.asset_type = 'Stock'
   ORDER BY h.holding_id
   ```
4. **Filtering Rule:** `s.asset_type = 'Stock'` strictly excludes bonds.
5. **Grouping Weights:** Loops through the rows and sums `current_weight` by sector:
   ```python
   exposure = {}
   for row in rows:
       sector = row[3]
       weight = float(row[5]) if row[5] is not None else 0.0
       exposure[sector] = exposure.get(sector, 0.0) + weight
   ```
6. Returns the sector breakdown dictionary, total equity weight, raw holding records, and the exact SQL query used as evidence.

---

## 6. The Gemini Portfolio Agent (`portfolio_agent.py`)

The agent coordinates user interaction, tool selection, and SQL generation using the official `google-genai` SDK and Pydantic.

### Structured Response Models
To prevent the model from returning unstructured conversational text that would break parsing, Pydantic models are passed to Gemini using `response_schema`:

```python
class ToolDecision(BaseModel):
    tool: Literal["sql", "exposure_calculator", "unsupported"]
    portfolio_name: Optional[str] = None
    reason: str = ""

class SQLResponse(BaseModel):
    sql: str
```

### Tool Routing (`select_tool`)
When a question arrives:
1. The agent reads the exact list of available portfolio names directly from SQLite (`SELECT portfolio_name FROM portfolios`).
2. It sends the question and the portfolio name list to Gemini.
3. Gemini matches the user's intent:
   - If the user asks for sector exposure of a fund, it returns `tool: "exposure_calculator"` and extracts the exact portfolio name (even if the user typed an informal version, like `"international equity"` -> `"International Equity Fund"`).
   - If the question asks for database values, counts, or comparisons, it returns `tool: "sql"`.
   - If unrelated, it returns `tool: "unsupported"`.

### SQL Generation (`generate_sql`)
When `sql` is selected:
1. Gemini is given the full database table definitions and specific portfolio analytics rules (e.g., how to calculate market value, how to join holdings with securities and sectors).
2. Temperature is set to `0` for consistent, deterministic outputs.
3. The generated SQL is returned in `SQLResponse.sql`.

### Response Formatting (`format_response`)
The agent converts raw tool outputs into clean Markdown:
- Single numbers are displayed as `Result: <value>`.
- Lists of values are numbered.
- Multi-column tables are rendered as Markdown tables.
- Sector exposure results show a table of percentages, total equity weight, and the underlying holding rows as audit evidence.

---

## 7. Important Calculations Explained

### A. Sector Exposure Percentage
- **Purpose:** Measures what fraction of a fund's equity is invested in a specific sector.
- **Formula:**
  $$\text{Sector Exposure} = \sum_{i \in \text{Holdings of Sector}} \text{current\_weight}_i$$
- **Example:** In the "Tech Innovation Fund", holdings are AAPL (0.15), MSFT (0.18), GOOGL (0.12), NVDA (0.15), AVGO (0.08), CRM (0.12), ORCL (0.10), and META (0.10).
  $$\text{Total Technology Exposure} = 0.15 + 0.18 + 0.12 + 0.15 + 0.08 + 0.12 + 0.10 + 0.10 = 1.00\ (100\%)$$

### B. Holding Market Value
- **Formula:**
  $$\text{Market Value} = \text{quantity} \times \text{current\_price}$$

### C. Total Portfolio Value
- **Formula:**
  $$\text{Total Portfolio Value} = \sum (\text{quantity} \times \text{current\_price})$$

### D. Diversification Ratio
- **Purpose:** Measures how diversified a portfolio's stock holdings are across different sectors.
- **Formula:**
  $$\text{Diversification Ratio} = \frac{\text{Number of Unique Sectors}}{\text{Total Number of Holdings}}$$
- **Example:** A portfolio with 12 holdings across 6 sectors has a diversification ratio of:
  $$\frac{6}{12} = 0.50$$

---

## 8. Evaluator and Testing Methodology (`evaluate.py`)

The evaluator verifies agent correctness by comparing agent outputs against expected ground truth.

### How `evaluate.py` Works:
1. Loads 10 test cases from `ground_truth_dataset.json`.
2. For SQL questions:
   - Runs the reference SQL query against `portfolio.db` to get the baseline columns and rows.
   - Runs the agent with the question.
   - Compares the agent's columns and rows with the reference output using `compare_results()`.
3. For Exposure questions:
   - Calculates the expected sector exposure directly from SQLite using a reference SQL query.
   - Runs the agent to get `sector_exposure`.
   - Checks that sector names and numeric weights match.
4. **Tolerance Handling:** Numeric comparisons use `math.isclose(rel_tol=1e-4, abs_tol=1e-6)` so minor rounding differences (e.g., 84.67 vs 84.6666) do not trigger false failures.
5. **Order Sensitivity:** If the question contains ordering keywords (`"top"`, `"highest"`, `"lowest"`, `"descending"`), row order is strictly enforced. For unordered queries, rows are sorted before comparison.
6. **Request Pacing:** A 5-second pause (`time.sleep(5)`) between questions prevents exceeding Gemini's free-tier rate limits.

---

## 9. Current Evaluation Results and Analysis

In our live testing of the local project, the evaluator produced the following results:

```
========== EVALUATION SUMMARY ==========
Total questions: 10
Passed: 7
Failed: 3
Agent errors: 0
Reference errors: 0
Skipped: 0
Agent accuracy: 70.00%
========================================
```

### Analysis of the 3 Failing Questions

Being transparent about what passes and what fails is critical in quantitative software engineering:

1. **Question 5 (Top 5 holdings by cost basis in Growth Equity Fund):**
   - **What happened:** The agent retrieved the exact 5 holdings (AAPL, AMZN, MSFT, NVDA, CRM) in the correct descending order.
   - **Why it failed:** The reference query selected `holding_id, symbol, company_name, quantity, cost_basis`. The agent's generated SQL selected `symbol, company_name, quantity, purchase_price, cost_basis`. Because column 1 was `symbol` instead of `holding_id`, the evaluator failed on value comparison.
2. **Question 7 (Technology sector value and percentage for each portfolio):**
   - **What happened:** The agent returned 13 portfolios, whereas the reference query returned 8.
   - **Why it failed:** In `portfolio_agent.py`, an instruction tells the model not to silently exclude portfolios with zero exposure. Therefore, the agent used a `LEFT JOIN` and included funds with 0% technology holdings. The reference query used an `INNER JOIN`, including only funds that actually hold technology stocks. Furthermore, the agent omitted the total portfolio value column.
3. **Question 8 (Portfolios with holdings in >5 sectors and diversification metrics):**
   - **What happened:** The agent correctly identified the single matching portfolio (`Total Stock Market Index Fund`), calculated 6 sectors, 12 holdings, and a ratio of 0.5.
   - **Why it failed:** The agent included an extra column `portfolio_id` (`portfolio_id, portfolio_name, sector_count, total_holdings, diversification_ratio`). Because the reference query only expected 4 columns, the evaluator failed on column count mismatch (5 vs 4).

---

## 10. Problems Faced and How They Were Solved

During the project lifecycle, several technical hurdles were identified and addressed:

1. **Gemini Free-Tier Rate Limits (HTTP 429 Errors):**
   - *Problem:* Running all 10 questions in a fast loop made 18 API calls in under 20 seconds, causing HTTP 429 "Resource Exhausted" errors on Questions 9 and 10.
   - *Fix:* Added a 5-second sleep interval (`time.sleep(5)`) between evaluation runs in `evaluate.py`.
2. **Portfolio Name Mismatches in Tool Selection:**
   - *Problem:* The user might ask for `"international equity"` while the database table has `"International Equity Fund"`.
   - *Fix:* `select_tool()` dynamically queries `SELECT portfolio_name FROM portfolios` and injects the valid list directly into Gemini's system prompt, instructing it to map informal names to the exact database name.
3. **Database Security Against Destructive Queries:**
   - *Problem:* A simple text-to-SQL prompt could generate `UPDATE`, `DROP`, or multiple queries separated by semicolons.
   - *Fix:* Combined read-only SQLite URI (`?mode=ro`), keyword validation (`SELECT` / `WITH`), an authorizer hook blocking unauthorized tables, and step counters.
4. **Floating Point Rounding in Evaluations:**
   - *Problem:* Minor differences in decimal places between SQL `ROUND()` and Python floats caused tests to fail.
   - *Fix:* Used `math.isclose()` with relative and absolute tolerances in `evaluate.py`.

---

## 11. Current Limitations and Future Improvements

### Current Limitations
1. **Column Alignment Sensitivity:** The agent occasionally selects different supporting columns (such as including `portfolio_id` or `purchase_price`), which causes evaluator failures even when the core financial insight is correct.
2. **Single-Portfolio Tool Execution:** The exposure calculator is designed to take one portfolio name at a time. It cannot handle questions like *"Compare the sector exposure of Fund A and Fund B"* in a single tool invocation.
3. **Single-Turn Interaction:** The agent does not maintain a conversation memory across multiple questions. Each question is treated independently.

### Future Improvements
1. **SQL Prompt Calibration:** Refine the prompt rules in `portfolio_agent.py` to specify standard entity identification columns (e.g., omitting surrogate primary keys like `portfolio_id` when fund names are displayed).
2. **API Retry with Exponential Backoff:** Add automatic retries in `call_gemini` to gracefully handle transient network pauses or API rate spikes.
3. **Multi-Portfolio Comparison:** Extend `exposure_calculator.py` to accept a list of portfolio names and return side-by-side sector allocation tables.

---

## 12. Detailed Code Changes Across Project Tools

This section documents all technical changes and enhancements made across each tool in the project:

### A. Exposure Calculator (`exposure_calculator.py`)
- **Input Validation:** Added checks for valid, non-empty portfolio name strings.
- **Read-Only SQLite URI:** Changed database connection string to `portfolio.db?mode=ro` to guarantee safety at the connection level.
- **Stock-Only Filtering:** Added `AND s.asset_type = 'Stock'` to explicitly ignore bond securities as requested by the assignment.
- **Unclassified Sector Handling:** Added `COALESCE(sec.sector_name, 'Unclassified')` so holdings without assigned sectors do not raise null-pointer exceptions.
- **Weight Accumulation:** Accumulated `current_weight` into each sector without artificial normalization, preserving true equity weights.
- **Audit Evidence Output:** Returned raw holding records (holding_id, symbol, company name, quantity, current weight) along with the exact SQL query and parameters used.
- **Standalone Self-Tests:** Added an executable `if __name__ == "__main__":` block to verify calculations directly against the "Tech Innovation Fund".

### B. SQL Tool (`sql_tool.py`)
- **Comment-Safe Validation:** Created `remove_leading_comments()` to strip out single-line (`--`) and multi-line (`/* */`) comments before checking SQL keywords.
- **Command Restricting:** Restricts execution strictly to read-only `SELECT` and `WITH` statements.
- **SQLite Authorizer Hook:** Implemented `authorize_query()` callback:
  - Permits only `SQLITE_SELECT`, `SQLITE_READ`, and `SQLITE_FUNCTION`.
  - Enforces `ALLOWED_TABLES` whitelist (9 project tables). Blocks internal SQLite tables such as `sqlite_master`.
  - Blocks dangerous extension and file functions (`load_extension`, `readfile`, `writefile`).
- **Query Step Limiting:** Uses `set_progress_handler` with a step counter to cancel queries if they run longer than permitted intervals.
- **Truncation Detection:** Limits result rows to `MAX_ROWS = 1000` and sets `"truncated": True` when more rows exist.
- **Standalone Self-Tests:** Included test cases for SELECT, CTE queries, rejected DELETE operations, rejected multiple statements, and rejected access to internal catalogs.

### C. Portfolio Agent (`portfolio_agent.py`)
- **Modern SDK Integration:** Uses Google's official `google-genai` SDK and `gemini-3.5-flash-lite`.
- **Pydantic Response Schemas:** Defined `ToolDecision` and `SQLResponse` Pydantic models so Gemini returns structured JSON rather than arbitrary text.
- **Dynamic Database Lookup for Tool Selection:** `select_tool()` dynamically queries `SELECT portfolio_name FROM portfolios` and injects the valid portfolio names into the prompt to resolve informal names (e.g. "international equity" -> "International Equity Fund").
- **Financial SQL Generation Rules:** Added schema definitions and domain calculation rules (how to compute market values, average prices by sector, top holdings by cost basis, diversification metrics).
- **Result Formatting:** Implemented `format_response()`, `format_table()`, and `format_records()` to render query results, sector percentages, and SQL evidence into clean Markdown tables.
- **CLI Interactive Loop:** Provided a continuous command-line loop where users can type questions and receive formatted answers.

### D. Evaluator (`evaluate.py`)
- **Ground Truth Loading:** Reads the 10 reference test questions from `ground_truth_dataset.json`.
- **Dynamic Reference Execution:** Runs expected reference SQL and expected sector calculations on the fly directly against `portfolio.db`.
- **Tolerance-Aware Float Comparison:** Compares numerical values with `math.isclose()` (`rel_tol=1e-4`, `abs_tol=1e-6`) to prevent false failures from floating point rounding.
- **Smart Order Preservation:** Detects ordering keywords (`"top"`, `"highest"`, `"lowest"`, `"descending"`) to enforce exact row order only when ranking is requested.
- **API Rate-Limit Protection:** Added `time.sleep(5)` between test cases to prevent HTTP 429 rate limit errors on Gemini free-tier quotas.

---

## 13. Setup, Installation, and How to Run

### Installation
1. Activate virtual environment:
   ```bash
   venv\Scripts\activate
   ```
2. Install required packages:
   ```bash
   pip install google-genai python-dotenv pydantic
   ```
3. Set your API key in `.env`:
   ```env
   GEMINI_API_KEY=your_key_here
   ```
4. Build the database:
   ```bash
   python database.py
   ```

### Running the Agent CLI
```bash
python portfolio_agent.py
```

### Running the Evaluation Suite
```bash
python evaluate.py
```


