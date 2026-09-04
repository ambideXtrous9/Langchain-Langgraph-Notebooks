"""Comprehensive Frontend-to-Backend Test Suite for Deep Agents Quant Sandbox & NSE Stock Swarm.

Tests against Backend at http://localhost:8000:
1. Frontend Asset & DOM Verification (Quant Sandbox buttons, modal, presets, terminal console).
2. Unauthenticated Access Audit: Asserts HTTP 401 Unauthorized for unauthenticated callers.
3. Authenticated Onboarding: Logs in to acquire a valid JWT Bearer access token.
4. Authenticated Status Fetch: GET /stock/sandbox/status (validates hardware ceilings & isolation).
5. Authenticated Quick Monte Carlo Simulation: POST /stock/quant/simulate (GBM 5,000 paths & VaR).
6. Authenticated Quick Portfolio Optimization: POST /stock/quant/simulate (Markowitz Max Sharpe allocation).
7. Authenticated Custom Python Scripting: POST /stock/sandbox/execute (NumPy math, exit code 0).
8. Sandbox Security Boundary Audit: POST /stock/sandbox/execute (asserts ZERO host API keys leaked).
9. Sandbox Timeout Guard: POST /stock/sandbox/execute (asserts exit code 124 on long runs).
10. Sandbox Error Resilience: POST /stock/sandbox/execute (asserts graceful Python traceback, no 500).
11. Authenticated Stock Swarm Analysis: POST /stock/analyze (asserts quant simulations & findings).
12. Authenticated Publication Report Delivery via ?token= Query Param: GET /stock/report/{run_id}?token=...
13. Static Chart Exhibit Delivery: GET /static/top_charts/{img} (asserts image/png delivery).
"""

import json
import time
import httpx

BASE_URL = "http://localhost:8000"
results = {"passed": 0, "failed": 0, "details": []}


def log(tc_id: str, name: str, passed: bool, info: str = ""):
    icon = "✅ PASS" if passed else "❌ FAIL"
    print(f"[{icon}] {tc_id}: {name}")
    if info:
        print(f"       └─ {info}")
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1
    results["details"].append({"id": tc_id, "name": name, "passed": passed, "info": info})


