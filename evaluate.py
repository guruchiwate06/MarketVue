
import json
import sqlite3
import math
from pathlib import Path
import time

from portfolio_agent import run_agent


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"
GROUND_TRUTH_PATH = BASE_DIR / "ground_truth_dataset.json"


def load_test_cases():
    """Load questions from the ground truth file."""

    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError("Ground truth file not found.")

    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    questions = data.get("questions")

    if not isinstance(questions, list):
        raise ValueError("Invalid ground truth format.")

    return questions


def get_connection():
    """Connect to the database in read-only mode."""

    if not DB_PATH.exists():
        raise FileNotFoundError("Database not found.")

    db_uri = DB_PATH.as_uri() + "?mode=ro"

    return sqlite3.connect(db_uri, uri=True)


def execute_reference_sql(sql_query):
    """Run the expected SQL query."""

    connection = get_connection()

    try:
        cursor = connection.cursor()
        cursor.execute(sql_query)

        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()

        return {
            "columns": columns,
            "rows": rows
        }

    finally:
        connection.close()


def compare_values(actual, expected, tolerance=1e-4):
    """Compare two values, allowing small differences in numbers."""

    if actual is None or expected is None:
        return actual is expected

    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(
            float(actual),
            float(expected),
            rel_tol=tolerance,
            abs_tol=1e-6
        )

    return str(actual).strip() == str(expected).strip()


def normalize_column_name(name):
    """Normalize column name by removing table prefixes and lowercase."""
    cleaned = str(name).strip().lower()
    if "." in cleaned:
        cleaned = cleaned.split(".")[-1]
    cleaned = cleaned.strip("`'\"[]")
    return cleaned


def column_names_match(actual_col, expected_col):
    """Check if actual column name matches expected column name or a valid alias."""
    a = normalize_column_name(actual_col)
    e = normalize_column_name(expected_col)

    if a == e:
        return True

    # Standard aggregation expression aliases
    if e == "count(*)" and a in {"count(*)", "count", "total", "total_count", "total_portfolios", "portfolio_count"}:
        return True
    if e == "sum(total_aum)" and a in {"sum(total_aum)", "total_aum", "sum_total_aum", "sum_aum"}:
        return True

    # Common metrics aliases
    if ("avg" in e or "average" in e) and "price" in e:
        if ("avg" in a or "average" in a) and "price" in a:
            return True
    if e == "tech_percentage" and a in {"tech_percentage", "percentage", "tech_pct", "technology_percentage"}:
        return True
    if e == "tech_value" and a in {"tech_value", "tech_sector_value", "technology_sector_value"}:
        return True

    return False


def row_sort_key(row):
    """
    Sort key that preserves numeric values as numbers and text as lowercase strings.
    Prevents string-sorting bugs (e.g., '10' sorting before '2').
    """
    key = []
    for item in row:
        if item is None:
            key.append((0, 0.0, ""))
        elif isinstance(item, (int, float)):
            key.append((1, float(item), ""))
        else:
            key.append((2, 0.0, str(item).strip().lower()))
    return tuple(key)


