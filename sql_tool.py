
import sqlite3
from pathlib import Path


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"

# Only these database tables can be queried.
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
PROGRESS_INTERVAL = 10000


# --------------------------------------------------
# SQL validation
# --------------------------------------------------

def remove_leading_comments(sql):
    """Remove whitespace and comments before the SQL command."""

    remaining = sql.lstrip()

    while remaining:

        if remaining.startswith("--"):
            newline = remaining.find("\n")

            if newline == -1:
                return ""

            remaining = remaining[newline + 1:].lstrip()

        elif remaining.startswith("/*"):
            comment_end = remaining.find("*/")

            if comment_end == -1:
                raise ValueError(
                    "SQL query contains an unfinished comment."
                )

            remaining = remaining[comment_end + 2:].lstrip()

        else:
            break

    return remaining


def validate_sql(sql):
    """Allow only one read-only SELECT or WITH query."""

    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL query cannot be empty.")

    if "\x00" in sql:
        raise ValueError("SQL query contains an invalid character.")

    remaining = remove_leading_comments(sql)

    if not remaining:
        raise ValueError("SQL query does not contain a command.")

    # Identify the first SQL keyword.
    first_keyword = remaining.split(None, 1)[0].upper()

    if first_keyword not in {"SELECT", "WITH"}:
        raise ValueError(
            "Only SELECT and WITH queries are allowed."
        )

    return True


# --------------------------------------------------
# SQLite authorizer
# --------------------------------------------------

def authorize_query(
    action,
    arg1,
    arg2,
    database_name,
    trigger_name
):
    """
    Restrict SQL operations to read-only queries
    against the approved database tables.
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

    # Restrict access to approved tables.
    if action == sqlite3.SQLITE_READ:

        table_name = (arg1 or "").lower()

        if table_name not in ALLOWED_TABLES:
            return sqlite3.SQLITE_DENY

    # Block potentially dangerous SQLite functions.
    if action == sqlite3.SQLITE_FUNCTION:

        function_name = (arg2 or arg1 or "").lower()

        blocked_functions = {
            "load_extension",
            "readfile",
            "writefile"
        }

        if function_name in blocked_functions:
            return sqlite3.SQLITE_DENY

    return sqlite3.SQLITE_OK


# --------------------------------------------------
# SQL execution
# --------------------------------------------------

def execute_sql(sql):
    """
    Validate and execute one read-only SQL query.

    Returns:
        success
        sql
        columns
        rows
        row_count
        truncated
        error
    """

    connection = None

    try:
        # Validate the SQL before connecting.
        validate_sql(sql)

        if not DB_PATH.is_file():
            raise FileNotFoundError(
                f"Database file not found: {DB_PATH}"
            )

        # Open the database in read-only mode.
        database_uri = DB_PATH.as_uri() + "?mode=ro"

        connection = sqlite3.connect(
            database_uri,
            uri=True
        )

        # Apply SQL operation restrictions.
        connection.set_authorizer(authorize_query)

        # Limit excessive query execution.
        progress_state = {"steps": 0}

        def query_progress():

            progress_state["steps"] += 1

            if progress_state["steps"] > MAX_QUERY_STEPS:
                return 1

            return 0

        connection.set_progress_handler(
            query_progress,
            PROGRESS_INTERVAL
        )

        # SQLite execute() accepts only one SQL statement.
        cursor = connection.execute(sql)

        columns = [
            description[0]
            for description in cursor.description or []
        ]

        # Fetch at most MAX_ROWS + 1 to detect truncation.
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

    except sqlite3.ProgrammingError as error:

        message = str(error)

        if "one statement at a time" in message.lower():
            message = "Multiple SQL statements are not allowed."

        return {
            "success": False,
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "error": message
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


# --------------------------------------------------
# Testing
# --------------------------------------------------

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
        ),
        (
            "Test rejected internal table access",
            "SELECT name FROM sqlite_master;"
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
