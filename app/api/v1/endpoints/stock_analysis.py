"""FastAPI Endpoints for Institutional NSE Stock Analysis Architecture."""

import logging
import os
import uuid
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from app.api.deps import get_current_active_user, get_report_user
from app.core.config import settings
from app.core.sandbox import get_sandbox_backend, is_docker_available
from app.schemas.auth import UserResponse
from app.schemas.stock_analysis import (
    QuantSimulationRequest,
    QuantSimulationResponse,
    SandboxExecuteRequest,
    SandboxExecuteResponse,
    SandboxStatusResponse,
    StockAnalysisRequest,
    StockAnalysisResponse,
)
from app.graphs.stock_analysis.nodes import sanitize_citation_tokens
from app.tools.quant_models import (
    run_sandboxed_monte_carlo,
    run_sandboxed_portfolio_optimization,
)
from app.tools.stock_fact_store import StockFactStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stock", tags=["NSE Stock Analysis"])


@router.post(
    "/analyze",
    response_model=StockAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Institutional NSE Stock Analysis Agentic Swarm",
)
async def analyze_stock_universe(
    request: Request,
    payload: StockAnalysisRequest,
    current_user: UserResponse = Depends(get_current_active_user),
) -> StockAnalysisResponse:
    """Executes the full institutional NSE stock analysis workflow:
    - Ingestion of NIFTY 500 CSV into DuckDB fact store
    - GNews intelligence & Pinecone MCP vector search
    - 13 Analyst lenses with create_deep_agent & middlewares
    - Reflection & follow-up analysis
    - 4-tier verification (Numeric tracer, Quote audit, Digit audit, Skeptic quorum)
    - Judge ranking & deduplication
    - Chart Agent with Chart Critic
    - 7 Section Writers & Executive Briefing
    - Deterministic Assembler & Chart Curator
    """
    graph = getattr(request.app.state, "stock_graph", None)
    if graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stock Analysis Graph is not initialized on the server.",
        )

    run_id = str(uuid.uuid4())[:8]
    thread_id = payload.thread_id or f"thread_stock_{run_id}"

    initial_state = {
        "query": payload.query,
        "sector_filter": payload.sector_filter,
        "run_id": run_id,
        "max_lenses": payload.max_lenses,
        "messages": [],
        "user_id": current_user.id,
        "user_email": current_user.email,
    }

    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": current_user.id,
        }
    }

    try:
        final_state = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.exception(f"Stock analysis workflow failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stock analysis execution encountered an error: {str(exc)}",
        )

    verified = final_state.get("verified_findings", [])
    rejected = final_state.get("rejected_findings", [])
    figures = final_state.get("figures_inventory", [])

    raw_sections = final_state.get("sections", {})
    clean_sections: Dict[str, Any] = {}
    for sec_name, sec_val in raw_sections.items():
        if isinstance(sec_val, str):
            clean_sections[sec_name] = sanitize_citation_tokens(sec_val)
        elif isinstance(sec_val, dict):
            if "content" in sec_val and isinstance(sec_val["content"], str):
                clean_sections[sec_name] = sanitize_citation_tokens(sec_val["content"])
            elif "text" in sec_val and isinstance(sec_val["text"], str):
                clean_sections[sec_name] = sanitize_citation_tokens(sec_val["text"])
            elif "narrative" in sec_val and isinstance(sec_val["narrative"], str):
                clean_sections[sec_name] = sanitize_citation_tokens(sec_val["narrative"])
            else:
                parts = []
                for k, v in sec_val.items():
                    k_clean = k.replace("_", " ").capitalize()
                    if isinstance(v, (str, int, float, bool)):
                        parts.append(f"**{k_clean}**: {sanitize_citation_tokens(str(v)) if isinstance(v, str) else v}")
                    elif isinstance(v, list):
                        parts.append(f"**{k_clean}**:\n" + "\n".join(f"- {sanitize_citation_tokens(str(item)) if isinstance(item, str) else item}" for item in v))
                    elif isinstance(v, dict):
                        subparts = [f"  - *{sk.replace('_', ' ').capitalize()}*: {sanitize_citation_tokens(str(sv)) if isinstance(sv, str) else sv}" for sk, sv in v.items()]
                        parts.append(f"**{k_clean}**:\n" + "\n".join(subparts))
                clean_sections[sec_name] = sanitize_citation_tokens("\n\n".join(parts)) if parts else sanitize_citation_tokens(str(sec_val))
        else:
            clean_sections[sec_name] = sanitize_citation_tokens(str(sec_val))

    raw_verified = verified[:10]
    sanitized_verified = []
    for vf in raw_verified:
        if isinstance(vf, dict):
            cleaned_vf = dict(vf)
            for field in ("claim", "title", "verbatim_quote", "headline"):
                if field in cleaned_vf and isinstance(cleaned_vf[field], str):
                    cleaned_vf[field] = sanitize_citation_tokens(cleaned_vf[field])
            sanitized_verified.append(cleaned_vf)
        else:
            sanitized_verified.append(vf)

    figures = final_state.get("figures_inventory", [])
    clean_figures = []
    for f in figures:
        if isinstance(f, dict):
            cf = dict(f)
            fp = str(cf.get("file_path") or "")
            if fp.startswith("app/static/"):
                fp = "/" + fp[4:]
            elif fp.startswith("static/"):
                fp = "/" + fp
            elif not fp.startswith("/") and not fp.startswith("http") and fp:
                fp = "/" + fp
            cf["file_path"] = fp
            if not cf.get("chart_type"):
                cf["chart_type"] = "bar"
            if not cf.get("critic_verdict"):
                cf["critic_verdict"] = "approved"
            clean_figures.append(cf)
        else:
            clean_figures.append(f)

    exec_summary_clean = sanitize_citation_tokens(final_state.get("executive_summary", ""))
    report_html_raw = final_state.get("report_html")
    report_html_clean = sanitize_citation_tokens(report_html_raw) if report_html_raw else None

    return StockAnalysisResponse(
        run_id=run_id,
        query=payload.query,
        is_rag_ready=final_state.get("is_rag_ready", True),
        enabled_lenses=final_state.get("enabled_lenses", []),
        verified_findings_count=len(verified),
        rejected_findings_count=len(rejected),
        executive_summary=exec_summary_clean,
        sections_count=len(clean_sections),
        figures_count=len(clean_figures),
        report_url=final_state.get("report_url", f"/static/report_{run_id}.html"),
        report_html=report_html_clean,
        telemetry={
            "subgoals_count": len(final_state.get("subgoals", [])),
            "traps_identified": len(final_state.get("traps", [])),
            "reflection_gap_funded": final_state.get("reflection_gap_funded", False),
            "user_id": current_user.id,
            "user_email": current_user.email,
        },
        verified_findings=sanitized_verified,
        figures=clean_figures,
        sections=clean_sections,
        quant_simulations=final_state.get("quant_simulations", []),
        sandbox_metrics=final_state.get("sandbox_metrics", {}),
        target_symbols=final_state.get("target_symbols", []),
        target_names=final_state.get("target_names", []),
        analysis_mode=final_state.get("analysis_mode", "sector"),
        time_horizon=final_state.get("time_horizon", "6 Months"),
        comparative_matrix=final_state.get("comparative_matrix", []),
        query_intelligence=final_state.get("query_intelligence"),
        master_strategic_plan=final_state.get("master_strategic_plan"),
    )



