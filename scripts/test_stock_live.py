"""Comprehensive Live Integration & Edge-Case Test Suite for Institutional NSE Stock Analysis.

Tests against the running Docker backend (http://localhost:8000):
1. GET /stock/health - DuckDB Fact Store & NIFTY 500 Universe initialization
2. GET /stock/mermaid - StateGraph Mermaid DSL diagram generation
3. POST /stock/analyze - Happy path sector-filtered multi-lens research pipeline
4. GET /stock/report/{run_id} - Publication-grade HTML report endpoint
5. Static Visual Asset Delivery - Verification of static report chart exhibits
6. Edge Case 1: Non-existent / Empty sector filter handling
7. Edge Case 2: Boundary test with max_lenses=1 (minimal lens)
8. Edge Case 3: Boundary test with max_lenses=25 (Pydantic le=13 schema validation)
9. Edge Case 4: SQL injection / adversarial query safety
10. Edge Case 5: Non-existent run_id report lookup (404 Not Found)
11. Edge Case 6: Empty query validation handling
12. Frontend SPA & Agent Asset Delivery
"""

import json
import sys
import time
import httpx

BASE_URL = "http://localhost:8000"

results = {
    "passed": 0,
    "failed": 0,
    "details": []
}


def log_test(category: str, tc_id: str, name: str, passed: bool, details: str = ""):
    status_icon = "✅ PASS" if passed else "❌ FAIL"
    print(f"[{status_icon}] {category} | {tc_id}: {name}")
    if details:
        print(f"       └─ {details}")
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1
    results["details"].append({
        "category": category,
        "id": tc_id,
        "name": name,
        "passed": passed,
        "details": details
    })