def compare_results(actual, expected, preserve_order=False):
    """Compare the results returned by the agent and reference query."""

    actual_columns = actual["columns"]
    expected_columns = expected["columns"]

    actual_rows = actual["rows"]
    expected_rows = expected["rows"]

    # 1. Compare column count
    if len(actual_columns) != len(expected_columns):
        return False, f"Column count mismatch: expected {len(expected_columns)} ({expected_columns}), got {len(actual_columns)} ({actual_columns})"

    # 2. Compare column names and order
    for idx, (act_col, exp_col) in enumerate(zip(actual_columns, expected_columns)):
        if not column_names_match(act_col, exp_col):
            return False, f"Column {idx + 1} name mismatch: expected '{exp_col}', got '{act_col}'"

    # 3. Compare row count
    if len(actual_rows) != len(expected_rows):
        return False, f"Row count mismatch: expected {len(expected_rows)} rows, got {len(actual_rows)} rows"

    # 4. Compare row order and values
    if preserve_order:
        rows = list(zip(actual_rows, expected_rows))
    else:
        # Use value-aware numeric/string sort key instead of string-based sorting
        sorted_actual = sorted(actual_rows, key=row_sort_key)
        sorted_expected = sorted(expected_rows, key=row_sort_key)
        rows = list(zip(sorted_actual, sorted_expected))

    for row_idx, (actual_row, expected_row) in enumerate(rows):
        if len(actual_row) != len(expected_row):
            return False, f"Row {row_idx + 1} field count mismatch"

        for col_idx, (actual_value, expected_value) in enumerate(zip(actual_row, expected_row)):
            if not compare_values(actual_value, expected_value):
                return False, f"Row {row_idx + 1}, Column '{expected_columns[col_idx]}' value mismatch: expected {expected_value}, got {actual_value}"

    return True, None


def evaluate_sql_question(test_case):
    """Test one SQL question."""

    question = test_case["question"]
    reference_sql = test_case["ground_truth"]["sql_query"]

    print(f"\nTesting Question {test_case['id']}")
    print(f"Question: {question}")

    # Get the expected result from the reference SQL.
    try:
        expected = execute_reference_sql(reference_sql)

    except sqlite3.Error as error:
        return {
            "id": test_case["id"],
            "status": "REFERENCE_ERROR",
            "error": str(error)
        }

    # Get the result from our agent.
    actual = run_agent(question)

    if not actual or not actual.get("success"):
        return {
            "id": test_case["id"],
            "status": "AGENT_ERROR",
            "error": actual.get("error", "Agent failed") if actual else "No response"
        }

    # Check if the agent returned the required data.
    if "columns" not in actual or "rows" not in actual:
        return {
            "id": test_case["id"],
            "status": "AGENT_ERROR",
            "error": "SQL result data is missing."
        }

    agent_result = {
        "columns": actual["columns"],
        "rows": actual["rows"]
    }

    # Check whether the question requires a particular row order.
    preserve_order = any(
        word in question.lower()
        for word in [
            "top ",
            "highest",
            "lowest",
            "ascending",
            "descending",
            "ranked"
        ]
    )

    passed, failure_reason = compare_results(
        agent_result,
        expected,
        preserve_order=preserve_order
    )

    return {
        "id": test_case["id"],
        "status": "PASS" if passed else "FAIL",
        "sql": actual.get("sql"),
        "expected": expected,
        "actual": agent_result,
        "error": failure_reason
    }


