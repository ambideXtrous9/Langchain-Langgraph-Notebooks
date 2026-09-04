"""Unit and Integration Tests for the Institutional NSE Stock Analysis Architecture."""

import os
import pytest
import pandas as pd
from langgraph.checkpoint.memory import MemorySaver
from app.core.blackboard import RunBlackboard
from app.graphs.stock_analysis.builder import (
    StockAnalysisGraphBuilder,
    route_gather,
    route_reflection,
)
from app.graphs.stock_analysis.charts import render_chart, run_chart_critic
from app.graphs.stock_analysis.verify import (
    run_digit_audit,
    run_numeric_tracer,
    run_quote_audit,
    run_skeptic_quorum,
    verify_finding,
)
from app.tools.nifty_data import load_enriched_nifty500
from app.tools.stock_fact_store import StockFactStore


def test_nifty_data_loading():
    """Tests NIFTY 500 CSV loading and deterministic metric enrichment."""
    df = load_enriched_nifty500()
    assert not df.empty
    assert len(df) >= 490
    required_cols = [
        "symbol",
        "company_name",
        "industry",
        "current_price",
        "market_cap_cr",
        "pe_ratio",
        "roe_pct",
        "debt_to_equity",
        "beta",
        "return_1m_pct",
        "breakout_52w",
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column {col}"
    assert df["current_price"].min() > 0
    assert df["pe_ratio"].min() > 0


def test_duckdb_fact_store():
    """Tests DuckDB fact store initialization, SQL query execution, and scalar extraction."""
    store = StockFactStore.get_instance()
    store.initialize()

    # 1. Tabular query
    df = store.execute_sql("SELECT symbol, current_price, pe_ratio FROM nifty500 LIMIT 5")
    assert len(df) == 5

    # 2. Scalar query
    count = store.execute_scalar("SELECT COUNT(*) FROM nifty500")
    assert int(count) >= 490

    # 3. Sector aggregates
    sec_df = store.execute_sql("SELECT industry, stock_count FROM sector_aggregates LIMIT 3")
    assert len(sec_df) == 3

    # 4. Profile generation
    profile = store.get_dataset_profile(filter_term="Automobile")
    assert "summary_stats" in profile
    assert profile["summary_stats"]["total_stocks"] > 0


def test_numeric_tracer():
    """Tests the Numeric Tracer audit against the DuckDB fact store."""
    store = StockFactStore.get_instance()
    store.initialize()

    # Exact match test
    sql = "SELECT ROUND(AVG(beta), 2) FROM nifty500"
    real_val = float(store.execute_scalar(sql))
    passed, msg, val = run_numeric_tracer(sql_query=sql, expected_scalar=real_val)
    assert passed is True
    assert "Scalar verified" in msg

    # Mismatch test
    passed_fail, msg_fail, _ = run_numeric_tracer(sql_query=sql, expected_scalar=real_val + 15.0)
    assert passed_fail is False
    assert "Numeric mismatch" in msg_fail


def test_quote_audit():
    """Tests verbatim substring audit vs source narratives."""
    source_text = "Tata Motors reports a 15% increase in electric vehicle sales across India."

    # Substring present
    ok, msg = run_quote_audit(verbatim_quote="electric vehicle sales", source_text=source_text)
    assert ok is True

    # Quote not present
    fail_ok, fail_msg = run_quote_audit(verbatim_quote="hydrogen truck exports to Germany", source_text=source_text)
    assert fail_ok is False


def test_digit_audit():
    """Tests digit audit ensuring prose numbers trace to verified data or exempt sets."""
    # Number matching verified scalar
    ok, msg, untraced = run_digit_audit(claim="Average beta is 1.05 across constituents.", verified_scalar=1.05)
    assert ok is True
    assert not untraced

    # Structural exemption (NIFTY 500, 52-week)
    ok_struct, _, untraced_struct = run_digit_audit(
        claim="In the NIFTY 500 index, stocks touched 52-week highs.", verified_scalar=None
    )
    assert ok_struct is True
    assert not untraced_struct

    # Untraced hallucinated number
    fail_ok, _, untraced_fail = run_digit_audit(
        claim="Profits surged by 879.4% unexpectedly.", verified_scalar=1.05
    )
    assert fail_ok is False
    assert "879.4" in untraced_fail


def test_skeptic_quorum():
    """Tests skeptic quorum detecting named analytical flaws."""
    # Clean finding
    good_finding = {
        "lens": "effectiveness",
        "claim": "Companies with P/E below 25 deliver average ROE of 21.5%.",
        "confidence": 0.88,
        "numeric_scalar": 21.5,
    }
    ok, msg, flaws = run_skeptic_quorum(good_finding, [good_finding])
    assert ok is True
    assert not flaws

    # Flawed finding: speculative unhedged claim
    bad_finding = {
        "lens": "predictive",
        "claim": "Stock prices will surge by 50% with guaranteed upside.",
        "confidence": 0.55,
    }
    bad_ok, bad_msg, bad_flaws = run_skeptic_quorum(bad_finding, [bad_finding])
    assert bad_ok is False
    assert len(bad_flaws) >= 1


def test_blackboard_sqlite(tmp_path):
    """Tests SQLite run blackboard memory for subgoals, evidence, and findings."""
    bb = RunBlackboard(run_id="test_run", db_dir=str(tmp_path))

    bb.add_subgoal("SG_01", "Evaluate valuation metrics")
    subgoals = bb.get_subgoals()
    assert len(subgoals) == 1
    assert subgoals[0]["id"] == "SG_01"

    bb.post_finding(
        finding_id="F_01",
        lens="temporal",
        title="Momentum Lead",
        claim="Average 1M return is 5.2%",
        numeric_scalar=5.2,
    )
    findings = bb.get_findings()
    assert len(findings) == 1
    assert findings[0]["id"] == "F_01"

    bb.update_finding_verification("F_01", verified=True, headline="Momentum Finding")
    verified = bb.get_findings(verified_only=True)
    assert len(verified) == 1
    assert verified[0]["verified"] == 1


def test_chart_rendering_and_critic(tmp_path):
    """Tests deterministic chart rendering and Chart Critic evaluation."""
    df = pd.DataFrame({
        "industry": ["Financial Services", "Capital Goods", "Healthcare"],
        "stock_count": [101, 63, 48],
    })
    spec = {
        "id": "test_chart",
        "title": "Top Industries",
        "chart_type": "bar",
        "x_col": "industry",
        "y_col": "stock_count",
    }

    # Test critic
    passed, msg = run_chart_critic(spec, df)
    assert passed is True

    # Test rendering
    path = render_chart(
        chart_id="test_chart",
        title="Top Industries",
        chart_type="bar",
        df=df,
        x_col="industry",
        y_col="stock_count",
        output_dir=str(tmp_path),
    )
    assert path is not None
    assert os.path.exists(path)


def test_stock_graph_compilation_and_topology():
    """Tests StockAnalysisGraphBuilder compilation, parallel branches, and node registration."""
    checkpointer = MemorySaver()
    builder = StockAnalysisGraphBuilder(checkpointer=checkpointer)
    builder.build()
    graph = builder.compile()

    assert graph is not None

    expected_nodes = [
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
    ]
    for node in expected_nodes:
        assert node in graph.nodes, f"Node {node} missing from graph"

    # Verify Mermaid output contains assembler defer=True
    mermaid_str = graph.get_graph().draw_mermaid()
    assert "assembler" in mermaid_str
    assert "chart_agent" in mermaid_str
    assert "section_writers" in mermaid_str
    assert "exec_summary" in mermaid_str
    assert "chart_curator" in mermaid_str


def test_yahoo_finance_tools():
    """Tests Yahoo Finance tool functions and symbol resolution."""
    from app.tools.yahoo_finance_tools import (
        _clean_nse_symbol,
        fetch_analyst_targets_yf,
        fetch_stock_fundamentals_yf,
        fetch_stock_historical_yf,
        fetch_stock_news_yf,
        fetch_stock_quote_yf,
    )

    # 1. Symbol cleaning
    assert _clean_nse_symbol("RELIANCE") == "RELIANCE.NS"
    assert _clean_nse_symbol("INFY.NS") == "INFY.NS"
    assert _clean_nse_symbol("^NSEI") == "^NSEI"

    # 2. Fetch quote
    res_quote = fetch_stock_quote_yf.invoke({"symbol": "RELIANCE"})
    assert "Quote" in res_quote

    # 3. Fetch fundamentals
    res_fund = fetch_stock_fundamentals_yf.invoke({"symbol": "INFY"})
    assert "Fundamental" in res_fund

    # 4. Fetch historical
    res_hist = fetch_stock_historical_yf.invoke({"symbol": "TCS", "period": "1mo"})
    assert "Historical" in res_hist or "Performance" in res_hist

    # 5. Fetch analyst targets
    res_targets = fetch_analyst_targets_yf.invoke({"symbol": "HDFCBANK"})
    assert "Target" in res_targets or "Analyst" in res_targets

    # 6. Fetch news
    res_news = fetch_stock_news_yf.invoke({"symbol": "RELIANCE"})
    assert "News" in res_news

    # 7. Multi-stock comparison
    from app.tools.yahoo_finance_tools import download_multi_stock_comparison_yf, search_ticker_yf
    res_comp = download_multi_stock_comparison_yf.invoke({"symbols": "RELIANCE, INFY", "period": "1mo"})
    assert "Comparison" in res_comp

    # 8. Ticker search
    res_search = search_ticker_yf.invoke({"query": "Tata"})
    assert "Ticker" in res_search or "Matches" in res_search



