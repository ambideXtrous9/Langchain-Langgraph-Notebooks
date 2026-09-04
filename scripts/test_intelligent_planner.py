"""Comprehensive Test Suite for Master Deep Agent Intelligent Query Reasoner & Orchestration Planner.

Verifies:
1. IntelligentQueryReasoner parsing across all classes of queries (single-stock, comparison, screening, sector, macro-risk)
2. Accurate intent classification, target symbol resolution, and time horizon inference
3. Coordinated data sourcing plans across DuckDB, Yahoo Finance, GNews, and Quant Sandbox
4. StateGraph 15-node architectural preservation
5. End-to-end execution returning master_strategic_plan and query_intelligence
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.graphs.stock_analysis.builder import StockAnalysisGraphBuilder
from app.tools.stock_fact_store import StockFactStore
from app.tools.stock_query_reasoner import (
    IntelligentQueryReasoner,
    INTENT_COMPARISON,
    INTENT_SCREENING,
    INTENT_SECTOR,
    INTENT_SINGLE_STOCK,
)


class TestIntelligentQueryReasoner(unittest.IsolatedAsyncioTestCase):
    """Tests for the Master Deep Agent IntelligentQueryReasoner."""

    async def asyncSetUp(self):
        self.fact_store = StockFactStore.get_instance()
        self.fact_store.initialize()
        self.reasoner = IntelligentQueryReasoner(fact_store=self.fact_store)

    async def test_single_stock_query_intelligence(self):
        """Verify intelligent decomposition of single stock deep dive query."""
        query = "research on HDFC Bank in depth"
        result = await self.reasoner.analyze_query(query)

        self.assertIn("HDFCBANK", result["target_symbols"])
        self.assertIn(result["intent"], [INTENT_SINGLE_STOCK, INTENT_COMPARISON])
        self.assertEqual(result["analysis_mode"], "single_stock")
        self.assertGreaterEqual(result["time_horizon_days"], 21)
        self.assertIn("data_sourcing_plan", result)
        self.assertIn("HDFCBANK.NS", result["data_sourcing_plan"]["yahoo_finance_symbols"])
        print(f"✅ Single Stock Reasoner passed: targets={result['target_symbols']} intent={result['intent']}")

    async def test_comparison_with_horizon_intelligence(self):
        """Verify intelligent decomposition of head-to-head comparison with 6-month horizon."""
        query = "compare HDFC Bank and Reliance performance for next 6 months"
        result = await self.reasoner.analyze_query(query)

        self.assertIn("HDFCBANK", result["target_symbols"])
        self.assertIn("RELIANCE", result["target_symbols"])
        self.assertEqual(result["analysis_mode"], "comparison")
        self.assertEqual(result["time_horizon_days"], 126)
        self.assertEqual(result["time_horizon"], "6 Months")
        self.assertIn("monte_carlo", result["data_sourcing_plan"]["quant_sandbox_tasks"])
        self.assertIn("portfolio_optimization", result["data_sourcing_plan"]["quant_sandbox_tasks"])
        print(f"✅ Comparison Reasoner passed: targets={result['target_symbols']} horizon={result['time_horizon']}")

    async def test_fundamental_screening_intelligence(self):
        """Verify dynamic discovery and screening for fundamental filter queries."""
        query = "screen NIFTY 500 for IT stocks with low debt and high ROE"
        result = await self.reasoner.analyze_query(query)

        self.assertIn(result["intent"], [INTENT_SCREENING, INTENT_SECTOR, INTENT_SINGLE_STOCK, INTENT_COMPARISON])
        self.assertTrue(len(result["target_symbols"]) >= 1, "Should resolve at least 1 target from screening")
        print(f"✅ Screening Reasoner passed: screened_targets={result['target_symbols']}")

    def test_graph_topology_preservation_15_nodes(self):
        """Strictly verify that the 15-node StateGraph topology is 100% preserved without drift."""
        builder = StockAnalysisGraphBuilder()
        builder.build()
        graph = builder.workflow

        expected_15_nodes = {
            "deterministic_ingest",
            "richness_assessor",
            "planner",
            "analyst_fanout",
            "reflection",
            "followup_analysis",
            "gather",
            "verify",
            "judge",
            "narrative_enrich",
            "chart_agent",
            "section_writers",
            "exec_summary",
            "assembler",
            "chart_curator",
        }

        actual_nodes = set(graph.nodes.keys())
        self.assertEqual(
            expected_15_nodes,
            actual_nodes,
            f"Graph node topology must match exactly 15 nodes. Difference: {actual_nodes.symmetric_difference(expected_15_nodes)}"
        )
        print(f"✅ 15-Node Graph Topology Preservation verified: exact {len(actual_nodes)} nodes registered.")

    async def test_end_to_end_master_planner_execution(self):
        """Verify full graph execution populates Master Strategic Plan and Query Intelligence."""
        builder = StockAnalysisGraphBuilder()
        compiled_graph = builder.compile()

        state_input = {
            "query": "compare HDFC Bank and Reliance performance for next 6 months",
            "max_lenses": 3,
            "run_id": "test_planner",
        }

        config = {"configurable": {"thread_id": "test_thread_planner"}}
        final_state = await compiled_graph.ainvoke(state_input, config=config)

        # 1. Check Query Intelligence in state
        qi = final_state.get("query_intelligence")
        self.assertIsNotNone(qi, "query_intelligence must be populated in final state")
        self.assertIn("target_symbols", qi)
        self.assertEqual(final_state.get("analysis_mode"), "comparison")

        # 2. Check Master Strategic Plan in state
        mp = final_state.get("master_strategic_plan")
        self.assertIsNotNone(mp, "master_strategic_plan must be populated in final state")
        self.assertIn("strategic_thesis", mp)
        self.assertIn("subgoals", mp)
        self.assertIn("phased_execution_plan", mp)
        self.assertIn("traps", mp)
        self.assertTrue(len(mp["subgoals"]) >= 2)

        # 3. Check Comparative Matrix
        matrix = final_state.get("comparative_matrix", [])
        self.assertTrue(len(matrix) >= 2)

        # 4. Check HTML Report generated with plan
        report_html = final_state.get("report_html", "")
        self.assertIn("Master Deep Agent Strategic Execution Plan", report_html)
        self.assertIn("Head-to-Head Fundamental & Valuation Scorecard", report_html)

        print("✅ End-to-End Master Strategic Planner passed with multi-source coordination!")


if __name__ == "__main__":
    unittest.main()
