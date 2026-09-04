"""Live End-to-End Test Suite for Deep Agents Sandboxes & Quantitative Modeling.

Executes against running backend container at http://localhost:8000:
1. GET /stock/sandbox/status: Verifies sandbox runtime boundaries (512MB RAM, 1.0 CPU, 30s timeout).
2. POST /stock/quant/simulate (Monte Carlo): Tests 2,000 Geometric Brownian Motion paths & VaR calculation.
3. POST /stock/quant/simulate (Portfolio Opt): Tests Markowitz Mean-Variance optimization in sandbox.
4. POST /stock/sandbox/execute: Tests isolated Python script execution.
5. POST /stock/sandbox/execute (Timeout guard): Tests long-running execution boundary.
6. POST /stock/analyze: Full multi-lens institutional swarm with sandboxed modeling.
7. GET /stock/report/{run_id}: Verifies publication report HTML exhibits.
"""

import json
import time
import httpx

BASE_URL = "http://localhost:8000"


def test_sandbox_status():
    print("\n--- 1. SANDBOX RUNTIME STATUS ---")
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        resp = client.get("/stock/sandbox/status")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "healthy"
        assert "sandbox_id" in data
        assert data["memory_limit"] == "512m"
        assert data["cpu_limit"] == 1.0
        print(f"[✅ PASS] Status: {data['status']}, Provider: {data['provider']}, Sandbox ID: {data['sandbox_id']}")


def test_quant_monte_carlo():
    print("\n--- 2. SANDBOXED MONTE CARLO SIMULATION ---")
    with httpx.Client(base_url=BASE_URL, timeout=20.0) as client:
        payload = {
            "symbol": "RELIANCE.NS",
            "current_price": 2900.0,
            "volatility_pct": 21.5,
            "paths": 2500,
            "simulation_type": "monte_carlo",
        }
        resp = client.post("/stock/quant/simulate", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        res = data["results"]
        assert data["simulation_type"] == "monte_carlo"
        assert res["symbol"] == "RELIANCE.NS"
        assert res["mean_terminal_price"] > 0
        assert 0 < res["var_95_pct"] < 100
        assert 0 < res["var_99_pct"] < 100
        print(f"[✅ PASS] Monte Carlo 2,500 paths: Mean ₹{res['mean_terminal_price']}, 95% VaR: {res['var_95_pct']}%, 99% VaR: {res['var_99_pct']}%")


def test_quant_portfolio_opt():
    print("\n--- 3. SANDBOXED MARKOWITZ PORTFOLIO OPTIMIZATION ---")
    with httpx.Client(base_url=BASE_URL, timeout=20.0) as client:
        payload = {
            "symbol": "TCS.NS,INFY.NS,HDFCBANK.NS,ITC.NS,LT.NS",
            "simulation_type": "portfolio_optimization",
        }
        resp = client.post("/stock/quant/simulate", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        res = data["results"]
        assert data["simulation_type"] == "portfolio_optimization"
        max_sharpe = res["max_sharpe_portfolio"]
        assert max_sharpe["sharpe_ratio"] > 0
        assert len(max_sharpe["weights"]) == 5
        print(f"[✅ PASS] Portfolio Optimization: Optimal Sharpe: {max_sharpe['sharpe_ratio']}, Return: {max_sharpe['expected_return_pct']}%, Vol: {max_sharpe['volatility_pct']}%")


def test_sandbox_python_execute():
    print("\n--- 4. DIRECT PYTHON SCRIPT EXECUTION IN SANDBOX ---")
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        code = (
            "import math, sys\n"
            "print('Python:', sys.version.split()[0])\n"
            "val = math.factorial(8)\n"
            "print(f'Computed 8! = {val}')\n"
        )
        resp = client.post("/stock/sandbox/execute", json={"code": code, "timeout": 15})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["exit_code"] == 0
        assert "Computed 8! = 40320" in data["output"]
        print(f"[✅ PASS] Direct Execution in Sandbox: Output verified, Exit Code 0")


def test_sandbox_timeout_guard():
    print("\n--- 5. SANDBOX TIMEOUT GUARD ---")
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        code = "import time; time.sleep(10)"
        resp = client.post("/stock/sandbox/execute", json={"code": code, "timeout": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["exit_code"] == 124
        assert "timed out" in data["output"].lower()
        print(f"[✅ PASS] Timeout Guard: Execution cleanly terminated after 2s (Exit: 124)")


def test_full_stock_swarm_with_quant():
    print("\n--- 6. INSTITUTIONAL MULTI-AGENT SWARM WITH QUANT SANDBOX ---")
    with httpx.Client(base_url=BASE_URL, timeout=60.0) as client:
        t0 = time.time()
        payload = {
            "query": "Comprehensive NIFTY 500 Automotive & Technology Quant Screening",
            "sector_filter": "Automobile and Auto Components",
            "max_lenses": 2,
        }
        resp = client.post("/stock/analyze", json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        dur = time.time() - t0
        run_id = data["run_id"]
        assert data["verified_findings_count"] >= 1
        assert len(data.get("quant_simulations", [])) >= 1
        assert data.get("sandbox_metrics", {}).get("status") == "active"
        print(f"[✅ PASS] Swarm Execution ({dur:.2f}s): Run ID {run_id}, Findings {data['verified_findings_count']}, Quant Sims: {len(data['quant_simulations'])}")

        # 7. HTML Report verification
        print("\n--- 7. PUBLICATION REPORT WITH QUANT EXHIBITS ---")
        rep_resp = client.get(f"/stock/report/{run_id}")
        assert rep_resp.status_code == 200
        html = rep_resp.text
        assert "Institutional Quantitative Sandbox Modeling" in html
        assert "Isolated DeepAgent Sandbox" in html
        print(f"[✅ PASS] HTML Publication Report: Quantitative Sandbox Exhibits embedded ({len(html)} bytes)")


def main():
    print("=" * 80)
    print("🚀 RUNNING LIVE DEEP AGENTS SANDBOX TEST SUITE")
    print(f"Target: {BASE_URL}")
    print("=" * 80)

    test_sandbox_status()
    test_quant_monte_carlo()
    test_quant_portfolio_opt()
    test_sandbox_python_execute()
    test_sandbox_timeout_guard()
    test_full_stock_swarm_with_quant()

    print("\n" + "=" * 80)
    print("🎉 ALL 7 DEEP AGENTS SANDBOX LIVE TESTS PASSED (100.0%)!")
    print("=" * 80)


if __name__ == "__main__":
    main()
