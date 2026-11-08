"""
Unit and integration tests for MarketView backend reliability and error handling.
All Gemini API calls are mocked with controlled exceptions and responses.
Zero live API requests are made.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from portfolio_agent import (
    classify_gemini_error,
    GeminiAPIException,
    ReasoningResult,
    generate_reasoning,
    run_agent,
    format_response,
    ToolDecision,
    SQLResponse,
    ReasoningResponse
)
from sql_tool import execute_sql
from exposure_calculator import calculate_sector_exposure
from app import check_database_status


class TestErrorClassification(unittest.TestCase):
    """Test error classifier across quota, auth, network, and malformed responses."""

    def test_quota_exhausted_classification(self):
        err = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for metric: generatelanguage.googleapis.com")
        err_type, msg = classify_gemini_error(err)
        self.assertEqual(err_type, "quota_exhausted")
        self.assertIn("quota", msg.lower())

    def test_auth_error_classification(self):
        err = Exception("403 PERMISSION_DENIED: API_KEY_INVALID")
        err_type, msg = classify_gemini_error(err)
        self.assertEqual(err_type, "auth_error")
        self.assertIn("authentication", msg.lower())

    def test_network_error_classification(self):
        err = Exception("httpx.ConnectError: [Errno 11001] getaddrinfo failed")
        err_type, msg = classify_gemini_error(err)
        self.assertEqual(err_type, "network_error")
        self.assertIn("network", msg.lower())

    def test_missing_api_key_classification(self):
        err = Exception("GEMINI_API_KEY is missing. Check your .env file")
        err_type, msg = classify_gemini_error(err)
        self.assertEqual(err_type, "missing_api_key")


class TestReasoningResult(unittest.TestCase):
    """Test ReasoningResult backwards compatibility and status preservation."""

    def test_string_behavior(self):
        res = ReasoningResult("Valid financial explanation", status="success", error=None)
        self.assertTrue(isinstance(res, str))
        self.assertEqual(str(res), "Valid financial explanation")
        self.assertEqual(res, "Valid financial explanation")
        self.assertEqual(res.status, "success")
        self.assertIsNone(res.error)

    def test_tuple_unpacking(self):
        res = ReasoningResult("", status="quota_exhausted", error="Daily quota reached")
        text, status, error = res
        self.assertEqual(text, "")
        self.assertEqual(status, "quota_exhausted")
        self.assertEqual(error, "Daily quota reached")


class TestMockedReasoningLayer(unittest.TestCase):
    """Test generate_reasoning under controlled mock conditions."""

    @patch("portfolio_agent.call_gemini")
    def test_reasoning_success(self, mock_call):
        mock_call.return_value = ReasoningResponse(explanation="Growth Equity holds 93% Tech.")
        res = generate_reasoning(
            question="Which sector dominates Growth Equity?",
            tool="sql",
            status="success",
            query="SELECT sector_name FROM...",
            data={"columns": ["sector_name"], "rows": [["Technology"]]}
        )
        self.assertEqual(res.status, "success")
        self.assertEqual(str(res), "Growth Equity holds 93% Tech.")
        self.assertIsNone(res.error)

    @patch("portfolio_agent.call_gemini")
    def test_reasoning_quota_exhausted_does_not_invent_facts(self, mock_call):
        mock_call.side_effect = Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
        res = generate_reasoning(
            question="What is total AUM?",
            tool="sql",
            status="success",
            query="SELECT SUM(total_aum) FROM portfolios",
            data={"columns": ["sum(total_aum)"], "rows": [[26750000.0]]}
        )
        self.assertEqual(res.status, "quota_exhausted")
        self.assertEqual(str(res), "")  # Never invent explanations
        self.assertIn("quota", res.error.lower())

    @patch("portfolio_agent.call_gemini")
    def test_reasoning_empty_response(self, mock_call):
        mock_call.return_value = ReasoningResponse(explanation="   ")
        res = generate_reasoning(
            question="What is total AUM?",
            tool="sql",
            status="success",
            data={"columns": ["sum"], "rows": [[100]]}
        )
        self.assertEqual(res.status, "empty_response")
        self.assertEqual(str(res), "")


class TestMockedAgentExecution(unittest.TestCase):
    """Test run_agent decoupling between SQL execution and reasoning."""

    @patch("portfolio_agent.select_tool")
    @patch("portfolio_agent.generate_sql")
    @patch("portfolio_agent.generate_reasoning")
    def test_sql_success_when_reasoning_fails_with_quota(self, mock_reasoning, mock_sql, mock_tool):
        """CRITICAL: Ensure SQL results are NOT discarded when reasoning quota is exhausted."""
        mock_tool.return_value = ToolDecision(tool="sql")
        mock_sql.return_value = "SELECT COUNT(*) FROM portfolios;"
        mock_reasoning.return_value = ReasoningResult("", status="quota_exhausted", error="Quota exceeded")

        result = run_agent("How many portfolios are there?")

        # SQL must succeed!
        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "sql")
        self.assertEqual(result["sql"], "SELECT COUNT(*) FROM portfolios;")
        self.assertEqual(result["rows"], [[13]])
        self.assertEqual(result["row_count"], 1)

        # Reasoning status decoupled
        self.assertEqual(result["reasoning_status"], "quota_exhausted")
        self.assertEqual(result["explanation"], "")
        self.assertIn("quota", result["reasoning_error"].lower())

    @patch("portfolio_agent.select_tool")
    def test_routing_quota_exhausted_classified(self, mock_tool):
        """Test when tool selection itself hits quota limit."""
        mock_tool.side_effect = GeminiAPIException("Gemini quota exhausted", error_type="quota_exhausted")

        result = run_agent("What is the total AUM?")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "quota_exhausted")

    @patch("portfolio_agent.select_tool")
    @patch("portfolio_agent.generate_reasoning")
    def test_exposure_calculator_preserved_when_reasoning_fails(self, mock_reasoning, mock_tool):
        """Test exposure calculator preserves calculations when reasoning fails."""
        mock_tool.return_value = ToolDecision(tool="exposure_calculator", portfolio_name="Tech Innovation Fund")
        mock_reasoning.return_value = ReasoningResult("", status="quota_exhausted", error="Quota exceeded")

        result = run_agent("Show sector exposure for Tech Innovation Fund")
        self.assertTrue(result["success"])
        self.assertEqual(result["tool"], "exposure_calculator")
        self.assertIn("sector_exposure", result["result"])
        self.assertIn("Technology", result["result"]["sector_exposure"])
        self.assertAlmostEqual(result["result"]["sector_exposure"]["Technology"], 1.0, places=4)
        self.assertEqual(result["reasoning_status"], "quota_exhausted")

    @patch("portfolio_agent.select_tool")
    @patch("portfolio_agent.generate_sql")
    @patch("portfolio_agent.generate_reasoning")
    def test_sql_execution_error_distinguished_from_api_error(self, mock_reasoning, mock_sql, mock_tool):
        """Test that database syntax errors are distinguished from API errors."""
        mock_tool.return_value = ToolDecision(tool="sql")
        mock_sql.return_value = "SELECT non_existent_column FROM portfolios;"
        mock_reasoning.return_value = ReasoningResult("", status="quota_exhausted", error="Quota exceeded")

        result = run_agent("Show non-existent column")
        self.assertFalse(result["success"])
        self.assertEqual(result["error_type"], "sql_error")
        self.assertIn("no such column", result["error"].lower())


class TestDatabaseAndSQLSecurity(unittest.TestCase):
    """Test SQL tool security and restrictions completely independently of Gemini."""

    def test_read_only_select_succeeds(self):
        res = execute_sql("SELECT COUNT(*) FROM portfolios;")
        self.assertTrue(res["success"])
        self.assertEqual(res["rows"], [[13]])

    def test_modification_rejected(self):
        res = execute_sql("DELETE FROM portfolios WHERE portfolio_id = 1;")
        self.assertFalse(res["success"])
        self.assertIn("Only SELECT and WITH queries are allowed", res["error"])

    def test_sqlite_master_rejected(self):
        res = execute_sql("SELECT name FROM sqlite_master;")
        self.assertFalse(res["success"])
        self.assertIn("prohibited", res["error"].lower())

    def test_multiple_statements_rejected(self):
        res = execute_sql("SELECT 1; SELECT 2;")
        self.assertFalse(res["success"])

    def test_database_connectivity_status(self):
        ok, msg = check_database_status()
        self.assertTrue(ok)
        self.assertIn("9 tables", msg)
        self.assertIn("13 funds", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