def calculate_reference_exposure(portfolio_name):
    """Calculate the expected sector exposure from the database."""

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                COALESCE(sec.sector_name, 'Unclassified') AS sector_name,
                SUM(h.current_weight) AS exposure
            FROM portfolios p
            JOIN holdings h
                ON p.portfolio_id = h.portfolio_id
            JOIN securities s
                ON h.security_id = s.security_id
            LEFT JOIN sectors sec
                ON s.sector_id = sec.sector_id
            WHERE p.portfolio_name = ?
              AND s.asset_type = 'Stock'
            GROUP BY sec.sector_name
            ORDER BY sector_name;
            """,
            (portfolio_name,)
        )

        rows = cursor.fetchall()

        if not rows:
            raise ValueError(
                f"No equity holdings found for {portfolio_name}"
            )

        return {
            sector: float(weight or 0.0)
            for sector, weight in rows
        }

    finally:
        connection.close()


def evaluate_exposure_question(test_case):
    """Test one sector exposure question."""

    ground_truth = test_case["ground_truth"]
    portfolio_name = ground_truth["parameters"]["portfolio_name"]

    print(f"\nTesting Question {test_case['id']}")
    print(f"Portfolio: {portfolio_name}")

    # Calculate the expected exposure.
    try:
        expected = calculate_reference_exposure(portfolio_name)

    except (sqlite3.Error, ValueError) as error:
        return {
            "id": test_case["id"],
            "status": "REFERENCE_ERROR",
            "error": str(error)
        }

    # Get the agent's answer.
    actual = run_agent(test_case["question"])

    if not actual or not actual.get("success"):
        return {
            "id": test_case["id"],
            "status": "AGENT_ERROR",
            "error": actual.get("error", "Agent failed") if actual else "No response"
        }

    if actual.get("tool") != "exposure_calculator":
        return {
            "id": test_case["id"],
            "status": "FAIL",
            "error": "Agent selected the wrong tool."
        }

    # Extract the calculated exposure.
    try:
        actual_exposure = actual["result"]["sector_exposure"]

    except (KeyError, TypeError):
        return {
            "id": test_case["id"],
            "status": "AGENT_ERROR",
            "error": "Sector exposure data is missing."
        }

    # Compare sector names and their exposure values.
    if set(actual_exposure) != set(expected):
        missing = set(expected) - set(actual_exposure)
        extra = set(actual_exposure) - set(expected)
        details = []
        if missing:
            details.append(f"missing: {missing}")
        if extra:
            details.append(f"extra: {extra}")
        return {
            "id": test_case["id"],
            "status": "FAIL",
            "expected": expected,
            "actual": actual_exposure,
            "error": "Sector mismatch: " + ", ".join(details)
        }

    for sector in expected:
        if not compare_values(actual_exposure[sector], expected[sector]):
            return {
                "id": test_case["id"],
                "status": "FAIL",
                "expected": expected,
                "actual": actual_exposure,
                "error": f"Value mismatch for sector '{sector}': expected {expected[sector]}, got {actual_exposure[sector]}"
            }

    return {
        "id": test_case["id"],
        "status": "PASS",
        "expected": expected,
        "actual": actual_exposure
    }


def run_evaluation():
    """Run all test cases and display the results."""

    test_cases = load_test_cases()
    results = []

    print("\n========== PORTFOLIO AGENT EVALUATION ==========")

    for test_case in test_cases:

        if test_case["type"] == "text2sql":
            result = evaluate_sql_question(test_case)

        elif test_case["type"] == "exposure_calculator":
            result = evaluate_exposure_question(test_case)

        else:
            result = {
                "id": test_case["id"],
                "status": "SKIPPED",
                "error": "Unsupported question type."
            }
        time.sleep(5)
        results.append(result)

        print(f"Question {result['id']}: {result['status']}")

        if result["status"] == "FAIL":
            print("Generated SQL:")
            print(result.get("sql"))

            print("Expected result:")
            print(result.get("expected"))

            print("Actual result:")
            print(result.get("actual"))

            if result.get("error"):
                print("Details:", result["error"])

        elif result["status"] in ["AGENT_ERROR", "REFERENCE_ERROR"]:
            print("Details:", result.get("error"))

    # Count the results.
    pass_count = sum(r["status"] == "PASS" for r in results)
    fail_count = sum(r["status"] == "FAIL" for r in results)
    agent_error_count = sum(r["status"] == "AGENT_ERROR" for r in results)
    reference_error_count = sum(r["status"] == "REFERENCE_ERROR" for r in results)
    skipped_count = sum(r["status"] == "SKIPPED" for r in results)

    evaluated_count = pass_count + fail_count + agent_error_count

    # Display the final score.
    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Total questions: {len(results)}")
    print(f"Passed: {pass_count}")
    print(f"Failed: {fail_count}")
    print(f"Agent errors: {agent_error_count}")
    print(f"Reference errors: {reference_error_count}")
    print(f"Skipped: {skipped_count}")

    if evaluated_count > 0:
        score = (pass_count / evaluated_count) * 100
        print(f"Agent accuracy: {score:.2f}%")
    else:
        print("Agent accuracy: Not available")

    print("========================================")


if __name__ == "__main__":
    run_evaluation()