def run_tests():
    print("=" * 80)
    print("🌐 RUNNING COMPREHENSIVE FRONTEND-TO-BACKEND QUANT SANDBOX & AUTH TEST SUITE")
    print(f"Target: {BASE_URL}")
    print("=" * 80)

    unauth_client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # --------------------------------------------------------------------------
    # 1. FRONTEND DOM & ASSETS VERIFICATION
    # --------------------------------------------------------------------------
    print("\n--- 1. FRONTEND HTML & ASSET INTEGRITY ---")
    try:
        r = unauth_client.get("/")
        html = r.text
        has_nav_btn = "btn-open-sandbox" in html
        has_modal = "sandbox-modal" in html
        has_mc_btn = "btn-quick-run-mc" in html
        has_opt_btn = "btn-quick-run-opt" in html
        has_terminal = "modal-sandbox-output-wrap" in html

        all_elements = has_nav_btn and has_modal and has_mc_btn and has_opt_btn and has_terminal
        log("TC-FE-1", "GET / delivers HTML with Quant Sandbox Console components", all_elements,
            f"Navbar Btn: {has_nav_btn}, Modal: {has_modal}, Quick MC: {has_mc_btn}, Quick Opt: {has_opt_btn}, Terminal: {has_terminal}")
    except Exception as e:
        log("TC-FE-1", "GET / delivers HTML with Quant Sandbox Console", False, str(e))

    try:
        r_css = unauth_client.get("/css/chat.css")
        r_js = unauth_client.get("/js/app.js")
        css_ok = "modal-sandbox-output-wrap" in r_css.text and "#btn-open-sandbox:hover" in r_css.text
        js_ok = "setupQuantSandboxConsole" in r_js.text and "btn-quick-run-mc" in r_js.text
        log("TC-FE-2", "Static CSS & JS deliver Quant Sandbox styles & event listeners", css_ok and js_ok,
            f"CSS ok: {css_ok}, JS ok: {js_ok}")
    except Exception as e:
        log("TC-FE-2", "Static CSS & JS deliver Quant Sandbox styles", False, str(e))

    # --------------------------------------------------------------------------
    # 2. UNAUTHENTICATED SECURITY AUDIT (ZERO GUEST ACCESS)
    # --------------------------------------------------------------------------
    print("\n--- 2. UNAUTHENTICATED ACCESS REJECTION AUDIT (HTTP 401) ---")
    
    # 2.1 GET /stock/sandbox/status unauthenticated
    try:
        r = unauth_client.get("/stock/sandbox/status")
        passed = r.status_code == 401
        log("TC-SEC-1", "GET /stock/sandbox/status rejects unauthenticated requests with 401", passed,
            f"Status Code: {r.status_code}")
    except Exception as e:
        log("TC-SEC-1", "GET /stock/sandbox/status auth guard", False, str(e))

    # 2.2 POST /stock/quant/simulate unauthenticated
    try:
        r = unauth_client.post("/stock/quant/simulate", json={"symbol": "RELIANCE.NS", "simulation_type": "monte_carlo"})
        passed = r.status_code == 401
        log("TC-SEC-2", "POST /stock/quant/simulate rejects unauthenticated requests with 401", passed,
            f"Status Code: {r.status_code}")
    except Exception as e:
        log("TC-SEC-2", "POST /stock/quant/simulate auth guard", False, str(e))

    # 2.3 POST /stock/sandbox/execute unauthenticated
    try:
        r = unauth_client.post("/stock/sandbox/execute", json={"code": "print(1)", "timeout": 5})
        passed = r.status_code == 401
        log("TC-SEC-3", "POST /stock/sandbox/execute rejects unauthenticated requests with 401", passed,
            f"Status Code: {r.status_code}")
    except Exception as e:
        log("TC-SEC-3", "POST /stock/sandbox/execute auth guard", False, str(e))

    # 2.4 POST /stock/analyze unauthenticated
    try:
        r = unauth_client.post("/stock/analyze", json={"query": "test"})
        passed = r.status_code == 401
        log("TC-SEC-4", "POST /stock/analyze rejects unauthenticated requests with 401", passed,
            f"Status Code: {r.status_code}")
    except Exception as e:
        log("TC-SEC-4", "POST /stock/analyze auth guard", False, str(e))

    # 2.5 GET /stock/report/{run_id} unauthenticated
    try:
        r = unauth_client.get("/stock/report/default")
        passed = r.status_code == 401
        log("TC-SEC-5", "GET /stock/report/default rejects unauthenticated requests with 401", passed,
            f"Status Code: {r.status_code}")
    except Exception as e:
        log("TC-SEC-5", "GET /stock/report/default auth guard", False, str(e))

    # 2.6 Public diagnostics (Health & Mermaid remain accessible)
    try:
        r_health = unauth_client.get("/stock/health")
        r_mermaid = unauth_client.get("/stock/mermaid")
        passed = r_health.status_code == 200 and r_mermaid.status_code == 200
        log("TC-SEC-6", "Diagnostic endpoints /stock/health & /stock/mermaid remain publicly accessible", passed,
            f"Health: {r_health.status_code}, Mermaid: {r_mermaid.status_code}")
    except Exception as e:
        log("TC-SEC-6", "Public diagnostic routes", False, str(e))

    # --------------------------------------------------------------------------
    # 3. AUTHENTICATION ONBOARDING (JWT ACQUISITION)
    # --------------------------------------------------------------------------
    print("\n--- 3. AUTHENTICATION & JWT TOKEN ACQUISITION ---")
    auth_token = ""
    test_email = f"tester_{int(time.time())}@example.com"
    test_pwd = "StrongSecurePassword123!"

    try:
        # Signup
        r_signup = unauth_client.post("/auth/signup", json={
            "email": test_email,
            "full_name": "Quant Swarm Tester",
            "password": test_pwd
        })
        # Login to get token
        r_login = unauth_client.post("/auth/login", json={
            "email": test_email,
            "password": test_pwd
        })
        if r_login.status_code != 200:
            # Fallback to OAuth2 form
            r_login = unauth_client.post("/auth/login", data={
                "username": test_email,
                "password": test_pwd
            })
        
        login_data = r_login.json()
        auth_token = login_data.get("access_token", "")
        passed = bool(auth_token)
        log("TC-AUTH-1", "Obtained JWT Bearer access token via /auth/login", passed,
            f"User: {test_email}, Token prefix: {auth_token[:25]}...")
    except Exception as e:
        log("TC-AUTH-1", "Obtain JWT token", False, str(e))

    if not auth_token:
        print("❌ ABORTING AUTHENTICATED TESTS: Could not obtain token.")
        return False

    auth_headers = {"Authorization": f"Bearer {auth_token}"}
    auth_client = httpx.Client(base_url=BASE_URL, headers=auth_headers, timeout=60.0)

    # --------------------------------------------------------------------------
    # 4. AUTHENTICATED SANDBOX STATUS
    # --------------------------------------------------------------------------
    print("\n--- 4. AUTHENTICATED SANDBOX STATUS BADGE POLLING ---")
    try:
        r = auth_client.get("/stock/sandbox/status")
        data = r.json()
        passed = r.status_code == 200 and data.get("status") == "healthy" and "sandbox_id" in data
        log("TC-FE-3", "GET /stock/sandbox/status polled with Bearer token succeeds", passed,
            f"Status: {data.get('status')}, Provider: {data.get('provider')}, Memory Limit: {data.get('memory_limit')}, ID: {data.get('sandbox_id')}")
    except Exception as e:
        log("TC-FE-3", "GET /stock/sandbox/status polled with Bearer token", False, str(e))

    # --------------------------------------------------------------------------
    # 5. AUTHENTICATED QUICK MONTE CARLO SIMULATION
    # --------------------------------------------------------------------------
    print("\n--- 5. AUTHENTICATED QUICK MONTE CARLO SIMULATION (#btn-quick-run-mc) ---")
    try:
        payload = {
            "symbol": "RELIANCE.NS",
            "current_price": 2850.0,
            "volatility_pct": 22.0,
            "paths": 5000,
            "simulation_type": "monte_carlo",
        }
        r = auth_client.post("/stock/quant/simulate", json=payload)
        data = r.json()
        res = data.get("results", {})
        passed = (
            r.status_code == 200
            and data.get("simulation_type") == "monte_carlo"
            and res.get("symbol") == "RELIANCE.NS"
            and res.get("mean_terminal_price", 0) > 0
            and 0 < res.get("var_95_pct", 0) < 100
        )
        log("TC-FE-4", "POST /stock/quant/simulate 5,000-Path Monte Carlo with Bearer token", passed,
            f"Symbol: {res.get('symbol')}, Mean: ₹{res.get('mean_terminal_price')}, VaR (95%): {res.get('var_95_pct')}%, CVaR: {res.get('cvar_95_pct')}%")
    except Exception as e:
        log("TC-FE-4", "POST /stock/quant/simulate Monte Carlo", False, str(e))

    # --------------------------------------------------------------------------
    # 6. AUTHENTICATED QUICK PORTFOLIO OPTIMIZATION
    # --------------------------------------------------------------------------
    print("\n--- 6. AUTHENTICATED QUICK PORTFOLIO OPTIMIZATION (#btn-quick-run-opt) ---")
    try:
        payload = {
            "symbol": "RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS,ITC.NS",
            "simulation_type": "portfolio_optimization",
        }
        r = auth_client.post("/stock/quant/simulate", json=payload)
        data = r.json()
        res = data.get("results", {})
        max_sharpe = res.get("max_sharpe_portfolio", {})
        passed = (
            r.status_code == 200
            and data.get("simulation_type") == "portfolio_optimization"
            and max_sharpe.get("sharpe_ratio", 0) > 0
            and len(max_sharpe.get("weights", {})) == 5
        )
        log("TC-FE-5", "POST /stock/quant/simulate Markowitz Portfolio Optimization with Bearer token", passed,
            f"Optimal Sharpe: {max_sharpe.get('sharpe_ratio')}, Return: {max_sharpe.get('expected_return_pct')}%, Vol: {max_sharpe.get('volatility_pct')}%")
    except Exception as e:
        log("TC-FE-5", "POST /stock/quant/simulate Portfolio Optimization", False, str(e))

    # --------------------------------------------------------------------------
    # 7. AUTHENTICATED CUSTOM PYTHON SCRIPT EXECUTION
    # --------------------------------------------------------------------------
    print("\n--- 7. AUTHENTICATED CUSTOM SCRIPT EXECUTION (#modal-sandbox-run-btn) ---")
    try:
        code = (
            "import numpy as np\n"
            "data = [12.5, 18.2, 14.7, 22.0, 19.4]\n"
            "print('Mean Return:', np.mean(data))\n"
            "print('Std Deviation:', round(float(np.std(data)), 2))\n"
        )
        r = auth_client.post("/stock/sandbox/execute", json={"code": code, "timeout": 20})
        data = r.json()
        passed = r.status_code == 200 and data.get("exit_code") == 0 and "Mean Return: 17.36" in data.get("output", "")
        log("TC-FE-6", "POST /stock/sandbox/execute custom mathematical script with Bearer token", passed,
            f"Exit Code: {data.get('exit_code')}, Output: {data.get('output', '').strip()}")
    except Exception as e:
        log("TC-FE-6", "POST /stock/sandbox/execute custom script", False, str(e))

    # --------------------------------------------------------------------------
    # 8. SANDBOX SECURITY AUDIT (ZERO SECRET LEAKAGE)
    # --------------------------------------------------------------------------
    print("\n--- 8. SANDBOX SECURITY AUDIT (ZERO HOST SECRET LEAKAGE) ---")
    try:
        audit_code = (
            "import os\n"
            "keys = ['OPENAI_API_KEY', 'DATABASE_URL', 'PINECONE_API_KEY', 'JWT_SECRET_KEY']\n"
            "leaks = [k for k in keys if k in os.environ]\n"
            "print('LEAKS_FOUND:', leaks)\n"
        )
        r = auth_client.post("/stock/sandbox/execute", json={"code": audit_code, "timeout": 15})
        data = r.json()
        passed = r.status_code == 200 and "LEAKS_FOUND: []" in data.get("output", "")
        log("TC-FE-7", "POST /stock/sandbox/execute verifies zero environment secret leakage", passed,
            f"Audit output: {data.get('output', '').strip()}")
    except Exception as e:
        log("TC-FE-7", "POST /stock/sandbox/execute security audit", False, str(e))

    # --------------------------------------------------------------------------
    # 9. SANDBOX TIMEOUT GUARD
    # --------------------------------------------------------------------------
    print("\n--- 9. SANDBOX TIMEOUT GUARD ENFORCEMENT ---")
    try:
        code = "import time; time.sleep(10)"
        r = auth_client.post("/stock/sandbox/execute", json={"code": code, "timeout": 2})
        data = r.json()
        passed = r.status_code == 200 and data.get("exit_code") == 124 and "timed out" in data.get("output", "").lower()
        log("TC-FE-8", "POST /stock/sandbox/execute handles script timeout without server stall", passed,
            f"Exit Code: {data.get('exit_code')}, Message: {data.get('output', '').strip()}")
    except Exception as e:
        log("TC-FE-8", "POST /stock/sandbox/execute timeout", False, str(e))

    # --------------------------------------------------------------------------
    # 10. SANDBOX PYTHON TRACEBACK ERROR RESILIENCE
    # --------------------------------------------------------------------------
    print("\n--- 10. SANDBOX PYTHON EXCEPTION RESILIENCE ---")
    try:
        error_code = "print(10 / 0)"
        r = auth_client.post("/stock/sandbox/execute", json={"code": error_code, "timeout": 10})
        data = r.json()
        passed = r.status_code == 200 and data.get("exit_code") != 0 and "ZeroDivisionError" in data.get("output", "")
        log("TC-FE-9", "POST /stock/sandbox/execute catches Python runtime exception safely", passed,
            f"Exit Code: {data.get('exit_code')}, Output snippet: {data.get('output', '').strip()[:60]}...")
    except Exception as e:
        log("TC-FE-9", "POST /stock/sandbox/execute exception", False, str(e))

    # --------------------------------------------------------------------------
    # 11. AUTHENTICATED STOCK SWARM EXECUTION
    # --------------------------------------------------------------------------
    print("\n--- 11. AUTHENTICATED CHAT FLOW: FULL MULTI-LENS STOCK SWARM ---")
    run_id = ""
    try:
        t0 = time.time()
        payload = {
            "query": "Institutional Automobile and Auto Components valuation, momentum, and risk breakdown",
            "sector_filter": "Automobile and Auto Components",
            "max_lenses": 2,
        }
        r = auth_client.post("/stock/analyze", json=payload, timeout=60.0)
        data = r.json()
        dur = time.time() - t0
        run_id = data.get("run_id", "")
        telemetry = data.get("telemetry", {})
        passed = (
            r.status_code == 200
            and bool(run_id)
            and data.get("verified_findings_count", 0) >= 1
            and len(data.get("quant_simulations", [])) >= 1
            and telemetry.get("user_email") == test_email
        )
        log("TC-FE-10", "POST /stock/analyze full multi-agent swarm grounded to authenticated user", passed,
            f"Run ID: {run_id}, Findings: {data.get('verified_findings_count')}, Quant Sims: {len(data.get('quant_simulations', []))}, Grounded User: {telemetry.get('user_email')}, Latency: {dur:.2f}s")
    except Exception as e:
        log("TC-FE-10", "POST /stock/analyze full multi-agent swarm", False, str(e))

    # --------------------------------------------------------------------------
    # 12. PUBLICATION REPORT DELIVERY VIA ?token= QUERY PARAM
    # --------------------------------------------------------------------------
    print("\n--- 12. PUBLICATION REPORT DELIVERY (BROWSER QUERY PARAM AUTH) ---")
    try:
        if run_id:
            # Query param auth without Authorization header (simulates browser window.open)
            r = unauth_client.get(f"/stock/report/{run_id}?token={auth_token}")
            html = r.text
            passed = (
                r.status_code == 200
                and "Institutional Quantitative Sandbox Modeling" in html
                and "Isolated DeepAgent Sandbox" in html
            )
            log("TC-FE-11", f"GET /stock/report/{run_id}?token=... succeeds for new browser tabs", passed,
                f"Status: {r.status_code}, HTML size: {len(html)} bytes, Quant section verified")
        else:
            log("TC-FE-11", "GET /stock/report/{run_id} skipped (no run_id)", False)
    except Exception as e:
        log("TC-FE-11", "GET /stock/report/{run_id} with query param token", False, str(e))

    # Also test with Bearer header
    try:
        if run_id:
            r_bearer = auth_client.get(f"/stock/report/{run_id}")
            passed = r_bearer.status_code == 200
            log("TC-FE-11B", f"GET /stock/report/{run_id} succeeds with Bearer header", passed,
                f"Status: {r_bearer.status_code}")
    except Exception as e:
        log("TC-FE-11B", "GET /stock/report with Bearer header", False, str(e))

    # --------------------------------------------------------------------------
    # 13. STATIC VISUAL EXHIBIT DELIVERY
    # --------------------------------------------------------------------------
    print("\n--- 13. STATIC CHART EXHIBIT DELIVERY ---")
    try:
        r = unauth_client.get("/static/top_charts/chart_sector_mcap.png")
        passed = r.status_code == 200 and r.headers.get("content-type") == "image/png"
        log("TC-FE-12", "GET /static/top_charts/chart_sector_mcap.png image exhibit delivery", passed,
            f"Content-Type: {r.headers.get('content-type')}, Size: {len(r.content)} bytes")
    except Exception as e:
        log("TC-FE-12", "GET /static/top_charts/chart_sector_mcap.png", False, str(e))

    # --------------------------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------------------------
    tot = results["passed"] + results["failed"]
    print("\n" + "=" * 80)
    print(f"📊 COMPREHENSIVE TEST SUITE SUMMARY: {results['passed']}/{tot} PASSED ({(results['passed']/tot)*100:.1f}%)")
    print("=" * 80)
    return results["failed"] == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
