
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


def compare_results(actual, expected, preserve_order=False):
    """Compare the results returned by the agent and reference query."""

    actual_columns = actual["columns"]
    expected_columns = expected["columns"]

    actual_rows = actual["rows"]
    expected_rows = expected["rows"]

    if len(actual_columns) != len(expected_columns):
        return False

    if len(actual_rows) != len(expected_rows):
        return False

    # Ignore row order unless the question asks for a ranking or order.
    if preserve_order:
        rows = zip(actual_rows, expected_rows)
    else:
        actual_rows = sorted(actual_rows, key=lambda row: str(row))
        expected_rows = sorted(expected_rows, key=lambda row: str(row))
        rows = zip(actual_rows, expected_rows)

    for actual_row, expected_row in rows:

        if len(actual_row) != len(expected_row):
            return False

        for actual_value, expected_value in zip(actual_row, expected_row):
            if not compare_values(actual_value, expected_value):
                return False

    return True


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

    passed = compare_results(
        agent_result,
        expected,
        preserve_order=preserve_order
    )

    return {
        "id": test_case["id"],
        "status": "PASS" if passed else "FAIL",
        "sql": actual.get("sql"),
        "expected": expected,
        "actual": agent_result
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
    passed = (
        set(actual_exposure) == set(expected)
        and all(
            compare_values(actual_exposure[sector], expected[sector])
            for sector in expected
        )
    )

    return {
        "id": test_case["id"],
        "status": "PASS" if passed else "FAIL",
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