@router.get(
    "/report/{run_id}",
    response_class=HTMLResponse,
    summary="View Full Publication-Grade HTML Research Report",
)
async def get_stock_report(
    run_id: str,
    current_user: UserResponse = Depends(get_report_user),
):
    """Returns the compiled publication report HTML for a given run ID."""
    report_file = os.path.join("app", "static", f"report_{run_id}.html")
    if not os.path.exists(report_file):
        # Check standard fallback report.html only for default or latest
        if run_id in ("latest", "default") and os.path.exists("app/static/report.html"):
            report_file = "app/static/report.html"
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report for run '{run_id}' not found.",
            )

    with open(report_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    return HTMLResponse(content=sanitize_citation_tokens(html_content))


@router.get(
    "/health",
    summary="Stock Analysis Fact Store and Tools Health Check",
)
async def stock_health():
    """Checks the health of the NIFTY 500 DuckDB fact store and data pipelines."""
    try:
        fact_store = StockFactStore.get_instance()
        count = fact_store.execute_scalar("SELECT COUNT(*) FROM nifty500")
        sector_count = fact_store.execute_scalar("SELECT COUNT(*) FROM sector_aggregates")
        return {
            "status": "healthy",
            "fact_store": "DuckDB in-memory",
            "nifty500_stocks_loaded": int(count),
            "sectors_indexed": int(sector_count),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
        }


@router.get(
    "/mermaid",
    response_class=HTMLResponse,
    summary="Get Mermaid Diagram for Stock Analysis Graph",
)
async def get_stock_mermaid(request: Request) -> str:
    """Returns the Mermaid graph definition for the Stock Analysis architecture."""
    graph = getattr(request.app.state, "stock_graph", None)
    if graph is not None:
        try:
            return graph.get_graph().draw_mermaid()
        except Exception:
            pass
    from app.graphs.stock_analysis.builder import StockAnalysisGraphBuilder
    builder = StockAnalysisGraphBuilder()
    builder.build()
    compiled = builder.compile()
    return compiled.get_graph().draw_mermaid()


# ---------------------------------------------------------------------------
# Deep Agents Isolated Sandbox Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/sandbox/status",
    response_model=SandboxStatusResponse,
    summary="Get Deep Agents Sandbox Runtime Status",
)
async def get_sandbox_status(
    current_user: UserResponse = Depends(get_current_active_user),
) -> SandboxStatusResponse:
    """Checks the health, configuration, and hardware boundaries of the sandbox backend."""
    sandbox = get_sandbox_backend()
    docker_ok = is_docker_available()
    return SandboxStatusResponse(
        status="healthy",
        provider=getattr(settings, "SANDBOX_PROVIDER", "auto"),
        sandbox_id=sandbox.id,
        memory_limit=getattr(settings, "SANDBOX_MEMORY_LIMIT", "512m"),
        cpu_limit=float(getattr(settings, "SANDBOX_CPU_LIMIT", 1.0)),
        timeout=int(getattr(settings, "SANDBOX_DEFAULT_TIMEOUT", 30)),
        docker_available=docker_ok,
    )


