"""Schemas and State Definitions for the NSE Stock Analysis Multi-Agent Graph."""

import operator
from typing import Annotated, Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from langgraph.graph import MessagesState


class Finding(BaseModel):
    """Structured candidate finding proposed by an analyst lens."""

    id: str = Field(..., description="Unique finding ID (e.g. 'F_TEMPORAL_01')")
    lens: str = Field(..., description="Analyst lens identifier (e.g. 'temporal', 'effectiveness')")
    title: str = Field(..., description="Concise finding title")
    claim: str = Field(..., description="Precise factual claim")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    sql_query: Optional[str] = Field(default=None, description="SQL statement returning single scalar proof")
    numeric_scalar: Optional[float] = Field(default=None, description="Target scalar value verified by DuckDB")
    verbatim_quote: Optional[str] = Field(default=None, description="Exact substring from corporate disclosure/news")
    source: Optional[str] = Field(default=None, description="Source provenance (e.g. 'DuckDB nifty500', 'GNews')")
    verified: bool = Field(default=False)
    verification_details: Dict[str, Any] = Field(default_factory=dict)
    skeptic_votes: List[str] = Field(default_factory=list)
    rank: Optional[int] = Field(default=None)
    headline: Optional[str] = Field(default=None)
    attached_quotes: List[str] = Field(default_factory=list)


class ChartSpec(BaseModel):
    """Specification for deterministic chart rendering and chart critique."""

    id: str = Field(..., description="Chart identifier")
    title: str = Field(..., description="Chart title")
    chart_type: str = Field(..., description="Chart style: 'bar', 'scatter', 'line', 'histogram'")
    sql_query: str = Field(..., description="DuckDB SQL generating realized data for plotting")
    x_col: str
    y_col: str
    hue_col: Optional[str] = None
    file_path: Optional[str] = None
    critic_verdict: Optional[str] = "approved"
    curator_rank: Optional[int] = None


class StockAnalysisState(MessagesState, total=False):
    """LangGraph State representation for the entire NSE Stock Analysis Workflow."""

    query: str
    sector_filter: Optional[str]
    run_id: str
    max_lenses: Optional[int]
    data_richness: Dict[str, Any]
    is_rag_ready: bool
    planner_output: Dict[str, Any]
    enabled_lenses: List[str]
    subgoals: List[Dict[str, Any]]
    traps: List[Dict[str, Any]]
    deliberately_not_pursued: List[str]
    proposed_findings: Annotated[List[Dict[str, Any]], operator.add]
    reflection_gap_funded: bool
    followup_findings: List[Dict[str, Any]]
    verified_findings: List[Dict[str, Any]]
    rejected_findings: List[Dict[str, Any]]
    ranked_findings: List[Dict[str, Any]]
    enriched_findings: List[Dict[str, Any]]
    charts: List[Dict[str, Any]]
    sections: Dict[str, Any]
    executive_summary: str
    figures_inventory: List[Dict[str, Any]]
    report_html: str
    report_path: str
    telemetry: Dict[str, Any]
    quant_simulations: List[Dict[str, Any]]
    sandbox_metrics: Dict[str, Any]
    target_symbols: List[str]
    target_names: List[str]
    analysis_mode: str
    time_horizon: str
    time_horizon_days: int
    comparative_matrix: List[Dict[str, Any]]
    query_intelligence: Dict[str, Any]
    master_strategic_plan: Dict[str, Any]


class StockAnalysisRequest(BaseModel):
    """Payload to trigger an NSE Stock Analysis run."""

    query: str = Field(
        ...,
        description="Stock analysis objective or query (e.g. 'research on HDFC Bank in depth' or 'compare HDFC Bank and Reliance performance for next 6 months')",
    )
    sector_filter: Optional[str] = Field(
        default=None,
        description="Optional specific industry/sector filter (e.g. 'Automobile and Auto Components', 'Financial Services')",
    )
    max_lenses: int = Field(default=13, ge=1, le=13, description="Maximum number of analyst lenses to fan out.")
    thread_id: Optional[str] = Field(default=None, description="Optional thread identifier for checkpointing.")
    enable_quant_sandbox: bool = Field(default=True, description="Enable quantitative sandbox modeling (Monte Carlo & Sharpe optimization)")


class StockAnalysisResponse(BaseModel):
    """Result of an NSE Stock Analysis run."""

    run_id: str
    query: str
    is_rag_ready: bool
    enabled_lenses: List[str]
    verified_findings_count: int
    rejected_findings_count: int
    executive_summary: str
    sections_count: int
    figures_count: int
    report_url: str
    report_html: Optional[str] = None
    telemetry: Dict[str, Any] = Field(default_factory=dict)
    verified_findings: List[Dict[str, Any]] = Field(default_factory=list)
    figures: List[Dict[str, Any]] = Field(default_factory=list)
    sections: Dict[str, Any] = Field(default_factory=dict)
    quant_simulations: List[Dict[str, Any]] = Field(default_factory=list)
    sandbox_metrics: Dict[str, Any] = Field(default_factory=dict)
    target_symbols: List[str] = Field(default_factory=list)
    target_names: List[str] = Field(default_factory=list)
    analysis_mode: str = "sector"
    time_horizon: str = "6 Months"
    comparative_matrix: List[Dict[str, Any]] = Field(default_factory=list)
    query_intelligence: Optional[Dict[str, Any]] = None
    master_strategic_plan: Optional[Dict[str, Any]] = None



class QuantSimulationRequest(BaseModel):
    """Request for on-demand financial simulation in the isolated sandbox."""

    symbol: str = Field(default="RELIANCE.NS", description="NSE Stock Symbol or comma-separated symbols")
    current_price: Optional[float] = Field(default=None, description="Current market price (fetched automatically if omitted)")
    volatility_pct: float = Field(default=24.0, ge=1.0, le=150.0, description="Annualized volatility percentage")
    paths: int = Field(default=5000, ge=100, le=50000, description="Number of Monte Carlo paths to simulate")
    simulation_type: str = Field(default="monte_carlo", description="'monte_carlo' or 'portfolio_optimization'")


class QuantSimulationResponse(BaseModel):
    """Result from sandboxed quantitative simulation."""

    simulation_type: str
    symbol: str
    sandbox_id: str
    results: Dict[str, Any]
    status: str = "success"


class SandboxExecuteRequest(BaseModel):
    """Request to safely run custom Python code inside the sandbox."""

    code: str = Field(..., description="Python script to execute in the isolated sandbox")
    timeout: int = Field(default=30, ge=1, le=120, description="Execution timeout in seconds")


class SandboxExecuteResponse(BaseModel):
    """Execution output from the isolated sandbox."""

    output: str
    exit_code: Optional[int] = 0
    truncated: bool = False
    sandbox_id: str
    provider: str


class SandboxStatusResponse(BaseModel):
    """Health and runtime status of the active sandbox backend."""

    status: str
    provider: str
    sandbox_id: str
    memory_limit: str
    cpu_limit: float
    timeout: int
    docker_available: bool

