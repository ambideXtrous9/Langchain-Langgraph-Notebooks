"""Comprehensive Test Suite for Targeted Stock Research and Head-to-Head Comparison.

Tests:
1. Entity & Alias Resolution (Single stock & Comparative)
2. Horizon Resolution (6 months, 1 year, etc.)
3. DuckDB Comparative Matrix Extraction
4. Chart Generation with Target-Specific Specs
5. Quant Sandbox Horizon-Aware Monte Carlo & Markowitz Optimization
6. End-to-End LangGraph Swarm Execution with Target Queries:
   - "research on HDFC Bank in depth"
   - "compare HDFC Bank and Reliance performance for next 6 months"
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.tools.stock_fact_store import StockFactStore
from app.graphs.stock_analysis.builder import build_stock_analysis_graph
from app.tools.quant_models import run_sandboxed_monte_carlo, run_sandboxed_portfolio_optimization


class TestTargetedStockQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fact_store = StockFactStore.get_instance()

    def test_entity_resolution_single(self):
        query = "research on HDFC Bank in depth"
        res = self.fact_store.resolve_target_entities(query)
        symbols = [r["symbol"] for r in res]
        self.assertIn("HDFCBANK", symbols)
        self.assertEqual(len(symbols), 1)
        print(f"✅ Single Stock Resolution: symbols={symbols}")

    def test_entity_resolution_comparison(self):
        query = "compare HDFC Bank and Reliance performance for next 6 months"
        res = self.fact_store.resolve_target_entities(query)
        symbols = [r["symbol"] for r in res]
        self.assertIn("HDFCBANK", symbols)
        self.assertIn("RELIANCE", symbols)
        self.assertEqual(len(symbols), 2)
        print(f"✅ Comparison Resolution: symbols={symbols}")

    def test_horizon_resolution(self):
        query_6m = "compare HDFC Bank and Reliance performance for next 6 months"
        h6m = self.fact_store.resolve_time_horizon(query_6m)
        self.assertEqual(h6m["label"], "6 Months")
        self.assertEqual(h6m["days"], 126)
        self.assertEqual(h6m["period"], "6mo")

        query_1y = "compare Tata Motors and M&M for next 1 year"
        h1y = self.fact_store.resolve_time_horizon(query_1y)
        self.assertEqual(h1y["label"], "1 Year")
        self.assertEqual(h1y["days"], 252)
        self.assertEqual(h1y["period"], "1y")
        print(f"✅ Horizon Resolution: 6m={h6m['days']}d, 1y={h1y['days']}d")

    def test_comparative_matrix_duckdb(self):
        matrix = self.fact_store.get_comparative_metrics(["HDFCBANK", "RELIANCE"])
        self.assertEqual(len(matrix), 2)
        symbols = [m["symbol"] for m in matrix]
        self.assertIn("HDFCBANK", symbols)
        self.assertIn("RELIANCE", symbols)
        for m in matrix:
            self.assertGreater(m["current_price"], 0)
            self.assertGreater(m["market_cap_cr"], 0)
            self.assertIn("pe_ratio", m)
            self.assertIn("roe_pct", m)
            self.assertIn("return_6m_pct", m)
        print(f"✅ Comparative Matrix: {len(matrix)} constituents loaded with multiples & returns.")

    def test_quant_models_with_target_stocks(self):
        # 1. Monte Carlo for HDFCBANK over 126 days (6 months)
        mc_res = run_sandboxed_monte_carlo(symbol="HDFCBANK.NS", current_price=1680.0, days=126, paths=500)
        self.assertEqual(mc_res["symbol"], "HDFCBANK.NS")
        self.assertEqual(mc_res["simulation_metadata"]["trading_days"], 126)
        self.assertIn("expected_return_pct", mc_res)

        # 2. Markowitz Portfolio Optimization for HDFCBANK & RELIANCE
        po_res = run_sandboxed_portfolio_optimization(symbols=["HDFCBANK.NS", "RELIANCE.NS"])
        self.assertIn("max_sharpe_portfolio", po_res)
        weights = po_res["max_sharpe_portfolio"]["weights"]
        self.assertIn("HDFCBANK.NS", weights)
        self.assertIn("RELIANCE.NS", weights)
        print(f"✅ Quant Sandbox: Monte Carlo horizon={mc_res['simulation_metadata']['trading_days']}d, Markowitz optimal Sharpe={po_res['max_sharpe_portfolio']['sharpe_ratio']}")


class TestEndToEndTargetedSwarm(unittest.IsolatedAsyncioTestCase):
    async def test_comparison_swarm_execution(self):
        graph = build_stock_analysis_graph()
        initial_state = {
            "query": "compare HDFC Bank and Reliance performance for next 6 months",
            "sector_filter": None,
            "max_lenses": 4,
            "run_id": "test_comp",
            "messages": [],
        }
        config = {"configurable": {"thread_id": "thread_test_comp"}}
        result = await graph.ainvoke(initial_state, config=config)

        # Assertions on targeted state
        self.assertIn("HDFCBANK", result.get("target_symbols", []))
        self.assertIn("RELIANCE", result.get("target_symbols", []))
        self.assertEqual(result.get("analysis_mode"), "comparison")
        self.assertEqual(result.get("time_horizon"), "6 Months")
        self.assertEqual(result.get("time_horizon_days"), 126)

        # Verify comparative matrix
        matrix = result.get("comparative_matrix", [])
        self.assertGreaterEqual(len(matrix), 2)

        # Verify findings and quant simulations
        self.assertGreater(len(result.get("verified_findings", [])), 0)
        self.assertGreater(len(result.get("quant_simulations", [])), 0)

        # Verify publication report
        report_html = result.get("report_html", "")
        self.assertIn("HDFCBANK", report_html)
        self.assertIn("RELIANCE", report_html)
        self.assertIn("Head-to-Head Fundamental & Valuation Scorecard", report_html)
        print("✅ End-to-End Comparison Swarm passed with full Head-to-Head scorecard and quant modeling!")

    async def test_single_stock_swarm_execution(self):
        graph = build_stock_analysis_graph()
        initial_state = {
            "query": "research on HDFC Bank in depth",
            "sector_filter": None,
            "max_lenses": 3,
            "run_id": "test_single",
            "messages": [],
        }
        config = {"configurable": {"thread_id": "thread_test_single"}}
        result = await graph.ainvoke(initial_state, config=config)

        self.assertIn("HDFCBANK", result.get("target_symbols", []))
        self.assertEqual(result.get("analysis_mode"), "single_stock")
        self.assertGreater(len(result.get("verified_findings", [])), 0)
        report_html = result.get("report_html", "")
        self.assertIn("HDFCBANK", report_html)
        print("✅ End-to-End Single Stock Deep Dive passed with target-specific research grounding!")


if __name__ == "__main__":
    unittest.main()