def run_tests():
    print("=" * 80)
    print("🚀 STARTING LIVE INSTITUTIONAL NSE STOCK ANALYSIS DOCKER TEST SUITE")
    print(f"Target: {BASE_URL}")
    print("=" * 80)

    client = httpx.Client(base_url=BASE_URL, timeout=120.0)

    # --------------------------------------------------------------------------
    # 1. Health & Fact Store Integrity
    # --------------------------------------------------------------------------
    print("\n--- 1. HEALTH & FACT STORE INITIALIZATION ---")
    try:
        r = client.get("/stock/health")
        data = r.json()
        passed = (
            r.status_code == 200
            and data.get("status") == "healthy"
            and data.get("fact_store") == "DuckDB in-memory"
            and data.get("nifty500_stocks_loaded") == 500
        )
        log_test(
            "Health", "TC-STOCK-1", "GET /stock/health DuckDB 500-stock initialization",
            passed, f"Status: {r.status_code}, Records: {data.get('nifty500_stocks_loaded')}, Fact Store: {data.get('fact_store')}"
        )
    except Exception as e:
        log_test("Health", "TC-STOCK-1", "GET /stock/health", False, str(e))

    # --------------------------------------------------------------------------
    # 2. StateGraph Mermaid Diagram
    # --------------------------------------------------------------------------
    print("\n--- 2. ARCHITECTURE MERMAID DIAGRAM ---")
    try:
        r = client.get("/stock/mermaid")
        passed = (
            r.status_code == 200
            and "deterministic_ingest" in r.text
            and "planner" in r.text
            and "analyst_fanout" in r.text
            and "reflection" in r.text
            and "judge" in r.text
            and "chart_curator" in r.text
        )
        log_test(
            "Diagram", "TC-STOCK-2", "GET /stock/mermaid DSL architecture representation",
            passed, f"Status: {r.status_code}, Length: {len(r.text)} bytes, Core nodes verified"
        )
    except Exception as e:
        log_test("Diagram", "TC-STOCK-2", "GET /stock/mermaid", False, str(e))

    # --------------------------------------------------------------------------
    # 2.5 Unauthenticated Guard & JWT Onboarding
    # --------------------------------------------------------------------------
    print("\n--- 2.5 AUTH GUARD & JWT ONBOARDING ---")
    try:
        r_unauth = client.post("/stock/analyze", json={"query": "test unauthenticated"})
        log_test("Security", "TC-STOCK-AUTH-1", "POST /stock/analyze rejects unauthenticated call with 401",
                 r_unauth.status_code == 401, f"Status: {r_unauth.status_code}")
    except Exception as e:
        log_test("Security", "TC-STOCK-AUTH-1", "POST /stock/analyze auth guard", False, str(e))

    test_email = f"stocklive_{int(time.time())}@example.com"
    test_pwd = "StrongPassword123!"
    try:
        client.post("/auth/signup", json={"email": test_email, "full_name": "Stock Live Tester", "password": test_pwd})
        r_login = client.post("/auth/login", json={"email": test_email, "password": test_pwd})
        if r_login.status_code != 200:
            r_login = client.post("/auth/login", data={"username": test_email, "password": test_pwd})
        token = r_login.json().get("access_token", "")
        client.headers["Authorization"] = f"Bearer {token}"
        log_test("Auth", "TC-STOCK-AUTH-2", "Authenticated test client with JWT token", bool(token), f"User: {test_email}")
    except Exception as e:
        log_test("Auth", "TC-STOCK-AUTH-2", "Authentication onboarding", False, str(e))

    # --------------------------------------------------------------------------
    # 3. Happy Path: Multi-Lens Institutional Analysis
    # --------------------------------------------------------------------------
    print("\n--- 3. HAPPY PATH: MULTI-LENS INSTITUTIONAL ANALYSIS ---")
    active_run_id = None
    chart_figures = []
    try:
        t0 = time.time()
        payload = {
            "query": "Identify top quality IT stocks with strong fundamentals and cash flow",
            "sector_filter": "Information Technology",
            "max_lenses": 2
        }
        r = client.post("/stock/analyze", json=payload)
        t_elapsed = time.time() - t0
        data = r.json()

        active_run_id = data.get("run_id")
        verified_count = data.get("verified_findings_count", 0)
        enabled_lenses = data.get("enabled_lenses", [])
        chart_figures = data.get("figures", [])
        report_url = data.get("report_url", "")
        sections = data.get("sections", {})
        exec_summary = data.get("executive_summary", "")

        passed = (
            r.status_code == 200
            and bool(active_run_id)
            and verified_count > 0
            and len(enabled_lenses) > 0
            and len(sections) == 7
            and len(exec_summary) > 50
            and "/static/report_" in report_url
        )
        log_test(
            "Analysis", "TC-STOCK-3", "POST /stock/analyze sector-filtered institutional scan",
            passed,
            f"Run ID: {active_run_id}, Verified Findings: {verified_count}, "
            f"Lenses: {len(enabled_lenses)}, Sections: {len(sections)}, "
            f"Figures: {len(chart_figures)}, Latency: {t_elapsed:.2f}s"
        )
    except Exception as e:
        log_test("Analysis", "TC-STOCK-3", "POST /stock/analyze happy path", False, str(e))

    # --------------------------------------------------------------------------
    # 4. Publication-Grade HTML Report Rendering
    # --------------------------------------------------------------------------
    print("\n--- 4. HTML REPORT RENDERING ---")
    if active_run_id:
        try:
            r = client.get(f"/stock/report/{active_run_id}")
            html_content = r.text
            passed = (
                r.status_code == 200
                and "text/html" in r.headers.get("content-type", "")
                and "NSE Institutional Stock Intelligence Report" in html_content
                and ("Executive Briefing" in html_content or "Executive Summary" in html_content)
                and "Deterministic Spine Sections" in html_content
                and "Curated Exhibits" in html_content
            )
            log_test(
                "Report", "TC-STOCK-4", f"GET /stock/report/{active_run_id} HTML compilation",
                passed, f"Status: {r.status_code}, Length: {len(html_content)} bytes"
            )
        except Exception as e:
            log_test("Report", "TC-STOCK-4", f"GET /stock/report/{active_run_id}", False, str(e))
    else:
        log_test("Report", "TC-STOCK-4", "GET /stock/report/{run_id} (Skipped: no run_id)", False, "Prior test failed to return run_id")

    # --------------------------------------------------------------------------
    # 5. Static Visual Asset Delivery
    # --------------------------------------------------------------------------
    print("\n--- 5. STATIC ASSET DELIVERY ---")
    try:
        if chart_figures:
            sample_fig = chart_figures[0]
            raw_path = sample_fig.get("file_path", "")
            # Convert app/static/... or static/... to /static/...
            static_url = "/" + raw_path.split("app/", 1)[-1] if "app/" in raw_path else f"/{raw_path}"
            r = client.get(static_url)
            passed = r.status_code == 200 and len(r.content) > 500
            log_test(
                "Static", "TC-STOCK-5", f"GET {static_url} visual exhibit delivery",
                passed, f"Status: {r.status_code}, Content-Type: {r.headers.get('content-type')}, Size: {len(r.content)} bytes"
            )
        else:
            r = client.get("/static/graph.png")
            passed = r.status_code == 200 and len(r.content) > 100
            log_test(
                "Static", "TC-STOCK-5", "GET /static/graph.png static delivery fallback",
                passed, f"Status: {r.status_code}, Size: {len(r.content)} bytes"
            )
    except Exception as e:
        log_test("Static", "TC-STOCK-5", "Static asset verification", False, str(e))

    # --------------------------------------------------------------------------
    # 6. Edge Case 1: Non-existent / Filter With No Matches
    # --------------------------------------------------------------------------
    print("\n--- 6. EDGE CASE: EMPTY SECTOR FILTER ---")
    try:
        t0 = time.time()
        payload = {
            "query": "Analyze top stocks in imaginary sector",
            "sector_filter": "QuantumNanotechnologySpaceMining",
            "max_lenses": 2
        }
        r = client.post("/stock/analyze", json=payload)
        t_elapsed = time.time() - t0
        passed = r.status_code == 200
        data = r.json()
        log_test(
            "EdgeCase", "TC-STOCK-6", "POST /stock/analyze empty sector handling (no crash)",
            passed, f"Status: {r.status_code}, Verified: {data.get('verified_findings_count', 0)}, Latency: {t_elapsed:.2f}s"
        )
    except Exception as e:
        log_test("EdgeCase", "TC-STOCK-6", "Empty sector handling", False, str(e))

    # --------------------------------------------------------------------------
    # 7. Edge Case 2: Minimal Lens Bound (max_lenses=1)
    # --------------------------------------------------------------------------
    print("\n--- 7. EDGE CASE: MINIMAL LENS BOUND (max_lenses=1) ---")
    try:
        payload = {
            "query": "Rapid liquidity screening",
            "sector_filter": "Financial Services",
            "max_lenses": 1
        }
        r = client.post("/stock/analyze", json=payload)
        data = r.json()
        lenses = data.get("enabled_lenses", [])
        passed = r.status_code == 200 and len(lenses) == 1
        log_test(
            "EdgeCase", "TC-STOCK-7", "POST /stock/analyze minimal lens bound (max_lenses=1)",
            passed, f"Status: {r.status_code}, Lenses scheduled: {lenses}"
        )
    except Exception as e:
        log_test("EdgeCase", "TC-STOCK-7", "Minimal lens bound", False, str(e))

    # --------------------------------------------------------------------------
    # 8. Edge Case 3: Lens Cap & Bounds Safety (max_lenses=25 rejected by schema)
    # --------------------------------------------------------------------------
    print("\n--- 8. EDGE CASE: LENS BOUND OVERFLOW REJECTION (max_lenses=25) ---")
    try:
        payload = {
            "query": "Comprehensive macro stress analysis",
            "sector_filter": "Automobile",
            "max_lenses": 25  # Exceeds schema constraint le=13
        }
        r = client.post("/stock/analyze", json=payload)
        # Should be rejected with 422 Unprocessable Entity
        passed = r.status_code == 422
        log_test(
            "EdgeCase", "TC-STOCK-8", "POST /stock/analyze Pydantic schema rejection on max_lenses > 13",
            passed, f"Status: {r.status_code}, Detail: {r.json().get('detail', [{}])[0].get('msg', 'N/A')}"
        )
    except Exception as e:
        log_test("EdgeCase", "TC-STOCK-8", "Lens bound overflow safety", False, str(e))

    # --------------------------------------------------------------------------
    # 9. Edge Case 4: SQL Injection / Malicious Input Safety
    # --------------------------------------------------------------------------
    print("\n--- 9. EDGE CASE: SQL INJECTION / ADVERSARIAL QUERY SAFETY ---")
    try:
        payload = {
            "query": "'; DROP TABLE nifty500; SELECT * FROM pg_user; --",
            "sector_filter": "Information Technology",
            "max_lenses": 1
        }
        r = client.post("/stock/analyze", json=payload)
        analysis_safe = r.status_code == 200

        # Verify DuckDB fact store is intact with 500 rows
        r_health = client.get("/stock/health")
        health_data = r_health.json()
        db_intact = (
            r_health.status_code == 200
            and health_data.get("nifty500_stocks_loaded") == 500
        )
        passed = analysis_safe and db_intact
        log_test(
            "EdgeCase", "TC-STOCK-9", "POST /stock/analyze SQL injection sandbox resilience",
            passed, f"Analysis Status: {r.status_code}, Post-check Records: {health_data.get('nifty500_stocks_loaded')}"
        )
    except Exception as e:
        log_test("EdgeCase", "TC-STOCK-9", "SQL injection safety check", False, str(e))

    # --------------------------------------------------------------------------
    # 10. Edge Case 5: Non-existent Run ID on Report Endpoint
    # --------------------------------------------------------------------------
    print("\n--- 10. EDGE CASE: NON-EXISTENT RUN ID 404 NOT FOUND ---")
    try:
        fake_id = "nonexistent-run-00000000"
        r = client.get(f"/stock/report/{fake_id}")
        passed = r.status_code == 404
        log_test(
            "EdgeCase", "TC-STOCK-10", "GET /stock/report/{invalid_id} returns 404 Not Found",
            passed, f"Status: {r.status_code}, Detail: {r.json().get('detail')}"
        )
    except Exception as e:
        log_test("EdgeCase", "TC-STOCK-10", "Non-existent run id check", False, str(e))

    # --------------------------------------------------------------------------
    # 11. Edge Case 6: Empty Query Input Validation
    # --------------------------------------------------------------------------
    print("\n--- 11. EDGE CASE: EMPTY QUERY HANDLING ---")
    try:
        r = client.post("/stock/analyze", json={"query": ""})
        passed = r.status_code in [200, 422]
        log_test(
            "EdgeCase", "TC-STOCK-11", "POST /stock/analyze empty string query graceful handling",
            passed, f"Status: {r.status_code}"
        )
    except Exception as e:
        log_test("EdgeCase", "TC-STOCK-11", "Empty query check", False, str(e))

    # --------------------------------------------------------------------------
    # 12. Frontend SPA Delivery & Configuration
    # --------------------------------------------------------------------------
    print("\n--- 12. FRONTEND SPA & ASSETS INTEGRITY ---")
    try:
        r_index = client.get("/")
        index_has_stock = (
            r_index.status_code == 200
            and 'data-agent-id="stock"' in r_index.text
            and "NSE Stock Swarm" in r_index.text
        )

        r_agents = client.get("/js/agents.js")
        agents_has_stock = (
            r_agents.status_code == 200
            and 'id: "stock"' in r_agents.text
            and "NSE Stock Analysis" in r_agents.text
        )

        r_config = client.get("/js/config.js")
        config_has_stock = (
            r_config.status_code == 200
            and "stock" in r_config.text
        )

        passed = index_has_stock and agents_has_stock and config_has_stock
        log_test(
            "Frontend", "TC-STOCK-12", "GET / and static JS assets include Stock Analysis agent",
            passed, f"index.html: {index_has_stock}, agents.js: {agents_has_stock}, config.js: {config_has_stock}"
        )
    except Exception as e:
        log_test("Frontend", "TC-STOCK-12", "Frontend asset verification", False, str(e))

    # --------------------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------------------
    total = results["passed"] + results["failed"]
    print("\n" + "=" * 80)
    print(f"📊 STOCK ANALYSIS TEST SUITE SUMMARY: {results['passed']}/{total} PASSED ({(results['passed']/total)*100:.1f}%)")
    print("=" * 80)
    if results["failed"] == 0:
        print("🎉 ALL INSTITUTIONAL NSE STOCK ANALYSIS TESTS PASSED SUCCESSFULLY!")
        return True
    else:
        print(f"⚠️ {results['failed']} TESTS FAILED. CHECK LOGS ABOVE.")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
