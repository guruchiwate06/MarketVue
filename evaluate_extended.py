"""
Evaluation runner for the 30-question extended benchmark dataset.
Runs against extended_test_dataset.json without modifying evaluate.py.
"""

import json
import sqlite3
import math
from pathlib import Path
import time

from portfolio_agent import run_agent


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"
GROUND_TRUTH_PATH = BASE_DIR / "extended_test_dataset.json"


def load_test_cases():
    """Load questions from the extended ground truth file."""

    if not GROUND_TRUTH_PATH.exists():
        raise FileNotFoundError("Extended ground truth file not found.")

    with open(GROUND_TRUTH_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    questions = data.get("questions")

    if not isinstance(questions, list):
        raise ValueError("Invalid extended ground truth format.")

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


def compare_values(actual, expected, tolerance=1e-3):
    """Compare two values, allowing small differences in numbers."""

    if actual is None or expected is None:
        return actual is expected

    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(
            float(actual),
            float(expected),
            rel_tol=tolerance,
            abs_tol=0.05
        )

    return str(actual).strip() == str(expected).strip()


def normalize_column_name(name):
    """Normalize column name by removing table prefixes and lowercase."""
    cleaned = str(name).strip().lower()
    if "(" not in cleaned and "." in cleaned:
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
    count_aliases = {
        "count(*)", "count", "total", "total_count", "portfolio_count",
        "holding_count", "sector_count", "transaction_count", "securities_count",
        "distinct_sectors_count"
    }
    if (e in count_aliases or "count" in e) and (a in count_aliases or "count" in a):
        return True

    if ("aum" in e) and ("aum" in a):
        return True

    if ("cost_basis" in e) and ("cost_basis" in a):
        return True

    if ("purchase_value" in e or "total_value" in e) and ("purchase_value" in a or "total_value" in a):
        return True

    # Common metrics aliases
    if ("avg" in e or "average" in e) and "price" in e:
        if ("avg" in a or "average" in a) and "price" in a:
            return True

    if ("beta" in e) and ("beta" in a):
        return True

    if ("tracking_error" in e) and ("tracking_error" in a):
        return True

    if ("volatility" in e) and ("volatility" in a):
        return True

    if ("return" in e) and ("return" in a):
        return True

    if ("drawdown" in e) and ("drawdown" in a):
        return True

    if e in {"exposure", "tech_exposure", "sector_exposure", "weight", "total_weight", "exposure_percentage"} and \
       a in {"exposure", "tech_exposure", "sector_exposure", "weight", "total_weight", "exposure_percentage", "percentage"}:
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


def run_evaluation():
    """Run all test cases and display the results."""

    test_cases = load_test_cases()
    results = []

    print("\n========== EXTENDED PORTFOLIO AGENT EVALUATION (30 Questions) ==========")

    for test_case in test_cases:
        result = evaluate_sql_question(test_case)
        time.sleep(4)
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
    print("\n========== EXTENDED EVALUATION SUMMARY ==========")
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

    print("=================================================")
    return results


if __name__ == "__main__":
    run_evaluation()