@router.post(
    "/quant/simulate",
    response_model=QuantSimulationResponse,
    summary="Execute On-Demand Financial Simulation in Isolated Sandbox",
)
async def run_quant_simulation(
    payload: QuantSimulationRequest,
    current_user: UserResponse = Depends(get_current_active_user),
) -> QuantSimulationResponse:
    """Executes a quantitative financial simulation (Monte Carlo GBM or Markowitz Portfolio Optimization)
    strictly within the isolated Deep Agents sandbox.
    """
    stype = payload.simulation_type.lower()
    symbol = payload.symbol.strip()

    if stype == "portfolio_optimization":
        symbols = [s.strip() for s in symbol.split(",") if s.strip()]
        if not symbols:
            symbols = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS"]
        res = run_sandboxed_portfolio_optimization(symbols=symbols)
        return QuantSimulationResponse(
            simulation_type="portfolio_optimization",
            symbol=",".join(symbols),
            sandbox_id=res.get("sandbox_id", "sandbox-quant"),
            results=res,
        )

    # Default: Monte Carlo Simulation
    price = payload.current_price
    if not price or price <= 0:
        fact_store = StockFactStore.get_instance()
        clean_sym = symbol.replace(".NS", "").strip()
        val = fact_store.execute_scalar(f"SELECT current_price FROM nifty500 WHERE symbol = '{clean_sym}'")
        price = float(val) if val is not None and float(val) > 0 else 2500.0

    sigma = max(0.05, payload.volatility_pct / 100.0)
    res = run_sandboxed_monte_carlo(
        symbol=symbol,
        current_price=price,
        volatility=sigma,
        paths=payload.paths,
    )
    return QuantSimulationResponse(
        simulation_type="monte_carlo",
        symbol=symbol,
        sandbox_id=res.get("sandbox_id", "sandbox-quant"),
        results=res,
    )


@router.post(
    "/sandbox/execute",
    response_model=SandboxExecuteResponse,
    summary="Safely Execute Custom Python Code in Isolated Sandbox",
)
async def execute_in_sandbox(
    payload: SandboxExecuteRequest,
    current_user: UserResponse = Depends(get_current_active_user),
) -> SandboxExecuteResponse:
    """Runs untrusted user or agent Python scripts inside the hardened sandbox with memory caps and timeout."""
    sandbox = get_sandbox_backend(timeout=payload.timeout)
    try:
        # Upload code as script inside sandbox
        sandbox.upload_files([("user_script.py", payload.code.encode("utf-8"))])
        res = sandbox.execute("python3 user_script.py", timeout=payload.timeout)
        return SandboxExecuteResponse(
            output=res.output,
            exit_code=res.exit_code,
            truncated=res.truncated,
            sandbox_id=sandbox.id,
            provider=getattr(settings, "SANDBOX_PROVIDER", "auto"),
        )
    finally:
        if hasattr(sandbox, "cleanup"):
            sandbox.cleanup()


