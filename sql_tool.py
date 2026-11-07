
import sqlite3
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"

# Tables that the agent is allowed to query.
ALLOWED_TABLES = {
    "benchmarks",
    "historical_prices",
    "holdings",
    "portfolios",
    "portfolio_performance",
    "risk_metrics",
    "sectors",
    "securities",
    "transactions"
}

MAX_ROWS = 1000
MAX_QUERY_STEPS = 50


def validate_sql(sql):
    """
    Check that the supplied query is a single,
    read-only SELECT or WITH query.
    """

    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL query cannot be empty.")

    if "\x00" in sql:
        raise ValueError("SQL query contains an invalid character.")

    # Skip comments at the beginning to identify
    # the actual first SQL keyword.
    remaining = sql.lstrip()

    while True:
        if remaining.startswith("--"):
            newline = remaining.find("\n")

            if newline == -1:
                remaining = ""
            else:
                remaining = remaining[newline + 1:].lstrip()

        elif remaining.startswith("/*"):
            comment_end = remaining.find("*/")

            if comment_end == -1:
                raise ValueError("SQL query contains an unfinished comment.")

            remaining = remaining[comment_end + 2:].lstrip()

        else:
            break

    match = re.match(r"[A-Za-z]+", remaining)

    if not match:
        raise ValueError("Unable to identify the SQL command.")

    first_keyword = match.group().upper()

    if first_keyword not in {"SELECT", "WITH"}:
        raise ValueError(
            "Only SELECT and WITH queries are allowed."
        )

    return True


def authorize_query(action, arg1, arg2, database_name, trigger_name):
    """
    SQLite authorizer provides an additional security layer.
    It allows reading approved tables but blocks modifications.
    """

    allowed_actions = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION
    }

    if hasattr(sqlite3, "SQLITE_RECURSIVE"):
        allowed_actions.add(sqlite3.SQLITE_RECURSIVE)

    if action not in allowed_actions:
        return sqlite3.SQLITE_DENY

    # Prevent access to tables outside our dataset.
    if action == sqlite3.SQLITE_READ:
        if arg1 not in ALLOWED_TABLES:
            return sqlite3.SQLITE_DENY

    # Block potentially dangerous extension or file functions.
    if action == sqlite3.SQLITE_FUNCTION:
        function_name = (arg2 or arg1 or "").lower()

        if function_name in {
            "load_extension",
            "readfile",
            "writefile"
        }:
            return sqlite3.SQLITE_DENY

    return sqlite3.SQLITE_OK


def execute_sql(sql):
    """
    Validate and execute a read-only SQL query.

    Returns the SQL, column names, result rows,
    row count and execution status.
    """

    connection = None

    try:
        # Validate before opening the database.
        validate_sql(sql)

        if not DB_PATH.is_file():
            raise FileNotFoundError(
                f"Database file not found: {DB_PATH}"
            )

        # Open SQLite in read-only mode.
        database_uri = f"{DB_PATH.as_uri()}?mode=ro"

        connection = sqlite3.connect(
            database_uri,
            uri=True
        )

        # Enable SQLite's query-level security checks.
        connection.set_authorizer(authorize_query)

        # Stop queries that consume excessive SQLite execution steps.
        progress_state = {"steps": 0}

        def query_progress():
            progress_state["steps"] += 1

            if progress_state["steps"] > MAX_QUERY_STEPS:
                return 1

            return 0

        connection.set_progress_handler(
            query_progress,
            10000
        )

        # Execute exactly one SQL statement.
        cursor = connection.execute(sql)

        columns = [
            description[0]
            for description in cursor.description or []
        ]

        # Retrieve at most MAX_ROWS + 1 to detect truncation.
        fetched_rows = cursor.fetchmany(MAX_ROWS + 1)

        truncated = len(fetched_rows) > MAX_ROWS
        rows = fetched_rows[:MAX_ROWS]

        return {
            "success": True,
            "sql": sql,
            "columns": columns,
            "rows": [list(row) for row in rows],
            "row_count": len(rows),
            "truncated": truncated,
            "error": None
        }

    except ValueError as error:
        return {
            "success": False,
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "error": str(error)
        }

    except FileNotFoundError as error:
        return {
            "success": False,
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "error": str(error)
        }

    except sqlite3.Error as error:
        return {
            "success": False,
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "error": f"Database query failed: {error}"
        }

    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":

    test_queries = [
        (
            "Count portfolios",
            "SELECT COUNT(*) FROM portfolios;"
        ),
        (
            "List active portfolios",
            """
            SELECT portfolio_name
            FROM portfolios
            WHERE status = 'Active';
            """
        ),
        (
            "Test CTE query",
            """
            WITH portfolio_count AS (
                SELECT COUNT(*) AS total
                FROM portfolios
            )
            SELECT total
            FROM portfolio_count;
            """
        ),
        (
            "Test rejected modification",
            "DELETE FROM portfolios;"
        ),
        (
            "Test rejected multiple statements",
            "SELECT COUNT(*) FROM portfolios; SELECT * FROM holdings;"
        )
    ]

    for test_name, query in test_queries:

        print(f"\nTEST: {test_name}")
        print("-" * 45)

        result = execute_sql(query)

        if result["success"]:
            print("Status: SUCCESS")
            print("Columns:", result["columns"])
            print("Rows:", result["rows"])
            print("Row count:", result["row_count"])

            if result["truncated"]:
                print("Warning: Results were limited.")

        else:
            print("Status: REJECTED / FAILED")
            print("Reason:", result["error"])
