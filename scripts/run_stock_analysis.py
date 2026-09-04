"""Standalone CLI Runner for Institutional NSE Stock Analysis Swarm."""

import argparse
import asyncio
import json
import logging
import os
import sys

# Ensure repository root is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.graphs.stock_analysis.builder import StockAnalysisGraphBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s - %(message)s",
)
logger = logging.getLogger("run_stock_analysis")


async def main():
    parser = argparse.ArgumentParser(description="Run Institutional NSE Stock Analysis Agentic Swarm")
    parser.add_argument(
        "--query",
        type=str,
        default="NIFTY 500 Automobile and Auto Components valuation, momentum, and risk breakdown",
        help="Stock research objective or market query",
    )
    parser.add_argument(
        "--sector",
        type=str,
        default="Automobile and Auto Components",
        help="Specific sector/industry to filter",
    )
    parser.add_argument(
        "--max-lenses",
        type=int,
        default=6,
        help="Maximum number of analyst lenses to fan out (1-13)",
    )
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("🚀 STARTING INSTITUTIONAL NSE STOCK ANALYSIS MULTI-AGENT SWARM")
    print(f"🎯 Objective: {args.query}")
    print(f"🏭 Sector Filter: {args.sector}")
    print(f"🔍 Max Lenses: {args.max_lenses}")
    print("=" * 80 + "\n")

    builder = StockAnalysisGraphBuilder()
    builder.build()
    graph = builder.compile()

    initial_state = {
        "query": args.query,
        "sector_filter": args.sector,
        "max_lenses": args.max_lenses,
        "messages": [],
    }

    config = {"configurable": {"thread_id": "cli_run_01"}}

    print("📊 Executing workflow through LangGraph pipeline...")
    final_state = await graph.ainvoke(initial_state, config=config)

    print("\n" + "=" * 80)
    print("✅ SWARM EXECUTION COMPLETED")
    print("=" * 80)

    richness = final_state.get("data_richness", {})
    verified = final_state.get("verified_findings", [])
    rejected = final_state.get("rejected_findings", [])
    charts = final_state.get("charts", [])
    report_path = final_state.get("report_path", "app/static/report.html")

    print(f"\n📈 Universe Summary:")
    print(f"  - Total Stocks Analyzed: {richness.get('total_stocks')}")
    print(f"  - Total Industries: {richness.get('total_industries')}")
    print(f"  - Market Avg P/E: {richness.get('market_avg_pe')}")
    print(f"  - Market Avg ROE: {richness.get('market_avg_roe')}%")

    print(f"\n🔍 Verification Results:")
    print(f"  - Verified Findings: {len(verified)}")
    print(f"  - Rejected Findings: {len(rejected)}")

    print(f"\n🏆 Top Verified Findings:")
    for i, f in enumerate(verified[:5], 1):
        print(f"  {i}. [{f.get('lens').upper()}] {f.get('headline', f.get('title'))}")
        print(f"     Claim: {f.get('claim')}")
        print(f"     SQL Ground: {f.get('sql_query')}")
        print(f"     Scalar: {f.get('numeric_scalar')} | Verified: {f.get('verified')}")

    print(f"\n📊 Rendered Figures ({len(charts)}):")
    for c in charts:
        print(f"  - {c.get('id')}: {c.get('title')} ({c.get('file_path')})")

    print(f"\n📝 Executive Briefing:")
    print(final_state.get("executive_summary", "")[:350] + "...")

    print(f"\n🌐 Publication Report generated at:")
    print(f"   file://{os.path.abspath(report_path)}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
