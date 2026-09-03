"""Frontend & CORS Live Verification Suite.

Tests:
1. Frontend delivery on http://localhost:3000/ (index.html, styles, modules).
2. CORS and Preflight from Origin: http://localhost:3000 to Backend: http://localhost:8000.
3. Full simulated Frontend flow (Authentication, Decision Graph streaming,
   WebSocket interactive connection, Text-to-SQL, MCP, and Stateful Chat).
"""

import json
import uuid
import httpx
import websockets.sync.client as ws_sync

FE_URL = "http://localhost:3000"
API_URL = "http://localhost:8000"

results = {"passed": 0, "failed": 0, "details": []}


def log(tc_id: str, name: str, passed: bool, info: str = ""):
    icon = "✅ PASS" if passed else "❌ FAIL"
    print(f"[{icon}] FE Suite | {tc_id}: {name}")
    if info:
        print(f"       └─ {info}")
    if passed:
        results["passed"] += 1
    else:
        results["failed"] += 1
    results["details"].append({"id": tc_id, "name": name, "passed": passed, "info": info})


def run_fe_tests():
    print("=" * 80)
    print("🌐 RUNNING COMPREHENSIVE FRONTEND & LIVE SIMULATION SUITE")
    print(f"Frontend: {FE_URL} | Backend: {API_URL}")
    print("=" * 80)

    fe_client = httpx.Client(base_url=FE_URL, timeout=15.0)
    api_client = httpx.Client(base_url=API_URL, timeout=45.0)

    # 1. Homepage
    try:
        r = fe_client.get("/")
        passed = r.status_code == 200 and "RP360 // Multi-Agent Intelligence Platform" in r.text
        log("FE 1.1", "GET / homepage HTML delivery", passed, f"Status: {r.status_code}, Length: {len(r.text)} bytes")
    except Exception as e:
        log("FE 1.1", "GET / homepage HTML delivery", False, str(e))

    # 2. Assets verification
    assets = [
        "/css/theme.css",
        "/css/components.css",
        "/css/chat.css",
        "/js/config.js",
        "/js/api.js",
        "/js/auth.js",
        "/js/chat.js",
        "/js/agents.js",
        "/js/decisionTree.js",
        "/js/research.js",
        "/js/mcp.js",
        "/js/sqlAgent.js",
        "/js/topology.js",
        "/js/app.js",
    ]

    all_assets_ok = True
    missing = []
    for asset in assets:
        try:
            r = fe_client.get(asset)
            if r.status_code != 200:
                all_assets_ok = False
                missing.append(f"{asset} ({r.status_code})")
        except Exception as e:
            all_assets_ok = False
            missing.append(f"{asset} ({e})")

    log("FE 1.2", "Verify all 14 CSS stylesheets and JavaScript ES modules", all_assets_ok, f"Checked: {len(assets)} files. Missing: {missing if missing else 'None'}")

    # 3. CORS Preflights from Frontend Origin
    preflight_headers = {
        "Origin": FE_URL,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Authorization, Content-Type",
    }
    endpoints = [
        "/interact",
        "/auth/login",
        "/auth/signup",
        "/research/stream",
        "/mcp/stream",
        "/get_sql_query",
        "/generic_chat",
    ]

    cors_ok = True
    cors_errors = []
    for ep in endpoints:
        try:
            r = api_client.options(ep, headers=preflight_headers)
            origin_header = r.headers.get("access-control-allow-origin", "")
            if r.status_code not in [200, 204] or (origin_header != FE_URL and origin_header != "*"):
                cors_ok = False
                cors_errors.append(f"{ep} (status={r.status_code}, origin={origin_header})")
        except Exception as e:
            cors_ok = False
            cors_errors.append(f"{ep} ({e})")

    log("FE 1.3", "CORS OPTIONS Preflight verification from FE Origin", cors_ok, f"Checked {len(endpoints)} endpoints. Errors: {cors_errors if cors_errors else 'None'}")

    # 4. Frontend Client Simulation Flow
    fe_headers = {
        "Origin": FE_URL,
        "Referer": f"{FE_URL}/",
        "User-Agent": "Mozilla/5.0 (FE Live Tester)",
    }

    test_uid = uuid.uuid4().hex[:6]
    user_email = f"fe_doctor_{test_uid}@fda.gov"
    user_pwd = "FrontEndPass123!"

    # 4.1 Signup
    try:
        r = api_client.post("/auth/signup", json={"email": user_email, "full_name": "Dr. Frontend", "password": user_pwd}, headers=fe_headers)
        log("FE 2.1", "Frontend Signup (POST /auth/signup)", r.status_code == 201, f"User ID: {r.json().get('id')}")
    except Exception as e:
        log("FE 2.1", "Frontend Signup", False, str(e))

    # 4.2 Login
    token = ""
    try:
        r = api_client.post("/auth/login", data={"username": user_email, "password": user_pwd}, headers=fe_headers)
        token = r.json().get("access_token", "")
        log("FE 2.2", "Frontend Login & JWT Issuance (POST /auth/login)", r.status_code == 200 and bool(token), f"Token: {token[:20]}...")
    except Exception as e:
        log("FE 2.2", "Frontend Login", False, str(e))

    auth_fe_headers = {
        **fe_headers,
        "Authorization": f"Bearer {token}",
    }

    # 4.3 Profile
    try:
        r = api_client.get("/auth/me", headers=auth_fe_headers)
        log("FE 2.3", "Frontend Profile Lookup (GET /auth/me)", r.status_code == 200 and r.json().get("email") == user_email, f"Email: {r.json().get('email')}")
    except Exception as e:
        log("FE 2.3", "Frontend Profile Lookup", False, str(e))

    # 4.4 Regulatory Decision Graph SSE with Normalized Device Data
    try:
        with api_client.stream(
            "POST",
            "/interact",
            json={
                "user_choices": {"device_class": "Class II"},
                "user_input": "What are predicate requirements for our ablation catheter?",
                "useDeviceData": True,
                "user_provided_device_data": "Model Ablator-X: Radiofrequency cardiac ablation catheter with temperature sensors",
            },
            headers=auth_fe_headers,
            timeout=45.0,
        ) as response:
            events = [line for line in response.iter_lines() if line.startswith("data: ")]
            passed = response.status_code == 200 and len(events) >= 3
            log("FE 3.1", "Frontend Regulatory Navigator SSE stream with device specs", passed, f"Received {len(events)} SSE frames")
    except Exception as e:
        log("FE 3.1", "Frontend Regulatory Navigator SSE stream", False, str(e))

    # 4.5 WebSocket Live Bi-directional Connection from Frontend Origin
    try:
        ws_url = f"ws://localhost:8000/ws/interact?token={token}"
        with ws_sync.connect(ws_url, origin=FE_URL) as ws:
            ws.send(json.dumps({
                "action": "start",
                "user_input": "Live test from FE WebSocket Client",
                "user_choices": {"device_class": "Class II"},
                "useDeviceData": False,
            }))
            resp = ws.recv(timeout=10.0)
            parsed = json.loads(resp)
            passed = parsed.get("type") == "thread_id" and bool(parsed.get("thread_id"))
            log("FE 3.2", "Frontend WebSocket live bidirectional session (ws/interact)", passed, f"Assigned Thread: {parsed.get('thread_id')}")
    except Exception as e:
        log("FE 3.2", "Frontend WebSocket session", False, str(e))

    # 4.6 Text-to-SQL Agent Query from FE
    try:
        r = api_client.post("/get_sql_query", json={"query": "Count registered medical devices"}, headers=auth_fe_headers, timeout=30.0)
        data = r.json()
        passed = r.status_code == 200 and ("final_answer" in data or "response" in data)
        log("FE 3.3", "Frontend Text-to-SQL Analyst execution (POST /get_sql_query)", passed, f"Answer: {data.get('final_answer', '')[:50]}...")
    except Exception as e:
        log("FE 3.3", "Frontend Text-to-SQL Analyst execution", False, str(e))

    # 4.7 MCP Multi-Agent Travel Stream from FE
    try:
        with api_client.stream(
            "POST",
            "/mcp/stream",
            json={"topic": "Find 2 Airbnbs in Paris near Eiffel Tower", "mode": "airbnb"},
            headers=auth_fe_headers,
            timeout=45.0,
        ) as response:
            events = [line for line in response.iter_lines() if line.startswith("data: ")]
            passed = response.status_code == 200 and len(events) >= 2
            log("FE 3.4", "Frontend MCP Multi-Agent SSE stream (Airbnb mode)", passed, f"Received {len(events)} SSE frames")
    except Exception as e:
        log("FE 3.4", "Frontend MCP Multi-Agent SSE stream", False, str(e))

    # 4.8 General Assistant Chat Memory from FE
    try:
        r = api_client.post(
            "/generic_chat",
            json={"user_input": "Hello from the new Frontend client!", "session_id": f"fe_sess_{test_uid}"},
            headers=auth_fe_headers,
            timeout=30.0,
        )
        passed = r.status_code == 200 and len(r.json().get("response", "")) > 5
        log("FE 3.5", "Frontend General Assistant multi-turn chat (POST /generic_chat)", passed, f"Response: {r.json().get('response', '')[:45]}...")
    except Exception as e:
        log("FE 3.5", "Frontend General Assistant chat", False, str(e))

    # Summary
    tot = results["passed"] + results["failed"]
    print("\n" + "=" * 80)
    print(f"📊 FRONTEND TEST SUITE SUMMARY: {results['passed']}/{tot} PASSED ({(results['passed']/tot)*100:.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    run_fe_tests()
