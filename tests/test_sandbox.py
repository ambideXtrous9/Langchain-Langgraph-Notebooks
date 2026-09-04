"""Unit and Integration Tests for Deep Agents Sandboxes Architecture.

Tests:
1. Isolated Subprocess Sandbox execution & output capture.
2. Environment Variable Sanitization (zero leak of API keys / DB passwords).
3. Timeout Enforcement and Graceful Process Termination.
4. Dual-Plane File Operations (upload_files, download_files, path boundary guards).
5. Quantitative Financial Modeling inside Sandbox (Monte Carlo & Markowitz Optimization).
6. LangChain Deep Agent pairing with Sandbox Backend.
"""

import os
import pytest
from app.core.sandbox import (
    BaseSandbox,
    IsolatedSubprocessSandbox,
    get_sandbox_backend,
)
from app.tools.quant_models import (
    run_sandboxed_monte_carlo,
    run_sandboxed_portfolio_optimization,
)


def test_isolated_subprocess_sandbox_execution():
    """Verifies that the isolated sandbox executes Python commands and captures output."""
    sandbox = IsolatedSubprocessSandbox(default_timeout=10)
    try:
        res = sandbox.execute("python3 -c 'import math; print(math.sqrt(144))'")
        assert res.exit_code == 0
        assert "12.0" in res.output
        assert not res.truncated
    finally:
        sandbox.cleanup()


def test_environment_variable_sanitization():
    """Verifies that host secrets and API keys are completely stripped from sandbox environment."""
    os.environ["OPENAI_API_KEY"] = "sk-fake-secret-key-12345"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@host:5432/db"
    os.environ["PINECONE_API_KEY"] = "fake-pinecone-key"

    sandbox = IsolatedSubprocessSandbox()
    try:
        res = sandbox.execute(
            "python3 -c 'import os; print(\"OPENAI:\", os.environ.get(\"OPENAI_API_KEY\")); print(\"DB:\", os.environ.get(\"DATABASE_URL\"))'"
        )
        assert res.exit_code == 0
        assert "OPENAI: None" in res.output
        assert "DB: None" in res.output
    finally:
        sandbox.cleanup()


def test_sandbox_timeout_enforcement():
    """Verifies that long-running commands are terminated cleanly after timeout."""
    sandbox = IsolatedSubprocessSandbox(default_timeout=2)
    try:
        res = sandbox.execute("python3 -c 'import time; time.sleep(10)'", timeout=2)
        assert res.exit_code == 124
        assert "timed out" in res.output.lower()
    finally:
        sandbox.cleanup()


def test_dual_plane_file_operations():
    """Verifies dual-plane file uploads, downloads, and path traversal guards."""
    sandbox = IsolatedSubprocessSandbox()
    try:
        # 1. Upload
        payload = b"Institutional quantitative data payload"
        up_res = sandbox.upload_files([("models/data.txt", payload)])
        assert len(up_res) == 1
        assert up_res[0].error is None

        # 2. Execution plane verifies file exists
        cat_res = sandbox.execute("cat models/data.txt")
        assert cat_res.exit_code == 0
        assert "Institutional quantitative data payload" in cat_res.output

        # 3. Download
        dl_res = sandbox.download_files(["models/data.txt"])
        assert len(dl_res) == 1
        assert dl_res[0].content == payload

        # 4. Path traversal boundary test
        bad_up = sandbox.upload_files([("../../evil.txt", b"danger")])
        assert bad_up[0].error == "permission_denied"
    finally:
        sandbox.cleanup()


def test_quant_monte_carlo_in_sandbox():
    """Tests 2,000-path Monte Carlo Geometric Brownian Motion inside the sandbox."""
    res = run_sandboxed_monte_carlo(
        symbol="RELIANCE.NS",
        current_price=2800.0,
        volatility=0.22,
        paths=2000,
        days=252,
    )
    assert res["symbol"] == "RELIANCE.NS"
    assert res["initial_price"] == 2800.0
    assert res["mean_terminal_price"] > 0
    assert 0.0 < res["var_95_pct"] < 100.0
    assert 0.0 < res["var_99_pct"] < 100.0
    assert "percentiles" in res
    assert res["percentiles"]["p5"] < res["percentiles"]["p95"]
    assert "sandbox_id" in res


def test_quant_portfolio_optimization_in_sandbox():
    """Tests Markowitz Mean-Variance Portfolio Optimization inside the sandbox."""
    symbols = ["TCS.NS", "INFY.NS", "HDFCBANK.NS", "RELIANCE.NS", "ITC.NS"]
    res = run_sandboxed_portfolio_optimization(symbols=symbols)
    assert "max_sharpe_portfolio" in res
    assert "min_volatility_portfolio" in res
    max_sharpe = res["max_sharpe_portfolio"]
    assert max_sharpe["sharpe_ratio"] > 0
    assert max_sharpe["expected_return_pct"] > 0

    # Weights sum approximately to 1.0
    weights = max_sharpe["weights"]
    assert len(weights) == len(symbols)
    weight_sum = sum(weights.values())
    assert 0.98 <= weight_sum <= 1.02


def test_deep_agent_pairing_with_sandbox():
    """Verifies that create_deep_agent accepts the sandbox backend and injects execution capabilities."""
    from deepagents import create_deep_agent
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    backend = get_sandbox_backend()
    model = FakeListChatModel(responses=["I executed the model in the isolated sandbox."])
    agent = create_deep_agent(model=model, backend=backend)
    assert agent is not None
    graph = agent.get_graph()
    assert "tools" in graph.nodes or "model" in graph.nodes

    if hasattr(backend, "cleanup"):
        backend.cleanup()
