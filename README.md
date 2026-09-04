# 🚀 Enterprise LangGraph Production Architecture Template

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Langfuse](https://img.shields.io/badge/Observability-Langfuse-purple.svg)](https://langfuse.com/)
[![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED.svg)](https://www.docker.com/)
[![uv](https://img.shields.io/badge/Package%20Manager-uv-blueviolet.svg)](https://astral.sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A reference implementation and production-grade boilerplate for building robust, observable, and stateful AI agent applications with **LangGraph**, **FastAPI**, **OAuth2 Multi-DB Authentication & Blacklisting**, **Agent Middleware Suite (PII, Rate Limiting, HITL, Summarization)**, **Per-Agent Token Budgeting**, **Parallel Multi-Critic Research (`defer=True`)**, **Institutional NSE Stock Analysis Swarm (13 Lenses, DuckDB Fact Store, Pinecone MCP, Yahoo Finance & LangChain Deep Agents Sandboxes)**, **Isolated Quant Financial Modeling (5,000-Path Monte Carlo & Markowitz Optimization)**, **PostgreSQL Checkpointing (`AsyncPostgresSaver`)**, **Langfuse Tracing**, **Server-Sent Events (SSE)**, and **WebSocket Streaming**.

---

## 📑 Table of Contents

- [Architectural Overview](#-architectural-overview)
  - [0. Agent Architecture & Cognitive Subsystems](#0-agent-architecture--cognitive-subsystems)
  - [1. System Gateway & Multi-DB Architecture (Authentication, Authorization & Guarded Endpoints)](#1-system-gateway--multi-db-architecture-authentication-authorization--guarded-endpoints)
    - [A. End-to-End System Gateway & Multi-DB Gateway Topology](#a-end-to-end-system-gateway--multi-db-gateway-topology)
    - [B. Authentication Lifecycle & Cryptographic Pipeline](#b-authentication-lifecycle--cryptographic-pipeline-appcoresecuritypy--appcoreauth_databasepy)
    - [C. Authorization Engine & Guard Pipeline](#c-authorization-engine--guard-pipeline-appapidepspy)
    - [D. Accessing Guarded Endpoints & Tenant Isolation](#d-accessing-guarded-endpoints--tenant-isolation)
    - [E. WebSocket Handshake & Streaming Authentication](#e-websocket-handshake--streaming-authentication-appapiv1endpointswebsocketpy)
    - [F. Comprehensive Execution Path & Technical Component Matrix](#f-comprehensive-execution-path--technical-component-matrix)
    - [G. Technology Stack, Specific Packages & Architectural Roles](#g-technology-stack-specific-packages--architectural-roles)
  - [2. Workflow Graphs](#2-workflow-graphs)
    - [A. Policy Decision-Tree Graph](#a-policy-decision-tree-graph-stateful-human-in-the-loop)
    - [B. Parallel Multi-Critic Research Graph](#b-parallel-multi-critic-research-graph-defer--true-join)
    - [C. Model Context Protocol (MCP) Multi-Agent Intelligence Graphs](#c-model-context-protocol-mcp-multi-agent-intelligence-graphs)
    - [D. Text-to-SQL Analyst Architecture Graph](#d-text-to-sql-analyst-architecture-graph-sqldatabasetoolkit)
    - [F. Institutional NSE Stock Analysis Swarm Architecture](#f-institutional-nse-stock-analysis-swarm-architecture-deepagents--duckdb--pinecone-mcp--yahoo-finance--gnews)
    - [G. Master Deep Agent Query Planning & Multi-Store Ingestion Architecture](#g-master-deep-agent-query-planning--multi-store-ingestion-architecture)
    - [H. Institutional Surveillance Dossier & Visual Report Pipeline](#h-institutional-surveillance-dossier--visual-report-pipeline)
    - [I. LangChain Deep Agents Sandboxes Architecture & Quant Modeling](#i-langchain-deep-agents-sandboxes-architecture-appcoresandbox)
- [Core Mechanisms & Design Patterns](#-core-mechanisms--design-patterns)
- [Project Directory Structure](#-project-directory-structure)
- [API Endpoints Specification](#-api-endpoints-specification)
- [Environment Configuration](#-environment-configuration)
- [Quickstart & Running Locally](#-quickstart--running-locally)
- [Docker & Docker Compose](#-docker--docker-compose)
- [Streaming & Interrupt Client Usage](#-streaming--interrupt-client-usage)
- [Adapting for Future Projects](#-adapting-for-future-projects)

---

## 🏛️ Architectural Overview

### 0. Agent Architecture & Cognitive Subsystems

<p align="center">
  <img src="./assets/agent_architecture.png" alt="Agent Cognitive Architecture" width="850"/>
</p>

The architecture implements an end-to-end agentic workflow combining:
- **Planning & Reasoning:** Chain of thoughts, Reflection, Self-critics, Subgoal decomposition, and parallel review pipelines (`defer=True`).
- **Memory Systems:** Short-term state memory (`add_messages` reducer) and Long-term thread memory (`AsyncPostgresSaver` PostgreSQL checkpointing).
- **Tools & Model Context Protocol (MCP):** Dynamic tool binding, stdio MCP server integrations, geocoding, meteorological forecasts, and API tools.
- **Action Execution:** Coordinated fan-out/fan-in graph node execution and real-time streaming output.

---

### 1. System Gateway & Multi-DB Architecture (Authentication, Authorization & Guarded Endpoints)

The platform implements an **Enterprise Zero-Trust Dual-Database Gateway Architecture** that decouples identity management and security credentials (`auth_db`) from agentic execution, state checkpointing, and thread histories (`agent_db`).

Every incoming request flows through a strict multi-layer defense pipeline consisting of:
1. **Network & Transport Layer:** CORS origin validation and WebSocket handshake validation.
2. **Authentication Subsystem (`auth_db`):** OWASP-compliant Argon2id password hashing, time-limited cryptographic JWT issuance, and persistent JTI revocation blacklisting.
3. **Authorization & Guard Pipeline (`app/api/deps.py`):** OAuth2 Bearer token extraction, signature verification, expiration checks, blacklisting queries, and Role-Based Access Control (RBAC).
4. **Tenant Isolation & Context Propagation:** Dynamic thread namespace isolation (`user-{id}-{uuid}`) and Langfuse `RunnableConfig` metadata binding.
5. **Agent Middleware Interception (`app/middleware/`):** Sliding-window rate limiting, PII/PHI sanitization, human-in-the-loop tool approvals, and chat summarization.
6. **Execution Engines & State Persistence (`agent_db`):** LangGraph StateGraphs, `AsyncPostgresSaver` checkpointing, stdio Model Context Protocol (MCP) servers, and PostgreSQL chat memory.

---

#### A. End-to-End System Architecture Overview

The platform implements an **Enterprise Zero-Trust Dual-Database Architecture** organized into 4 intuitive, decoupled tiers:

```mermaid
flowchart TD
    subgraph Clients ["1. Client Tier"]
        UI["🖥️ Modern Web SPA (Tailwind + Vanilla JS)"]
        External["📱 External REST & WebSocket Clients"]
    end

    subgraph GatewayLayer ["2. API Gateway & Security Layer (FastAPI :8000)"]
        direction TB
        APIGateway["🚪 FastAPI Unified Router\n(/auth, /stock, /research, /interact, /mcp, /chat)"]
        
        subgraph SecuritySuite ["Security & Guard Pipeline"]
            AuthGuard["🛡️ Auth & RBAC Guard\n(JWT Bearer Verification + JTI Blacklist Check)"]
            Middleware["⚙️ Agent Middleware Suite\n(Rate Limiter, PII Sanitizer, HITL Interrupts)"]
        end
        APIGateway --> AuthGuard --> Middleware
    end

    subgraph EngineLayer ["3. Autonomous Agent & Execution Engines"]
        direction LR
        StockEngine["📈 Stock Analysis Swarm\n(Master Planner + 13 Specialized Lenses)"]
        ResearchEngine["🔍 Multi-Critic Research\n(Parallel Fact/Style Critics + Live Search)"]
        MCPEngine["🔌 MCP Integrations\n(Pinecone Vector & OpenBnB Tools)"]
        PolicyEngine["📋 Policy & SQL Agents\n(Decision Tree & Database Toolkit)"]
        QuantSandbox["⚡ Deep Agents Quant Sandbox\n(Subprocess/Docker 512MB RAM Ceiling)"]
    end

    subgraph DataLayer ["4. Dual-Database Storage Tier (PostgreSQL :5432)"]
        AuthDB[("🔐 auth_db\n• User Accounts & Roles\n• Argon2id Password Hashes\n• Revoked Token Blacklist")]
        AgentDB[("📦 agent_db\n• LangGraph Thread Checkpoints\n• Thread State Blobs\n• Chat Message Histories")]
    end

    UI & External -->|HTTP REST / SSE / WebSocket| APIGateway
    AuthGuard <-->|Verify Credentials & Check Blacklist| AuthDB
    Middleware --> StockEngine & ResearchEngine & MCPEngine & PolicyEngine
    StockEngine -->|Isolated Math Execution| QuantSandbox
    StockEngine & ResearchEngine & PolicyEngine <-->|Hydrate / Persist State| AgentDB
```

The system operates across 4 distinct layers:
1. **Client Tier**: Web SPA, REST, and WebSocket clients authenticate via `/auth/login` to obtain an HS256 JWT access token.
2. **API Gateway & Security Layer (`FastAPI :8000`)**: Single entry point with CORS, exception handling, and routing. Public endpoints handle onboarding and password resets. Protected endpoints pass through the OAuth2 Bearer security guard (`app/api/deps.py`) to verify signatures, check expiration, assert non-revocation against `auth_db.token_blacklist`, and enforce role permissions before triggering rate-limiting and PII sanitization middlewares.
3. **Autonomous Agent Engines**: Guarded endpoints route to specialized LangGraph execution graphs:
   - **Stock Analysis Swarm**: 15-node StateGraph led by the Master Deep Agent Planner across 13 specialized analytical lenses.
   - **Multi-Critic Research**: Parallel research synthesis pipeline with live DuckDuckGo Search and `defer=True` critics.
   - **Model Context Protocol (MCP)**: Dynamic tool discovery and stdio client connections to Pinecone and OpenBnB servers.
   - **Policy & Text-to-SQL**: Deterministic decision-tree navigation and read-only PostgreSQL database introspection.
   - **Deep Agents Quant Sandbox**: Isolated execution environment enforcing resource limits for Monte Carlo and portfolio optimization.
4. **Dual-Database Storage Tier (`PostgreSQL :5432`)**: Strict separation of concerns between security and execution:
   - `auth_db`: OWASP-compliant Argon2id user credentials, active statuses, and real-time revoked token blacklist (`psycopg==3.3.4`).
   - `agent_db`: Thread checkpointing (`AsyncPostgresSaver`), binary state snapshots (`checkpoint_blobs`), and conversation histories (`PostgresChatMessageHistory`).

---

#### B. Authentication Lifecycle & Cryptographic Pipeline (`app/core/security.py` & `app/core/auth_database.py`)

The authentication subsystem handles identity lifecycle events with industry-standard cryptographic primitives:

1. **Password Hashing with Argon2id (`pwdlib==0.3.1` & `argon2-cffi==25.1.0`)**: Plaintext passwords are never stored. The system uses `pwdlib.PasswordHash.recommended()` (Argon2id), providing memory-hard protection resistant to GPU and ASIC brute-force attacks.
2. **Access Token Minting (`pyjwt==2.13.0`)**: Upon successful authentication, the server issues a signed JWT (`HS256`) with a cryptographically unique `jti` (UUID v4) and the following payload:
   ```json
   {
     "sub": "user@example.com",
     "user_id": "8f3b2a7d-5e2a-4a6c-9c1e-3b2a7d5e2a4a",
     "role": "user",
     "iat": 1772520000,
     "exp": 1772523600,
     "jti": "d3b07384-d113-424a-93f8-5807908b8d42",
     "token_type": "access"
   }
   ```
3. **Stateful Token Revocation (`psycopg==3.3.4` in `auth_db.token_blacklist`)**: When a user calls `POST /auth/logout`, the token's unique identifier (`jti`) and its expiration timestamp (`exp`) are committed to the `token_blacklist` table in `auth_db`. Any subsequent request presenting this token is immediately rejected with `401 Unauthorized`.
4. **Time-Limited Password Reset (`hashlib.sha256`)**: The `/auth/forgot-password` endpoint issues a single-use 15-minute token with `token_type: "reset_password"`. The SHA-256 hash of this token is stored in `password_reset_tokens`. When consumed via `/auth/reset-password`, the token is marked `is_used = TRUE` inside an atomic transaction, preventing replay attacks.

```mermaid
sequenceDiagram
    autonumber
    actor Client as Browser Client (SPA Fetch API)
    participant Gateway as FastAPI Router (app/api/v1/endpoints/auth.py)
    participant Security as Security & Crypto (pwdlib & pyjwt)
    participant AuthDB as PostgreSQL auth_db (psycopg==3.3.4 pool)

    Note over Client,AuthDB: Scenario 1: User Registration (/auth/signup) [Pydantic: UserSignupRequest]
    Client->>Gateway: POST /auth/signup (email, password, full_name)
    Gateway->>AuthDB: SELECT 1 FROM users WHERE email = %s
    AuthDB-->>Gateway: None (User does not exist)
    Gateway->>Security: pwdlib.hash(password) -> Argon2id ($argon2id$v=19$m=65536...)
    Security-->>Gateway: Hashed password string
    Gateway->>AuthDB: INSERT INTO users (id, email, hashed_password, role...) VALUES (%s...)
    AuthDB-->>Gateway: Created User Record (UUID: 8f3b2a7d...)
    Gateway-->>Client: 201 Created (UserResponse without password)

    Note over Client,AuthDB: Scenario 2: User Login & JWT Token Minting (/auth/login) [python-multipart]
    Client->>Gateway: POST /auth/login (OAuth2 Form / JSON: username=email, password)
    Gateway->>AuthDB: SELECT * FROM users WHERE email = %s
    AuthDB-->>Gateway: User Record (with hashed_password, is_active)
    Gateway->>Security: pwdlib.verify(plain_pwd, hashed_pwd) [constant-time]
    Security-->>Gateway: True (Password matched)
    Gateway->>Security: pyjwt.encode(payload={sub, user_id, role, iat, exp, jti}, JWT_SECRET_KEY, HS256)
    Security-->>Gateway: Signed Bearer JWT Access Token
    Gateway-->>Client: 200 OK (TokenResponse: access_token, token_type: "bearer", expires_in: 60)

    Note over Client,AuthDB: Scenario 3: User Logout & Revocation (/auth/logout) [Depends(get_current_active_user)]
    Client->>Gateway: POST /auth/logout (Header: Authorization: Bearer <token>)
    Gateway->>Security: pyjwt.decode(token) -> Extract 'jti' and 'exp'
    Security-->>Gateway: Claims Payload {jti, exp, sub...}
    Gateway->>AuthDB: INSERT INTO token_blacklist (token_jti, user_id, expires_at) VALUES (%s, %s, %s)
    AuthDB-->>Gateway: Row inserted & committed
    Gateway-->>Client: 200 OK (MessageResponse: "Token revoked successfully")

    Note over Client,AuthDB: Scenario 4: Password Reset Flow (/auth/forgot-password & /auth/reset-password)
    Client->>Gateway: POST /auth/forgot-password (email)
    Gateway->>AuthDB: SELECT id, email FROM users WHERE email = %s
    AuthDB-->>Gateway: Found User Record
    Gateway->>Security: pyjwt.encode(payload={sub, user_id, token_type='reset_password', exp=15m})
    Security-->>Gateway: Reset JWT Token
    Gateway->>Gateway: hashlib.sha256(reset_token.encode()).hexdigest()
    Gateway->>AuthDB: INSERT INTO password_reset_tokens (user_id, token_hash, expires_at) VALUES (...)
    Gateway-->>Client: 200 OK (reset_token generated)
    Client->>Gateway: POST /auth/reset-password (token, new_password)
    Gateway->>Security: pyjwt.decode(token) -> Assert token_type == 'reset_password'
    Gateway->>AuthDB: UPDATE password_reset_tokens SET is_used=TRUE WHERE token_hash=%s RETURNING user_id
    Gateway->>Security: pwdlib.hash(new_password) -> New Argon2id Hash
    Gateway->>AuthDB: UPDATE users SET hashed_password = %s WHERE id = %s
    Gateway-->>Client: 200 OK (MessageResponse: "Password reset successfully")
```

---

#### C. Authorization Engine & Guard Pipeline (`app/api/deps.py`)

Access to protected agent endpoints is guarded by FastAPI's Dependency Injection system. Each guarded route declares dependencies such as `Depends(get_current_active_user)`.

```
HTTP Request with Header: "Authorization: Bearer <token>"
                           │
                           ▼
              ┌──────────────────────────┐
              │      oauth2_scheme       │  Extracts raw Bearer token string
              └────────────┬─────────────┘
                           ▼
              ┌──────────────────────────┐
              │      decode_token()      │  Validates HS256 signature and exp timestamp
              └────────────┬─────────────┘
                           ▼
              ┌──────────────────────────┐
              │  is_token_blacklisted()  │  Queries auth_db token_blacklist table by JTI
              └────────────┬─────────────┘
                           ▼
              ┌──────────────────────────┐
              │   get_user_by_email()    │  Queries auth_db users table by 'sub' claim
              └────────────┬─────────────┘
                           ▼
              ┌──────────────────────────┐
              │ get_current_active_user  │  Asserts user.is_active == True
              └────────────┬─────────────┘
                           ▼
              ┌──────────────────────────┐
              │    require_role(...)     │  (Optional) Enforces Role-Based Access Control
              └────────────┬─────────────┘
                           ▼
         Injected UserResponse into Route Handler
```

The authorization sequence enforces the following verification steps:
1. **Header Parsing:** `oauth2_scheme` extracts the bearer token from the `Authorization: Bearer <token>` HTTP header.
2. **Signature & Expiration Validation:** `decode_token()` validates the cryptographic HMAC-SHA256 signature using `settings.JWT_SECRET_KEY` and confirms that `exp > current_utc_time`.
3. **Revocation Query:** The unique `jti` claim is looked up in the `token_blacklist` table in `auth_db`. If found, a `401 Unauthorized` exception is thrown immediately.
4. **Entity Resolution:** The user's current account record is retrieved from `auth_db` by email (`sub`), ensuring that deleted users cannot access the system even with a cryptographically valid token.
5. **Account Status Verification:** `get_current_active_user` verifies that `is_active` is true. Deactivated accounts receive `403 Forbidden`.
6. **Role-Based Access Control (RBAC):** `require_role("admin", "operator")` asserts that `current_user.role` matches the allowed role set, bypassing checks for superusers (`is_superuser == True`).

---

#### D. Accessing Guarded Endpoints & Tenant Isolation

Once authorization succeeds, FastAPI injects the authenticated `UserResponse` object (`current_user`) directly into the route handler. The endpoint then orchestrates tenant isolation, middleware execution, and state persistence:

```mermaid
sequenceDiagram
    autonumber
    actor Client as Browser Client (EventSource / Fetch API)
    participant CORS as CORS & Router (fastapi.middleware.cors)
    participant Deps as FastAPI Guard Pipeline (deps.py Depends(get_current_active_user))
    participant AuthDB as PostgreSQL auth_db (psycopg==3.3.4 AsyncConnectionPool)
    participant Middleware as Agent Middleware Suite (RateLimit, PII, HITL, Summarizer)
    participant Endpoint as Guarded Endpoint Handler (app/api/v1/endpoints/*.py)
    participant Engine as LangGraph Engine (astream_events version='v2')
    participant AgentDB as PostgreSQL agent_db (AsyncPostgresSaver)
    participant Langfuse as Langfuse Observability (langfuse==4.14.4 CallbackHandler)

    Client->>CORS: HTTP Request with Header: "Authorization: Bearer <jwt_access_token>"
    CORS->>Deps: Invoke Dependency: get_current_active_user()
    
    rect rgb(240, 245, 255)
        Note over Deps,AuthDB: Security Verification & Revocation Pipeline
        Deps->>Deps: fastapi.security.OAuth2PasswordBearer extracts raw Bearer token string
        Deps->>Deps: pyjwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        alt Signature Tampered or Expired (exp <= utcnow)
            Deps-->>Client: 401 Unauthorized ("Token has expired" or "Invalid token")
        end
        Deps->>AuthDB: psycopg: SELECT 1 FROM token_blacklist WHERE token_jti = %s
        alt Token JTI Found in Blacklist
            AuthDB-->>Deps: Row Exists (Token was revoked via /auth/logout)
            Deps-->>Client: 401 Unauthorized ("Token has been revoked. Please log in again.")
        end
        Deps->>AuthDB: psycopg: SELECT id, email, role, is_active FROM users WHERE email = %s
        alt User Not Found or Inactive (is_active == False)
            Deps-->>Client: 401 Unauthorized / 403 Forbidden ("User account is deactivated")
        end
        Deps->>Deps: Instantiate UserResponse(id=uuid, email=sub, role=role, is_active=True)
    end

    Deps->>Endpoint: Inject current_user: UserResponse into route handler

    rect rgb(245, 255, 245)
        Note over Endpoint,Middleware: Tenant Isolation & Middleware Interception
        Endpoint->>Endpoint: Enforce Namespace: thread_id = f"user-{current_user.id}-{uuid.uuid4()}"
        Endpoint->>Endpoint: get_runnable_config(thread_id, metadata={"user_id": current_user.id, "email": current_user.email})
        Endpoint->>Middleware: pipeline.run_before_agent(state)
        Middleware->>Middleware: RateLimitMiddleware: check sliding window timestamp queue (collections.deque per user_id)
        alt Rate Limit Exceeded (> 60 req / 60s)
            Middleware-->>Client: 429 Too Many Requests ("Rate limit exceeded. Retry in 60s")
        end
        Middleware->>Middleware: PIIMiddleware: regex + Luhn scan -> mask SSN, credit cards, emails, PHI
    end

    rect rgb(255, 250, 240)
        Note over Endpoint,Langfuse: Execution, Checkpointing & Real-Time Streaming
        Endpoint->>Engine: graph.astream_events(inputs, config=thread_config, version="v2")
        Engine<<->>AgentDB: AsyncPostgresSaver(pool): Save/Load thread checkpoint blobs & writes
        Engine->>Langfuse: CallbackHandler records non-blocking traces, latency & token usage
        Engine-->>Endpoint: Yield event dicts (on_chat_model_stream tokens, stage hints)
    end

    Endpoint-->>Client: FastAPI StreamingResponse: data: {"token": "...", "stage": "..."}\n\n (text/event-stream)
```

##### 1. User Isolation & Multi-Tenancy
- **Thread ID Namespacing:** If a client does not provide a `thread_id`, the system deterministically binds the conversation to the user ID:
  ```python
  thread_id = request.thread_id or f"user-{current_user.id}-{uuid.uuid4()}"
  ```
- **Checkpoint Isolation:** Checkpoints stored in `agent_db` via `AsyncPostgresSaver` are partitioned by `thread_id`. Users cannot access or overwrite state belonging to another tenant.
- **Observability Audit Trail:** The `RunnableConfig` tags all LangGraph executions and Langfuse traces with the authenticated user context:
  ```python
  thread_config = get_runnable_config(
      thread_id=thread_id,
      metadata={"user_id": current_user.id, "email": current_user.email},
  )
  ```

##### 2. Agent Middleware Execution Suite (`app/middleware/`)
Every guarded path passes through the middleware pipeline before invoking LLMs or external tools:
- **`RateLimitMiddleware`:** Tracks request timestamps per `user_id` using an in-memory sliding window (60 requests/60s). It also maintains an error budget; 3 consecutive agent execution failures trigger an immediate circuit-breaker timeout.
- **`PIIMiddleware`:** Scans user inputs and intermediate state values for emails, phone numbers, Social Security Numbers (SSNs), credit cards, and Protected Health Information (MRN/PHI), replacing them with sanitized tokens (`[REDACTED_EMAIL]`, `[MASKED_SSN]`) before LLM reasoning.
- **`HumanInTheLoopMiddleware`:** Intercepts sensitive or destructive tool invocations, pausing graph execution via LangGraph's `interrupt()` primitive until explicit administrative approval is provided.
- **`SummarizationMiddleware`:** Monitors cumulative token counts and message history lengths (`trigger=[("tokens", 1200), ("messages", 8)]`), automatically condensing older dialog turns into a concise executive summary.

---

#### E. WebSocket Handshake & Streaming Authentication (`app/api/v1/endpoints/websocket.py`)

Because standard browser WebSocket APIs cannot send custom HTTP authorization headers during the initial handshake, the gateway implements a specialized handshake protocol:

```mermaid
sequenceDiagram
    autonumber
    actor Client as Browser WebSocket Client (new WebSocket)
    participant Gateway as WebSocket Gateway (app/api/v1/endpoints/websocket.py)
    participant Security as Security & AuthDB (pyjwt & psycopg==3.3.4)
    participant LangGraph as LangGraph Execution Engine (astream_events)
    participant Checkpointer as AsyncPostgresSaver (agent_db)

    Client->>Gateway: WS Handshake: ws://localhost:8000/ws/interact?token=<JWT>
    Gateway->>Security: authenticate_websocket(websocket)
    Note over Gateway,Security: Extract token from websocket.query_params.get("token")
    Security->>Security: pyjwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
    Security->>Security: psycopg: SELECT 1 FROM token_blacklist WHERE token_jti = %s
    Security->>Security: psycopg: SELECT * FROM users WHERE email = %s (assert is_active)

    alt Validation Fails or Token Missing/Revoked
        Gateway-->>Client: websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
    else Validation Passes
        Gateway-->>Client: await websocket.accept() (101 Switching Protocols)
        Gateway->>Client: websocket.send_json({"type": "thread_id", "thread_id": "user-uuid..."})
        
        loop Bi-directional Streaming Interaction
            Client->>Gateway: websocket.receive_text() -> json.loads() {"action": "start" | "resume", "user_input": "..."}
            Gateway->>LangGraph: astream_events(inputs, config=thread_config, version="v2")
            LangGraph<<->>Checkpointer: AsyncPostgresSaver: persist state snapshots in agent_db
            LangGraph-->>Gateway: Yield real-time model tokens and stage execution hints
            Gateway-->>Client: websocket.send_json({"type": "token", "token": "..."})
        end
    end
```

1. **Handshake Extraction:** The client connects with `ws://localhost:8000/ws/interact?token=<jwt_access_token>`. The gateway inspects `websocket.query_params["token"]` (falling back to `websocket.headers["authorization"]`).
2. **Pre-Acceptance Verification:** Before calling `websocket.accept()`, the server decodes the token, checks the `token_blacklist` table in `auth_db`, and confirms the user account is active.
3. **Policy Violation Rejection:** If authentication fails, the server closes the connection immediately with status `1008 Policy Violation`, preventing unauthenticated socket connections from consuming server resources.
4. **Bidirectional State Streaming:** Once connected, the client sends structured JSON commands (`start`, `resume`). Real-time tokens and node execution hints stream back over the established full-duplex connection.

---

#### F. Comprehensive Execution Path & Technical Component Matrix

The table below details every request path through the system, the security dependencies applied, the databases accessed, and the runtime components involved:

| Request Path & Method | Protocol | Auth & Security Dependency | Databases Involved | Middleware Executed | Execution Engine / Runtime | Resulting Artifact & Response |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`POST /auth/signup`** | HTTP REST | Public (None) | `auth_db` (`users`) | None | Argon2id Password Hasher | `UserResponse` JSON (201 Created) |
| **`POST /auth/login`** | HTTP REST | Public (Form/JSON parser) | `auth_db` (`users`) | None | PyJWT Token Minting | `TokenResponse` with Bearer JWT |
| **`POST /auth/logout`** | HTTP REST | `Depends(get_current_active_user)` | `auth_db` (`token_blacklist`) | None | JTI Blacklist Ingestion | `MessageResponse` confirmation |
| **`POST /auth/forgot-password`** | HTTP REST | Public (None) | `auth_db` (`password_reset_tokens`) | None | SHA-256 Token Generation | Cryptographic reset token |
| **`POST /auth/reset-password`** | HTTP REST | Public (Reset Token) | `auth_db` (`users`, `password_reset_tokens`) | None | Argon2id Hash & Token Invalidation | `MessageResponse` confirmation |
| **`POST /interact`** | HTTP SSE | `Depends(get_current_active_user)` | `auth_db` (Auth), `agent_db` (Checkpoints) | RateLimit, PII, HITL, Summarizer | LangGraph Policy StateGraph | SSE stream (`text/event-stream`) |
| **`GET /thread/{id}/state`** | HTTP REST | `Depends(get_current_active_user)` | `agent_db` (`checkpoints`) | None | `AsyncPostgresSaver.aget_state` | `GraphStateResponse` JSON |
| **`DELETE /delete_thread`** | HTTP REST | `Depends(get_current_active_user)` | `agent_db` (`checkpoints`) | None | Checkpoint Deletion | `DeleteThreadResponse` JSON |
| **`POST /research/run`** | HTTP REST | `Depends(get_current_active_user)` | `auth_db` (Auth), `agent_db` (State) | RateLimit, PII | Parallel Research (`defer=True`) | `ResearchResponse` JSON |
| **`POST /research/stream`** | HTTP SSE | `Depends(get_current_active_user)` | `auth_db` (Auth), `agent_db` (State) | RateLimit, PII | Parallel Research (`defer=True`) | SSE stream (`text/event-stream`) |
| **`GET /mcp/tools`** | HTTP REST | `Depends(get_current_active_user)` | `auth_db` (Auth) | None | `MCPClientManager.get_server_status()` | `MCPToolsListResponse` JSON |
| **`POST /mcp/run`** | HTTP REST | `Depends(get_current_active_user)` | `auth_db` (Auth) | RateLimit, PII | Pinecone/Airbnb MCP stdio Workers | `MCPResponse` JSON |
| **`POST /mcp/stream`** | HTTP SSE | `Depends(get_current_active_user)` | `auth_db` (Auth) | RateLimit, PII | Pinecone/Airbnb MCP stdio Workers | SSE stream (`text/event-stream`) |
| **`POST /generic_chat`** | HTTP REST | `Depends(get_current_active_user)` | `auth_db` (Auth), `agent_db` (`chat_history`) | RateLimit, PII, Summarizer | `PostgresChatMessageHistory` + Groq | `ChatResponse` JSON |
| **`DELETE /delete_session`** | HTTP REST | `Depends(get_current_active_user)` | `agent_db` (`chat_history`) | None | Session Message Eviction | `DeleteSessionResponse` JSON |
| **`POST /get_sql_query`** | HTTP REST | `Depends(get_current_active_user)` | `auth_db` (Auth), `agent_db` (SQL Schema) | RateLimit, PII, HITL | `create_sql_agent` (SQLDatabaseToolkit) | `SQLQueryResponse` JSON + Data Table |
| **`WS /ws/interact`** | WebSocket | Query Param `?token=` Handshake | `auth_db` (Auth), `agent_db` (Checkpoints) | RateLimit, PII, HITL | Bi-directional LangGraph Runner | Full-duplex JSON streaming frames |

---

#### G. Technology Stack, Specific Packages & Architectural Roles

Every stage of the authentication, authorization, database persistence, and agent execution lifecycle is powered by battle-tested, specialized open-source libraries:

##### 1. FastAPI & ASGI Gateway Layer
- **`fastapi` (`fastapi==0.141.1`)**: Core async framework providing high-throughput endpoint routing, OpenAPI / Swagger documentation generation, dependency injection, and declarative request/response validation.
- **`starlette` (`starlette==1.6.0`)**: Low-level ASGI toolkit underlying FastAPI, providing base classes for `Request`, `Response`, `StreamingResponse`, and `WebSocket`.
- **`uvicorn` (`uvicorn==0.52.4`) + `uvloop` (`uvloop==0.22.1`) + `httptools` (`httptools==0.8.0`)**: Production ASGI server stack utilizing the C-based Linux epoll event loop (`uvloop`) and high-speed C HTTP parser (`httptools`) for microsecond-level request dispatch.
- **`fastapi.security.OAuth2PasswordBearer`**: Native security scheme that extracts the bearer token from the `Authorization: Bearer <token>` HTTP header and automatically configures interactive Bearer authentication in Swagger UI (`/docs`).
- **`python-multipart` (`python-multipart==0.0.32`)**: Streaming parser for `application/x-www-form-urlencoded` and multipart form requests, enabling native OAuth2 password grant form handling on `/auth/login`.
- **`fastapi.middleware.cors.CORSMiddleware`**: Intercepts preflight `OPTIONS` requests, verifies origin whitelisting against `settings.CORS_ORIGINS`, and injects appropriate `Access-Control-Allow-*` headers.
- **`fastapi.responses.StreamingResponse`**: Manages chunked Server-Sent Events (SSE) data streams (`media_type="text/event-stream"`), streaming real-time LLM token chunks and dynamic agent progress hints without buffering.
- **`fastapi.WebSocket` & `fastapi.WebSocketDisconnect`**: Manages the bi-directional TCP socket lifecycle, supporting connection upgrade, query-token authorization, policy violation closing (`WS_1008_POLICY_VIOLATION`), and real-time frame distribution.

##### 2. Authentication, Cryptography & Security Layer
- **`pwdlib` (`pwdlib==0.3.1`) & `argon2-cffi` (`argon2-cffi==25.1.0`)**:
  - **Algorithm**: `PasswordHash.recommended()` configures **Argon2id** (the PHC winner and OWASP #1 recommended password hash).
  - **Parameters**: Salted hash with memory-hardness ($m=65536$, $t=3$, $p=4$) preventing GPU, ASIC, and rainbow table brute-force attacks.
  - **Immunity**: Constant-time verification (`password_hasher.verify()`) protects against side-channel timing attacks.
- **`pyjwt` (`pyjwt==2.13.0`)**:
  - **Token Engine**: Signs and decodes JSON Web Tokens using cryptographic HMAC-SHA256 (`HS256`) against `settings.JWT_SECRET_KEY`.
  - **Claims Verification**: Emits and validates standard RFC 7519 claims: `sub` (email), `user_id` (UUID), `role`, `iat` (issued at), `exp` (60m access expiry, 15m reset expiry), `jti` (unique token ID), and `token_type`.
  - **Tamper Protection**: Detects token tampering, invalid signatures (`InvalidTokenError`), and expired tokens (`ExpiredSignatureError`).
- **`hashlib` (Python Standard Library)**:
  - Computes SHA-256 digests (`hashlib.sha256(token.encode()).hexdigest()`) of password reset tokens before storing them in `password_reset_tokens` in `auth_db`. Plaintext reset tokens are never persisted, preventing credential compromise even if the database is leaked.
- **`uuid` (Python Standard Library)**:
  - Generates cryptographically isolated UUID v4 identifiers for user primary keys (`gen_random_uuid()`), unique `jti` token fingerprints, and tenant thread namespaces (`user-{id}-{uuid}`).

##### 3. Database Driver, Connection Pooling & Checkpointing Layer
- **`psycopg` (`psycopg==3.3.4`) & `psycopg-binary`**:
  - Modern, native asynchronous PostgreSQL 3 driver utilizing Python's `async/await` syntax.
  - **SQL Injection Prevention**: Parameterized query execution using `%s` placeholders for all dynamic inputs across user lookups, token insertions, and blacklist queries.
  - **Row Factory**: Configured with `row_factory=dict_row` to automatically convert SQL result tuples into native Python dictionaries keyed by column name.
- **`psycopg-pool` (`psycopg-pool==3.3.1`)**:
  - `AsyncConnectionPool`: Maintains high-performance connection pools for both `auth_db` and `agent_db` (`min_size=2`, `max_size=10`). Reuses pre-established TCP database connections and eliminates connection handshake latency on every request.
- **`langgraph-checkpoint-postgres` (`langgraph-checkpoint-postgres==3.1.2`)**:
  - `AsyncPostgresSaver`: Implements persistent distributed checkpointing for LangGraph StateGraphs. Checkpoints thread states, node outputs, and channels directly into PostgreSQL, enabling state hydration, graph rollback, and human-in-the-loop resumes.
- **`langchain-postgres` (`langchain-postgres==0.0.17`)**:
  - `PostgresChatMessageHistory`: Manages conversational memory persistence in PostgreSQL for generic chat sessions, persisting user and assistant messages across server restarts.

##### 4. Data Validation, Configuration & Schema Modeling Layer
- **`pydantic` (`pydantic==2.13.4`) & `pydantic-core` (`pydantic-core==2.46.4`)**:
  - Rust-backed high-speed data validation and serialization.
  - Validates request schemas (`UserSignupRequest`, `InteractionRequest`, `ResearchRequest`, `SQLQueryRequest`) and serializes response schemas (`UserResponse`, `TokenResponse`, etc.).
  - Enforces structured JSON output parsing for the classifier agent via `PydanticOutputParser`.
- **`pydantic-settings` (`pydantic-settings==2.15.0`)**:
  - `BaseSettings`: Strongly typed configuration engine reading environment variables from `.env`, enforcing type constraints, and setting production defaults.

##### 5. Agent Middleware, LLM Runtimes & Observability Layer
- **`langgraph` (`langgraph==1.2.2`)**:
  - Stateful multi-agent orchestration framework supporting cyclical graphs, parallel branches with synchronization joins (`defer=True`), and Human-in-the-Loop interrupts (`interrupt()`).
- **`langfuse` (`langfuse==4.14.4`)**:
  - Production observability engine providing non-blocking OpenTelemetry traces, latency analysis, token consumption tracking, and session debugging via `langfuse.callback.CallbackHandler`.
- **`langchain-mcp-adapters` (`langchain-mcp-adapters==0.3.1`) & `mcp` (`mcp==1.29.0`)**:
  - Standardized Model Context Protocol (MCP) client running stdio subprocesses (`npx @openbnb/mcp-server-airbnb`, `@pinecone-database/mcp`).
- **`langchain-groq` (`langchain-groq==1.1.3`) & `groq` (`groq==0.37.1`)**:
  - Ultra-low latency LPU inference client running open models (`openai/gpt-oss-120b`).
- **`tiktoken` (`tiktoken==0.14.0`)**:
  - Fast BPE token counting used by `SummarizationMiddleware` to enforce token budget boundaries.
- **`duckduckgo-search` (`duckduckgo-search==8.1.1`)**:
  - Real-time zero-configuration live search engine integration for researcher dispatchers.

##### 6. Institutional Stock Market Analysis & Quantitative Engine Layer
- **`deepagents` (`deepagents==0.7.13`)**:
  - LangChain deep agent framework powering 13 specialized analyst lenses with autonomous reasoning, tool execution, and middleware integration.
- **`duckdb` (`duckdb==1.5.0`)**:
  - High-performance embedded columnar analytical database providing in-memory SQL querying, aggregate sector statistics, and sub-millisecond scalar proof verification for the Numeric Tracer.
- **`yfinance` (`yfinance==1.7.0`)**:
  - Official PyPI package by Ran Aroussi implementing real-time quotes, multi-period historical prices, valuation ratios, consensus price targets, peer comparisons, and live corporate news.
- **`gnews` (`gnews==0.4.5`)**:
  - Real-time Indian financial media and stock market news retrieval engine providing sentiment context and source quotes for qualitative audit.
- **`matplotlib` (`matplotlib==3.10.8`)**:
  - High-resolution publication chart generation in headless mode (`Agg` backend) generating visual exhibits reviewed and scored by the Chart Critic and Curator.

---

### 2. Workflow Graphs

#### A. Policy Decision-Tree Graph (Stateful Human-in-the-Loop)

<p align="center">
  <img src="./assets/policy_graph.png" alt="Policy Decision-Tree StateGraph" width="550"/>
</p>

```mermaid
flowchart TD
    Start([User Request]) --> UserInitPath[1. user_initpath\nExtract User Decision & Path]
    UserInitPath --> ClassifyNode[2. classify_node\nStructured Pydantic Classifier with Retries]
    
    ClassifyNode -- "exit" --> EndNode([END])
    ClassifyNode -- "generic" --> FeedbackLoop[6. process_feedback\nHuman-in-the-Loop Interrupt]
    ClassifyNode -- "policy / useDeviceData=True" --> DeviceSummary[3. device_summary\nExtract & Summarize System Specs]
    ClassifyNode -- "policy / useDeviceData=False" --> KnowledgeBase[4. knowledge_base\nHybrid BM25 + Dense Retrieval]
    
    DeviceSummary --> KnowledgeBase
    KnowledgeBase --> ReasonLLM[5. reason_llm\nDomain Policy Reasoning & SSE Tag]
    ReasonLLM --> FeedbackLoop
    FeedbackLoop --> ClassifyNode
```

#### B. Parallel Multi-Critic Research Graph (`defer = True` Join)

<p align="center">
  <img src="./assets/research_graph.png" alt="Parallel Multi-Critic Research Graph" width="600"/>
</p>

```mermaid
graph TD;
	__start__(["__start__"]):::first
	planner["planner"]
	approver["approver<br/><small><em>autonomous review</em></small>"]
	researcher_dispatcher["researcher_dispatcher"]
	researcher["researcher<br/><small><em>DuckDuckGo live search</em></small>"]
	synthesizer["synthesizer"]
	fact_critic["fact_critic<br/><small><em>Branch A: Fact Audit</em></small>"]
	style_critic_1["style_critic_1<br/><small><em>Branch B1: Tone & Clarity</em></small>"]
	style_critic_2["style_critic_2<br/><small><em>Branch B2: Executive Polish</em></small>"]
	publisher["publisher<hr/><small><em>defer = True</em></small>"]
	__end__(["__end__"]):::last
	
	__start__ --> planner;
	planner --> approver;
	approver -. "revise" .-> planner;
	approver -. "dispatch" .-> researcher_dispatcher;
	researcher_dispatcher --> researcher;
	researcher --> synthesizer;
	
	%% Parallel Fan-Out
	synthesizer --> fact_critic;
	synthesizer --> style_critic_1;
	style_critic_1 --> style_critic_2;
	
	%% Fan-In with defer=True
	fact_critic --> publisher;
	style_critic_2 --> publisher;
	publisher --> __end__;
	
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

#### C. Model Context Protocol (MCP) Multi-Agent Intelligence Graphs

##### Mode 1: ⚡ Multi-Hop Harry Potter Lore QA Graph (`@pinecone-database/mcp`)

<p align="center">
  <img src="./assets/mcp_graph_hp.png" alt="Multi-Hop Harry Potter Lore QA Graph" width="450"/>
</p>

```mermaid
flowchart TD
    Start([User Harry Potter Complex Question]) --> HPSearchAgent[1. hpSearchAgent\nMulti-Hop ReAct Agent\nPinecone MCP Index: hpvdb-openai\nTools: search-records, list-indexes,\ndescribe-index-stats, rerank-documents,\ncascading-search, search-docs]
    HPSearchAgent -->|Multi-Hop Trace & Reranked Passages| HPLoreScholar[2. hpLoreScholar\nMaster Lore Scholar Synthesizer\nChronological Causal Chain Analysis]
    HPLoreScholar --> EndNode([END])
    
    classDef default fill:#f2f0ff,line-height:1.2
```

##### Mode 2: 🏨 Airbnb Travel & Lodging Graph (`@openbnb/mcp-server-airbnb` + WeatherAPI)

<p align="center">
  <img src="./assets/mcp_graph_airbnb.png" alt="Airbnb Travel & Lodging Graph" width="500"/>
</p>

```mermaid
flowchart TD
    Start([User Travel Query]) --> AirbnbAgent[1. airbnbAgent\nReAct Agent with Airbnb MCP Tools]
    Start --> WeatherAgent[2. weatherAgent\nReAct Agent with WeatherAPI / Open-Meteo]
    
    AirbnbAgent --> TourAgent[3. tourAgent\nTour Guide Synthesizer & Stay-Weather Match]
    WeatherAgent --> TourAgent
    TourAgent --> EndNode([END])
    
    classDef default fill:#f2f0ff,line-height:1.2
```

#### D. Text-to-SQL Analyst Architecture Graph (`SQLDatabaseToolkit`)
```mermaid
flowchart TD
    Start([User Natural Language Query]) --> SQLAgent[1. create_sql_agent\nSQLDatabaseToolkit Orchestrator]
    SQLAgent --> ListTables[2. sql_db_list_tables\nSchema Introspection & Table Discovery]
    ListTables --> QueryChecker[3. sql_db_query_checker\nSyntax Validation & Dialect Correction]
    QueryChecker --> ExecuteSQL[4. sql_db_query\nSafe Read-Only PostgreSQL Execution]
    ExecuteSQL --> Synthesizer[5. Tabular Data & Explanation Synthesizer]
    Synthesizer --> EndNode([Synthesized Explanation & Interactive Data Table])
    
    classDef default fill:#f2f0ff,line-height:1.2
```

#### E. General Assistant Memory Graph (`PostgresChatMessageHistory`)
```mermaid
flowchart TD
    Start([User Message + Session ID]) --> FetchHistory[1. PostgresChatMessageHistory\nThread Checkpoint & Session Memory Retrieval]
    FetchHistory --> ContextAssembler[2. Context & History Assembler\nTrim & Token Budget Window]
    ContextAssembler --> ChatLLM[3. ChatGroq Inference\nStateful Conversational Generation]
    ChatLLM --> AppendHistory[4. Append Message & Update Postgres Checkpoint]
    AppendHistory --> EndNode([Streaming Response & Memory Persisted])
    
    classDef default fill:#f2f0ff,line-height:1.2
```

#### F. Institutional NSE Stock Analysis Swarm Architecture (`deepagents` + DuckDB + Pinecone MCP + Yahoo Finance + GNews)

<p align="center">
  <img src="./assets/stock_analysis_graph.png" alt="Institutional Stock Analysis Swarm StateGraph" width="750"/>
</p>

```mermaid
graph TD;
	__start__(["__start__"]):::first
	deterministic_ingest["1. deterministic_ingest<br/><small><em>NIFTY 500 CSV -> DuckDB & Pinecone MCP</em></small>"]
	richness_assessor["2. richness_assessor<br/><small><em>Data Completeness & Lens Gating</em></small>"]
	planner["3. planner<br/><small><em>Master Deep Agent Strategy & Subgoals</em></small>"]
	analyst_fanout["4. analyst_fanout<br/><small><em>13 Deep Agent Lenses + Middlewares</em></small>"]
	reflection["5. reflection<br/><small><em>Coverage & Gap Evaluation</em></small>"]
	followup_analysis["6. followup_analysis<br/><small><em>Targeted Gap Funding</em></small>"]
	gather["7. gather<br/><small><em>SQLite Blackboard Synchronization</em></small>"]
	verify["8. verify<br/><small><em>4-Tier Numeric, Quote, Digit & Skeptic Audit</em></small>"]
	judge["9. judge<br/><small><em>Deduplication, Ranking & Headlines</em></small>"]
	narrative_enrich["10. narrative_enrich<br/><small><em>Pinecone MCP Vector Context - No LLM</em></small>"]
	chart_agent["11a. chart_agent<br/><small><em>Matplotlib Realized Plots + Chart Critic</em></small>"]
	section_writers["11b. section_writers<br/><small><em>7 Spine Section Writers</em></small>"]
	exec_summary["11c. exec_summary<br/><small><em>CIO Actionable Briefing</em></small>"]
	assembler["12. assembler<hr/><small><em>defer = True</em></small>"]
	chart_curator["13. chart_curator<br/><small><em>Top Exhibits & figures.json</em></small>"]
	__end__(["__end__"]):::last

	__start__ --> deterministic_ingest;
	deterministic_ingest --> richness_assessor;
	richness_assessor --> planner;
	planner --> analyst_fanout;
	analyst_fanout --> reflection;
	reflection -. "followup" .-> followup_analysis;
	reflection -.-> gather;
	followup_analysis --> gather;
	gather -.-> verify;
	gather -.-> judge;
	verify --> judge;
	judge --> narrative_enrich;
	
	%% Parallel Synthesis Join (defer = True)
	narrative_enrich --> chart_agent;
	narrative_enrich --> section_writers;
	narrative_enrich --> exec_summary;
	
	chart_agent --> assembler;
	section_writers --> assembler;
	exec_summary --> assembler;
	
	assembler --> chart_curator;
	chart_curator --> __end__;

	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

##### 15-Node Quantitative Pipeline Architecture:
1. **`deterministic_ingest`**: Fetches official NIFTY 500 CSV from NSE (`niftyindices.com`), ingests 500 equities into an embedded **DuckDB Fact Store**, retrieves Indian stock market headlines via **GNews**, generates semantic vector embeddings into **Pinecone MCP**, and enforces an **Empty Guard** fail-fast.
2. **`richness_assessor`**: Programmatically computes field completeness, sector distribution, and record counts to dynamically gate the 13 analyst lenses.
3. **`planner`**: Evaluates data profile and initializes **SQLite Blackboard Memory** (`data/blackboard_{run_id}.db`) with subgoals, lens-specific briefs, priority ordering, and analytical traps.
4. **`analyst_fanout` (13 Lenses with Deep Agents + Isolated Sandboxes)**: Concurrently runs deep agents (`create_deep_agent` from LangChain) equipped with:
   - **4 Custom Agent Middlewares**: `StockThrottleMiddleware`, `StockTelemetryMiddleware`, `StockSelfCritiqueMiddleware`, `StockContextEditingMiddleware`.
   - **Isolated Sandbox Backend (`backend=get_sandbox_backend()`)**: Enforces the **Sandbox-as-Tool** pattern where untrusted Python math & algorithmic scripts execute within a sanitized environment (stripped of host credentials/API keys, capped at 512MB RAM and 1 CPU).
   - **Quantitative Modeling Tools**: 5,000-path Monte Carlo Geometric Brownian Motion simulations, Value at Risk (VaR 95% & 99%), Expected Shortfall (CVaR), and Markowitz Mean-Variance Portfolio Optimization.
   - **Tools Suite**: DuckDB analytical SQL execution, GNews intelligence, Pinecone MCP vector search, and 7 Yahoo Finance (`yfinance`) tools (`fetch_stock_quote_yf`, `fetch_stock_historical_yf`, `fetch_stock_fundamentals_yf`, `fetch_analyst_targets_yf`, `fetch_stock_news_yf`, `download_multi_stock_comparison_yf`, `search_ticker_yf`).
5. **`reflection`**: Evaluates subgoal coverage across lenses to detect gaps or unaddressed risk factors.
6. **`followup_analysis` / `gather`**: Dispatches targeted follow-up queries if the reflection gap is funded, then gathers all candidate findings into SQLite Blackboard Memory.
7. **`verify` (4-Tier Verification Suite)**:
   - **Numeric Tracer**: Re-executes claimed SQL against DuckDB and verifies a single scalar match within tolerance.
   - **Quote Audit**: Verifies exact verbatim substring matches against company announcements/news.
   - **Digit Audit**: Ensures every prose number is traced back to verified data or exempt sets.
   - **Skeptic Quorum**: Evaluates candidate findings against named analytical flaws.
8. **`judge`**: Deduplicates findings, ranks by confidence, and writes authoritative headlines using Finding IDs only.
9. **`narrative_enrich`**: Enriches verified claims using Pinecone MCP vector search without consuming LLM tokens.
10. **Parallel Synthesis Join (`defer=True`)**:
    - **`chart_agent` & `chart_critic`**: Generates Matplotlib visualizations and critiques data sufficiency (drops zero-row/zero-variance figures).
    - **`section_writers`**: 7 specialized section writers (*Valuation multiples, Operational efficiency, Momentum, Structural shifts, Policy/governance, Behavioral sentiment, Systemic risks*).
    - **`exec_summary`**: CIO-level executive briefing.
11. **`assembler`**: Resolves citation tokens and compiles a publication-grade HTML research dossier featuring embedded Quantitative Sandbox modeling exhibits.
12. **`chart_curator`**: Scores and curates top exhibits into `figures.json` and outputs final assets.

---

#### G. Master Deep Agent Query Planning & Multi-Store Ingestion Architecture

The stock swarm features an autonomous **Master Deep Agent Planning & Strategic Ingestion Subsystem** (`planner_node` & `StockQueryReasoner`). Rather than executing rigid hard-coded workflows, natural language user prompts (e.g. *"research on HDFC Bank in depth"* or *"compare HDFC Bank and Reliance performance for next 6 months"*) are dynamically parsed, decomposed, and routed across five segregated data tiers:

```mermaid
flowchart TD
    UserQuery(["💬 User Natural Language Query\n'compare HDFC Bank and Reliance performance for next 6 months'\n'research on HDFC Bank in depth'"])
    
    subgraph DeepPlanner ["🧠 Master Deep Agent Planning Subsystem (app/graphs/stock_analysis/nodes.py)"]
        Reasoner["StockQueryReasoner (app/tools/stock_query_reasoner.py)\n• Entity & Alias Disambiguation (HDFC Bank -> HDFCBANK, Reliance -> RELIANCE)\n• Analysis Mode Selection: single_stock | comparison | sector\n• Horizon Mapping: 6 Months -> 126 Trading Days, 1 Year -> 252 Trading Days"]
        ThesisGen["Master Strategic Thesis & Execution Plan Generator\n• Formulates Phase 1-5 Milestone Roadmap\n• Establishes Prioritized Subgoals (SG_VAL, SG_MOM, SG_RISK, SG_QUANT)\n• Identifies & Gates Cognitive Valuation Traps"]
        BlackboardInit["SQLite Blackboard Run Memory (data/blackboard_{run_id}.db)\n• Ingestion of Target Tickers, Subgoals, and Lens Briefs"]
    end

    UserQuery --> Reasoner
    Reasoner --> ThesisGen
    ThesisGen --> BlackboardInit

    subgraph MultiStore ["📚 Coordinated Multi-Store Heterogeneous Data Tier"]
        CSVStore[("1. CSV Directory (data/nifty500.csv)\n• Official NSE NIFTY 500 constituents\n• ISIN, Sector, Industry mapping")]
        DuckDBStore[("2. DuckDB In-Memory Analytical Fact Store\n• Ultra-fast columnar SQL fact store\n• Multiples (P/E, P/B), ROCE, ROE, 1M/6M/1Y Momentum\n• Ground truth proof verification engine")]
        GNewsStore[("3. GNews Real-Time Media Intelligence\n• Live Indian financial press headlines\n• Sentiment tracking & corporate disclosures")]
        YFStore[("4. Yahoo Finance PyPI Suite (7 Deep Agent Tools)\n• Real-time spot quotes & bid/ask spreads\n• Multi-stock comparative price histories\n• Forward analyst targets & upside consensus")]
        QuantSandboxStore[("5. Deep Agents Quant Sandbox\n• Isolated Subprocess / Docker runtime (512MB RAM)\n• 5,000-Path Monte Carlo GBM forward price projection\n• Markowitz Mean-Variance Max Sharpe portfolio optimization")]
    end

    BlackboardInit --> CSVStore
    BlackboardInit --> DuckDBStore
    BlackboardInit --> GNewsStore
    BlackboardInit --> YFStore
    BlackboardInit --> QuantSandboxStore

    subgraph SwarmLenses ["⚡ Parallel Deep Analyst Swarm (analyst_fanout_node)"]
        L1["Effectiveness Lens (Valuation & Multiples)"]
        L2["Temporal Lens (Momentum & 126d Monte Carlo)"]
        L3["Harm Attribution (Leverage & Debt Audit)"]
        L4["Discovery Lens (Institutional Holdings & FII)"]
        L5["Systemic Risk Lens (Beta & Sector Exposure)"]
        L6["Portfolio Optimization (Markowitz Max Sharpe)"]
        LRest["Remaining 7 Specialized Analytical Lenses..."]
    end

    CSVStore --> SwarmLenses
    DuckDBStore --> SwarmLenses
    GNewsStore --> SwarmLenses
    YFStore --> SwarmLenses
    QuantSandboxStore --> SwarmLenses
    SwarmLenses <-->|Bidirectional candidate findings & SQL proofs| BlackboardInit
```

---

#### H. Institutional Surveillance Dossier & Visual Report Pipeline

The generated publication research report is styled as an **Institutional Equity Surveillance Dossier** modeled directly on high-stakes institutional forensics (matching the 51-page Swiss editorial template: *Hidden recall risk — Boston Scientific Pacemaker (LWP)*).

```mermaid
flowchart TD
    subgraph AssemblyPipeline ["📑 Institutional Dossier Compilation Pipeline (assembler_node & chart_curator_node)"]
        P1["📄 Page 1: Cover Page\n• Burgundy Confidentiality Pill Tag\n• Dossier Title & Subtitle\n• Verified Provenance Notice (DuckDB, GNews, YF)\n• Soft Rose Thesis Box (#fff1f2 / 4px #8b1528 border)\n• Summary Statistics & Accent Rule"]
        P2["📄 Page 2: Table of Contents\n• Clean 7-Part Numbered Analytical Index\n• Page-break rules for printing"]
        S1["1. Executive Summary\n• Prose synthesis (zero unicode citation artifacts)\n• Bullet findings with severity tags (Critical / High)"]
        S2["2. Master Deep Agent Strategic Plan\n• Strategic Thesis Callout\n• Phased Execution Roadmap & Prioritized Subgoals\n• Cognitive & Valuation Traps Gated"]
        S3["3. Head-to-Head Comparative Scorecard\n• Deep Burgundy Header (#8b1528) with White Text\n• MCap, P/E, P/B, ROE%, ROCE%, D/E, Beta, 6M Ret%"]
        S4["4. Verified Analytical Findings Cards\n• Severity Badges: CRITICAL / HIGH / MEDIUM\n• Soft Rose Problem Statement Box\n• 4 Subsections: Evidence, Driver, Risk, Recommendation"]
        S5["5. Deterministic Spine Sections\n• 7 Analytical Pillars (5.1 to 5.7)"]
        S6["6. Curated Exhibits & Figures\n• Deep Burgundy Bar Palette (#8b1528)\n• Top/Right Spines Removed, Horizontal-Only Gridlines\n• Figure X. [Title] Captions & Critic Approval Tags"]
        S7["7. Quantitative Sandbox Modeling\n• Isolated DeepAgent Sandbox Execution Profile\n• Formatted Monte Carlo & Markowitz Telemetry JSON"]
        Colophon["📜 Page 51: Colophon & Governance Notice\n• Strict Verification Notice & Legal Compliance Disclaimer"]
    end

    P1 --> P2 --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> Colophon
```

---

#### I. LangChain Deep Agents Sandboxes Architecture (`app/core/sandbox/`)

This platform adheres strictly to the official [LangChain Deep Agents Sandboxes specification](https://docs.langchain.com/oss/python/deepagents/sandboxes) to safely run untrusted quantitative financial algorithms, Monte Carlo paths, and algorithmic scripts.

```mermaid
flowchart LR
    subgraph Host ["1. Host Application Plane"]
        direction TB
        Agent["🤖 Deep Agents Swarm\n(LLM Orchestrator)"]
        Blackboard["📝 SQLite Run Blackboard\n(State & Findings Store)"]
        Agent <--> Blackboard
    end

    subgraph Security ["2. Security Isolation Barrier"]
        direction TB
        Sanitizer["🔒 Environment Stripper\n• Purges all API keys & DB secrets\n• Whitelists only safe env vars"]
        Watchdog["⏱️ Resource Watchdog\n• Strict 512MB RAM ceiling\n• 1.0 CPU allocation\n• 30s timeout enforcement"]
        Sanitizer --> Watchdog
    end

    subgraph SandboxPlane ["3. Isolated Execution Plane"]
        direction TB
        Provider["📦 Subprocess / Docker Sandbox\n(Ephemeral Directory, Network Disabled)"]
        Quant["📊 Financial Quant Engines\n• 5,000-Path Monte Carlo GBM\n• Markowitz Portfolio Optimizer\n• Custom NumPy / SciPy Scripts"]
        Provider --- Quant
    end

    subgraph Results ["4. Validated Output"]
        JSON["⚡ Safe JSON Telemetry\n• Simulated Terminal Prices\n• VaR 95% / 99% & CVaR\n• Optimal Sharpe Ratio Weights"]
    end

    Agent -->|Dispatches Quant Code| Sanitizer
    Watchdog --> Provider
    Quant -->|Structured Metrics| JSON
    JSON -->|Safe Return| Agent
```

##### 1. The "Sandbox-as-Tool" Pattern
Rather than running the entire agent loop inside an untrusted sandbox (which introduces severe risks of prompt injection dumping API keys and database credentials), we implement the **Sandbox-as-Tool** architecture:
* **Host / Application Plane**: The LLM orchestration, checkpointing, and graph routing run securely on the host/backend.
* **Sandbox Execution Plane**: Dispatched code and mathematical simulations run inside an isolated, resource-constrained environment implementing `SandboxBackendProtocol`.
* **Zero Credential Leakage**: Sensitive environment variables (`OPENAI_API_KEY`, `PINECONE_API_KEY`, `DATABASE_URL`, `JWT_SECRET_KEY`) are stripped before subprocess or container execution.

| Dimension | Host / Direct Execution | Agent-in-Sandbox | **Sandbox-as-Tool (Our Architecture)** |
|:---|:---|:---|:---|
| **API Keys & Secrets** | Vulnerable to shell `env` inspection | Exposed to prompt injection in sandbox | 🔒 **100% Isolated outside sandbox** |
| **Database & File Safety** | Direct access to Postgres/DuckDB | Full access to sandbox filesystem | 🛡️ **Guarded ephemeral filesystem & boundary checks** |
| **Resource Constraints** | Can hang host / exhaust memory | Bound to VM/container | ⚡ **Strict 512MB RAM ceiling, 1.0 CPU, 30s timeout** |
| **Quant Computation** | Insecure | High orchestration overhead | 🚀 **Fast, dynamic NumPy/SciPy execution** |

##### 2. Protocol Compliance & Dual-Plane File Access
Adheres 1:1 with LangChain Deep Agents `SandboxBackendProtocol`:
* **External File Operations**:
  - `upload_files(files)`: Stages datasets and historical prices from host into sandbox.
  - `download_files(paths)`: Extracts generated chart figures and simulation artifacts.
* **Internal Agent Tool Operations**:
  - Automatically provisions agents with native filesystem tools: `read_file`, `write_file`, `edit_file`, `ls`, `grep`, `glob`, and `delete`.

##### 3. Pluggable Sandbox Providers (`app/core/sandbox/`)
* **`IsolatedSubprocessSandbox`**: Zero-dependency, secure local execution engine with environment sanitization, ephemeral working directories, and POSIX timeout enforcement (exit code `124`).
* **`DockerSandbox`**: Containerized execution with hardware ceilings (`--memory=512m`, `--cpus=1.0`, `--network=none`), non-root execution, and auto-fallback to subprocess.
* **`SandboxFactory`**: Dynamic factory auto-detecting runtime capabilities and instantiating the optimal provider (`provider="auto"`).

##### 4. Quantitative Financial Modeling Suite (`app/tools/quant_models.py`)
Executed strictly inside the isolated sandbox:
1. **5,000-Path Monte Carlo Geometric Brownian Motion (GBM)**:
   - Projects 252 trading-day price paths using \(S_t = S_0 \exp\left((\mu - \frac{1}{2}\sigma^2)t + \sigma \sqrt{t} Z\right)\).
   - Computes 95% and 99% Value at Risk (VaR), Conditional VaR / Expected Shortfall (CVaR), loss probability, and percentiles (P5, P50, P95).
2. **Markowitz Mean-Variance Portfolio Optimization**:
   - Generates 10,000 random portfolio weight allocations across specified NIFTY equities using NumPy.
   - Calculates the **Maximum Sharpe Ratio** optimal portfolio and the **Minimum Volatility** portfolio.
3. **Custom Python Sandbox Execution**:
   - Allows users and deep agents to execute arbitrary Python code safely with timeout guards and stdout/stderr capture.

##### 5. Frontend Quant Sandbox Console Modal
* **Main Navigation Launch Button (`#btn-open-sandbox`)**: Located prominently in the top header navbar.
* **Real-Time Telemetry Badge**: Polled from `GET /stock/sandbox/status` displaying isolated status, provider, and memory limits (`🟢 ISOLATED (512MB limit, 1.0 CPU)`).
* **One-Click Quick Simulators**:
  - **Monte Carlo Simulator**: Symbol input (`RELIANCE.NS`), volatility slider (`22%`), and execute button (`#btn-quick-run-mc`).
  - **Markowitz Portfolio Optimizer**: Multi-symbol input (`RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS,ITC.NS`) and execute button (`#btn-quick-run-opt`).
* **Interactive Code Editor & Terminal**:
  - Code textarea with presets (GBM, Markowitz, Custom math).
  - Monospace dark terminal console (`#modal-sandbox-output-wrap`) displaying execution duration, exit code, and stdout/stderr.
* **Chat Stream Integration (`frontend/js/chat.js`)**:
  - Injects violet **`⚡ DeepAgent Quant Sandbox`** cards into chat messages showcasing simulated terminal prices, 95% VaR, and optimal Sharpe weights alongside verified findings and chart exhibits.

### 1. LangGraph StateGraph & Class-Based Nodes
- **`AgentState` TypedDict**: Manages `tree`, `user_choices`, `current_path_str`, `user_decisions_str`, `context_docs_str`, `classification`, `feedback`, `useDeviceData`, `userProvidedDeiveceData`, and `chat_history` with the `add_messages` reducer.
- **`MCPState` / `MCPTravelState` TypedDict**: Manages `topic`, `knowledge` (`add_messages` reducer), `hp_report` (HP QA), `airbnb_report`, `weather_report`, and `summary` (Airbnb mode).
- **Modular OOP Nodes**: Each node inherits from standardized execution boundaries, error handling, and tracing.

### 2. PostgreSQL Checkpointing (`AsyncPostgresSaver`)
- Persistent thread checkpoints stored asynchronously in PostgreSQL with `AsyncPostgresSaver(pool)`.
- Seamless development fallback to `MemorySaver` when PostgreSQL is offline.
- Dedicated `/delete_thread` endpoint for checkpoint eviction and GDPR compliance.

### 3. Server-Sent Events (SSE) & WebSocket Streaming
- **SSE Endpoint (`/interact`)**: Streams the generated `thread_id` first, then yields real-time token chunks using `graph.astream_events(..., version="v2")` filtered on `on_chat_model_stream` and `tags=["PolicyExpert"]`.
- **SSE MCP Endpoint (`/mcp/stream`)**: Yields dynamic agent execution hints (`hpSearchAgent`, `hpLoreScholar`, `airbnbAgent`, `weatherAgent`, `tourAgent`) and streams raw token chunks filtered by active sub-agent tag (`HPLoreScholar` or `TourGuideExpert`).
- **WebSocket Endpoint (`/ws/interact`)**: Full-duplex bidirectional streaming supporting initial conversations and instant interrupt resume commands.

### 4. Human-in-the-Loop Interrupts & Resumes
- The `process_feedback` node uses LangGraph's `interrupt()` primitive to safely suspend execution without blocking threads.
- Graph resumes execution upon receiving user feedback via `Command(resume=..., update=...)`.

### 5. Model Context Protocol (MCP) Integration & Lifespan Architecture (`app/core/mcp.py`)

#### A. Multi-Server MCP Client Architecture
```
                               ┌─────────────────────────────────────────────────────────┐
                               │           FASTAPI APPLICATION LIFESPAN STARTUP          │
                               └────────────────────────────┬────────────────────────────┘
                                                            │
                                                            ▼
                               ┌─────────────────────────────────────────────────────────┐
                               │            MCPClientManager.initialize()                │
                               │  - Spawns stdio subprocesses via MultiServerMCPClient:  │
                               │    1) npx -y @openbnb/mcp-server-airbnb                │
                               │    2) npx -y @pinecone-database/mcp (hpvdb-openai)      │
                               │  - Discovers & caches tools in app.state.mcp_manager    │
                               └────────────────────────────┬────────────────────────────┘
                                                            │
                            ┌───────────────────────────────┴───────────────────────────────┐
                            │ Mode: "harry_potter"                                          │ Mode: "airbnb"
                            ▼                                                               ▼
             ┌─────────────────────────────┐                               ┌────────────────────────────────┐
             │    hpSearchAgent (Node)     │                               │      airbnbAgent + weather     │
             │  - Queries hpvdb-openai     │                               │  - Airbnb stdio MCP listings   │
             │  - Retrieves canonical lore │                               │  - Live 3-day weather forecast │
             └──────────────┬──────────────┘                               └───────────────┬────────────────┘
                            │                                                              │
                            ▼                                                              ▼
             ┌─────────────────────────────┐                               ┌────────────────────────────────┐
             │   hpLoreScholar Synthesis   │                               │    tourAgent Synthesizer       │
             │  - Synthesizes answer       │                               │  - Pairs lodgings with weather │
             │  - Tags: ["HPLoreScholar"]  │                               │  - Tags: ["TourGuideExpert"]   │
             └──────────────┬──────────────┘                               └───────────────┬────────────────┘
                            │                                                              │
                            └───────────────────────────────┬───────────────────────────────┘
                                                            │
                                                            ▼
                               ┌─────────────────────────────────────────────────────────┐
                               │           FASTAPI APPLICATION LIFESPAN SHUTDOWN         │
                               │  - MCPClientManager.shutdown()                          │
                               │  - Terminates all active stdio subprocesses gracefully   │
                               └─────────────────────────────────────────────────────────┘
```

#### B. Transport Evaluation: `npx @openbnb/mcp-server-airbnb` (stdio) vs Docker Hub Container
When selecting the integration method between the **`mcp.so` NPM/npx stdio subprocess** and the **Docker Hub container image (`openbnb-airbnb`)**:

| Architectural Dimension | **`npx @openbnb/mcp-server-airbnb` (stdio)** *(Chosen)* | **Docker Image `openbnb-airbnb`** *(Container)* |
| :--- | :--- | :--- |
| **Transport Protocol** | **Native `stdio` (Standard I/O pipe)** | **Container Subprocess / Network SSE** |
| **Latency & Throughput** | ⚡ **Microsecond latency** (direct pipe in OS process memory) | 🐢 Higher (Docker daemon invocation & container boot) |
| **FastAPI Container Security** | 🔒 **Secure** — Node.js runs as standard unprivileged app user | ⚠️ Requires mounting `/var/run/docker.sock` (root-level breakout risk) |
| **Port & Network Management** | 🟢 **Zero ports needed** (no port conflicts or bridge networks) | 🟡 Requires managing port bindings or virtual networks |
| **Resource Footprint** | 🟢 Minimal (~30–50MB RAM for lightweight Node.js worker) | 🟡 Container runtime daemon & image storage overhead |
| **LangGraph MCP Adapters** | 🟢 100% native alignment with `langchain-mcp-adapters` | 🟡 Requires SSE transport bridge or docker-exec wrappers |

**Why `stdio` (npx) was selected:**
1. **Zero Privileged Sockets**: Spawning Docker containers from within a containerized FastAPI application requires mounting the host Docker socket (`/var/run/docker.sock`), which presents high security risks in production. Running `npx` in-process avoids this entirely.
2. **Deterministic Lifecycle**: Process lifecycle is synchronously bound to FastAPI's `lifespan` context manager via `asyncio`.
3. **Resilient Fallback**: If the external stdio MCP server is offline or fails network resolution, `MCPClientManager` automatically falls back to internal search adapters with zero service interruption.

#### C. Autonomous Dynamic Multi-Hop Reasoning Architecture (`hpSearchAgent` & `hpLoreScholar`)

The Harry Potter QA engine implements an **Autonomous ReAct Reasoning Architecture** that dynamically navigates the 7-book corpus (`hpvdb-openai`) using Pinecone MCP tools:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          USER LORE QUESTION                                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 🧠 AUTONOMOUS REACT REASONING & DYNAMIC TOOL SELECTION (`hpSearchAgent`)    │
│  - Non-deterministic, LLM-driven tool selection based on the specific query │
│  - Flexible multi-hop iterations (calls `search-records` multiple times)    │
│  - Intelligently skips irrelevant tools (e.g. schema introspection)         │
│  - Applies cross-encoder `rerank-documents` dynamically when needed         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Canonical Excerpts & Evidence)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ ⚡ MASTER LORE SCHOLAR SYNTHESIS (`hpLoreScholar`)                          │
│  - Synthesizes the full chronological causal chain with book citations      │
└─────────────────────────────────────────────────────────────────────────────┘
```

##### Autonomous Tool Calling Principles:
1. **Zero Pre-Determined Checklists**: The agent does not execute rigid sequential steps. Simple queries may trigger 1 or 2 focused searches, while complex cross-book investigations iteratively trace clues across multiple targeted queries.
2. **Multiple Invocations Per Tool**: Search tools like `search-records` can be invoked multiple times in sequence with refined keywords, entity names, or filter criteria uncovered from prior retrieval hops.
3. **Selective Skipping**: Diagnostic tools (`list-indexes`, `describe-index`, `describe-index-stats`, `search-docs`) are called only when schema or syntax inspection is genuinely needed.
4. **Smart Stopping Condition**: The agent terminates tool execution and passes findings to `hpLoreScholar` as soon as sufficient canonical evidence is gathered.

##### Full Pinecone MCP Tool Suite Matrix:
| Pinecone MCP Tool | Category | Role in Multi-Hop Reasoning |
| :--- | :--- | :--- |
| **`search-records`** | Retrieval | Semantic vector search on `hpvdb-openai` with integrated inference, metadata filters, and top-K sampling. |
| **`rerank-documents`** | Reranking | Cross-encoder model (`cohere-rerank-3.5`, `pinecone-rerank-v0`, `bge-reranker-v2-m3`) re-scoring multi-hop candidates. |
| **`cascading-search`** | Federation | Multi-index search across different vector namespaces with automatic deduplication. |
| **`list-indexes`** | Introspection | Discovers and validates active Pinecone indexes in the project. |
| **`describe-index`** | Schema | Inspects index embedding dimensions (1536), readiness status, and fieldMap. |
| **`describe-index-stats`** | Analytics | Returns exact record count and namespace vector distribution in `hpvdb-openai`. |
| **`search-docs`** | Documentation | Live documentation search for Pinecone query and filter syntax (`$eq`, `$in`, `$and`). |
| **`create-index-for-model`** | Management | Creates integrated inference indexes dynamically. |
| **`upsert-records`** | Ingestion | Inserts or updates lore records with integrated inference. |
| **`pinecone_multihop_search`** | Native Fallback | Direct multi-hop sequential vector batch retriever across consecutive hops. |
| **`pinecone_index_stats`** | Native Inspection | Real-time index health and namespace vector statistics. |

### 6. SQL Agent with SQLDatabaseToolkit
- Natural language to SQL generation and execution using `create_sql_agent` with toolkits, returning synthesized explanations, the exact SQL query, and raw tabular results.

### 7. Structured Output Classifier with Self-Correction Retries
- Enforces strict JSON schemas using `PydanticOutputParser(pydantic_object=Classify)` with an iterative retry loop on `ValidationError` that passes formatting correction feedback to the LLM.

### 8. Observability with Langfuse
- Non-blocking tracing and telemetry integration using `langfuse.callback.CallbackHandler` attached to LangGraph `RunnableConfig`.

### 9. Agent Middleware Architecture (`app/middleware/`)
Modular, extensible middleware system implementing lifecycle interception (`run_before_agent`, `run_before_model`, `run_after_model`, `run_before_tools`, `run_after_tools`, `run_after_agent`):
- **`PIIMiddleware`**: Detects and sanitizes emails, phone numbers, SSNs, credit cards, medical record IDs (MRN/PHI), and IPv4 addresses via `mask`, `redact`, or `hash` strategies.
- **`RateLimitMiddleware`**: Sliding-window rate limiter per user/session, consecutive error count tracking, circuit breaker protection, and reasoning confidence auditing.
- **`HumanInTheLoopMiddleware`**: Intercepts sensitive tool calls (e.g. `execute_sql_mutation`, `submit_compliance_audit`) and pauses execution until human authorization is granted.
- **`SummarizationMiddleware`**: Token- and message-count-aware chat history compressor (`trigger=[("tokens", 1200), ("messages", 8)]`), summarizing older dialogue while preserving recent context.

### 10. Centralized Streaming Engine (`app/core/streaming.py`)
- **DRY SSE Event Generation**: Unified `stream_graph_events` async generator eliminates repetitive SSE serialization across endpoints (`/interact`, `/research/stream`, `/mcp/stream`).
- **Granular Token & Hint Filtering**: Emits metadata events (`tool_start`, `tool_end`, `stage`, `hint`) while routing filtered `on_chat_model_stream` tokens with active agent tags (`PolicyExpert`, `HPLoreScholar`, `TourGuideExpert`, `Publisher`).
- **Heartbeat & Error Encapsulation**: Guarantees keep-alive heartbeats during long reasoning cycles and gracefully emits structured `{"error": "..."}` payloads if an upstream model or tool errors.

### 11. Graph Visualizer & Artifact Engine (`app/graphs/visualizer.py`)
- **Dynamic Mermaid & PNG Rendering**: Centralized compilation pipeline for generating Mermaid `.mmd` files and compiled `.png` image artifacts directly into `app/static/`.
- **Domain-Specific Graph Export**: Generates and serves diagrams for all 3 stateful graphs:
  - Policy Decision Graph (`graph.mmd`, `graph.png`)
  - Autonomous Parallel Research Graph (`research_graph.mmd`, `research_graph.png`)
  - Dual MCP Intelligence Graph (`mcp_graph_hp.mmd`, `mcp_graph_airbnb.mmd`, `mcp_graph.png`)

### 12. Modern Decoupled Frontend UX (`frontend/`)
- **Custom MCP Mode Dropdown**: Replaced the hybrid native `<select>` with a custom dropdown (`#mcp-dropdown-trigger` & `#mcp-dropdown-menu`). Completely resolves duplicate emoji rendering (`🏨 🏨` -> `🏨`), OS-level popup collisions, and establishes mutual exclusion with the Agent menu.
- **Context-Aware Dynamic Parameter Input**: The top navbar `[ Parameters ]` button is automatically displayed only for agents that require configurable parameters (`policy`) and hidden for all other agents. Pre-populates form state on click and dynamically binds values to live SSE execution payloads.
- **WebSocket Handshake Authentication**: Automatically appends `?token=${encodeURIComponent(token)}` to the connection URI, ensuring seamless compatibility with WebSocket JWT authorization.
- **Schema Normalization**: Fully supports the standardized `user_provided_device_data` attribute while preserving backward compatibility with legacy `userProvidedDeiveceData` payloads.

### 13. Institutional NSE Stock Analysis Swarm Mechanisms
- **Master Deep Agent Query Planning & Plain-English Entity Resolution**:
  - Accepts natural-language analytical prompts (e.g., *"research on HDFC Bank in depth"* or *"compare HDFC Bank and Reliance performance for next 6 months"*).
  - The **Master Deep Agent Planner** immediately parses the objective, resolves target company aliases (e.g., *HDFC Bank* ➔ `HDFCBANK`, *Reliance* ➔ `RELIANCE`, *Tata Motors* ➔ `TATAMOTORS`), determines the analysis mode (`single_stock`, `comparison`, or `sector`), and calculates the explicit trading-day horizon (e.g., *6 months* ➔ 126 trading days, *1 year* ➔ 252 trading days).
  - Orchestrates downstream analytical lenses to coordinate across:
    - **CSV**: Official NIFTY 500 constituent directory (`data/nifty500.csv`) for ISIN, series, and entity mapping.
    - **DuckDB**: Fast in-memory analytical SQL fact store for multiples (P/E, P/B), returns (1M, 6M, 1Y), ROE, ROCE, leverage (D/E), and beta.
    - **SQLite Blackboard**: Run-level memory (`data/blackboard_{run_id}.db`) storing subgoals, target metrics, and shared audit proofs.
    - **GNews Intelligence**: Real-time company-specific news extraction and sentiment tracking.
    - **Yahoo Finance (`yfinance`)**: 7 live deep agent tools extracting real-time quotes, multi-stock comparative histories, and consensus analyst target upside.
    - **Deep Agents Quant Sandbox**: Horizon-calibrated Monte Carlo forward projections and Markowitz Sharpe-maximizing portfolio allocations.
- **Embedded DuckDB Fact Store & NIFTY 500 Enrichment**: Blazing fast in-memory analytical SQL engine ingesting 500 NSE equities from official NSE records (`data/nifty500.csv`). Tables (`nifty500`, `sector_aggregates`, `changepoint_candidates`, `quality_value_stocks`) provide instant access to P/E, P/B, ROE, ROCE, 1M/6M/1Y momentum, and market cap metrics.
- **Pinecone MCP Vector Search & Narrative RAG**: Semantic vector retrieval across corporate disclosures and real-time news headlines using the official Pinecone MCP server, generating contextual narrative grounding without unnecessary LLM overhead.
- **Yahoo Finance (`yfinance`) PyPI Tool Suite inside Deep Agents**: 7 high-performance tools (`fetch_stock_quote_yf`, `fetch_stock_historical_yf`, `fetch_stock_fundamentals_yf`, `fetch_analyst_targets_yf`, `fetch_stock_news_yf`, `download_multi_stock_comparison_yf`, `search_ticker_yf`) conforming to Ran Aroussi's official `yfinance` specification with DuckDB Fact Store fallback for resilience against network rate limits.
- **LangChain `deepagents` & 4 Custom Middlewares**:
  - `StockThrottleMiddleware`: Rate-limiting and tool call pacing.
  - `StockTelemetryMiddleware`: Latency, model calls, and token budget tracking.
  - `StockSelfCritiqueMiddleware`: Enforces empirical grounding, filtering speculative claims and unverified superlatives.
  - `StockContextEditingMiddleware`: Compresses tool outputs to prevent context window exhaustion.
- **SQLite Blackboard Memory (`data/blackboard_{run_id}.db`)**: Shared run-level persistent memory allowing analyst lenses to post candidate findings, recall peer evidence, and update verification statuses.
- **4-Tier Quantitative Verification Suite**:
  - **Numeric Tracer**: Re-runs claimed SQL queries against DuckDB and verifies that exactly ONE scalar matches the claimed value within a 2% tolerance.
  - **Quote Audit**: Strict verbatim substring matching against source disclosures and GNews feed.
  - **Digit Audit**: Scans generated prose to ensure every numeric figure maps to primary or secondary verified data (`additional_scalars`) or structural exempt sets.
  - **Skeptic Quorum**: Evaluates candidate findings against named analytical flaws (*correlation vs causation, survivorship bias, small sample size*).
- **Chart Agent, Critic & Curator**: Deterministic Matplotlib renderer generating charts in `app/static/top_charts/`, evaluated by a **Chart Critic** (drops zero-row/zero-variance figures) and ranked by a **Chart Curator** into `figures.json`.
- **Deterministic Assembler & Publication HTML Report**: Resolves citation tokens and compiles a publication-grade, self-contained HTML research report at `/stock/report/{run_id}` featuring an embedded **Head-to-Head Fundamental & Valuation Scorecard** table and Quantitative Sandbox modeling exhibits.

### 14. LangChain Deep Agents Sandboxes & Isolated Quant Modeling
- **Sandbox-as-Tool Architecture**: Implements the official LangChain Deep Agents Sandboxes protocol (`SandboxBackendProtocol`) separating the host LLM orchestration plane from untrusted code execution.
- **Strict Security Sanitization**: Strips host environment variables (`OPENAI_API_KEY`, `PINECONE_API_KEY`, `DATABASE_URL`, `JWT_SECRET_KEY`) before sandbox execution, preventing credential leakage via malicious code or prompt injection.
- **Resource Ceilings & Isolation**: Enforces a strict 512MB RAM ceiling, 1.0 CPU limit, and a 30-second POSIX timeout (exit code `124`) preventing denial-of-service or memory exhaustion.
- **Dual-Plane File Operations**:
  - *Outside Plane*: `upload_files` and `download_files` for dataset and figure synchronization.
  - *Inside Plane*: Native filesystem tools (`read_file`, `write_file`, `edit_file`, `ls`, `grep`, `glob`, `delete`).
- **Institutional Quant Models (`app/tools/quant_models.py`)**:
  - *Monte Carlo Price Simulator*: 5,000-path Geometric Brownian Motion (GBM) calculating 95% & 99% Value at Risk (VaR), Conditional VaR / Expected Shortfall (CVaR), loss probability, and percentile cones.
  - *Markowitz Portfolio Optimizer*: Generates 10,000 weight allocations across NIFTY equities using NumPy to identify the Maximum Sharpe Ratio optimal portfolio.
- **Interactive Frontend Quant Sandbox Console Modal**:
  - Dedicated **⚡ Quant Sandbox** launch button in the top navigation bar.
  - Real-time status telemetry badge (`🟢 ISOLATED (512MB limit, 1.0 CPU)`).
  - One-click Quick Simulators for Monte Carlo and Markowitz Portfolio Optimization.
  - Custom Python code editor with syntax-highlighted dark terminal output console.
  - Chat stream stock cards with violet **`⚡ DeepAgent Quant Sandbox`** metric badges.

---

## 📁 Project Directory Structure

```
langgraph-project/
├── .env.example                # Example environment variables template
├── .env                        # Active local environment variables (ignored by git)
├── .gitignore                  # Git ignore rules
├── Dockerfile                  # Production multi-stage Docker build (uv-powered)
├── docker-compose.yml          # FastAPI + PostgreSQL orchestration
├── pyproject.toml              # Build system & pytest configuration
├── requirements.txt            # Python dependencies
├── README.md                   # Comprehensive architecture documentation
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application, lifespan, CORS, and router mounts
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py             # OAuth2 Bearer dependencies & token validation
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py       # API v1 router aggregation
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── auth.py     # /auth/signup, /login, /me, /logout, /forgot-password, /reset-password
│   │           ├── health.py   # /health, /graph/mermaid
│   │           ├── research.py # /research/run, /research/stream, /research/mermaid
│   │           ├── chat.py     # /generic_chat, /delete_session (PostgresChatMessageHistory)
│   │           ├── sql.py      # /get_sql_query (SQL Agent)
│   │           ├── interact.py # /interact (SSE streaming), /delete_thread, /thread state
│   │           ├── websocket.py# /ws/interact (Bidirectional streaming WebSocket)
│   │           └── stock_analysis.py # /stock/analyze, /stock/report/{run_id}, /stock/health, /stock/mermaid
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Pydantic BaseSettings (DB, LLM, Token Budgets, Auth, Langfuse)
│   │   ├── database.py         # AsyncConnectionPool & Postgres checkpointing manager (agent_db)
│   │   ├── auth_database.py    # Auth DB connection pool, table DDL, and token blacklist (auth_db)
│   │   ├── blackboard.py       # SQLite Blackboard Run Memory (data/blackboard_{run_id}.db)
│   │   ├── security.py         # Argon2id password hashing & PyJWT token utilities
│   │   ├── llm.py              # ChatGroq LLM factory with per-node token limit support
│   │   ├── exceptions.py       # Custom application exceptions and error handlers
│   │   ├── observability.py    # Langfuse callback handlers and RunnableConfig builder
│   │   ├── streaming.py        # Centralized async SSE & token streaming event generator
│   │   └── sandbox/            # LangChain Deep Agents Sandboxes Architecture
│   │       ├── __init__.py
│   │       ├── base.py         # BaseSandbox dual-plane file & inner tool implementation
│   │       ├── factory.py      # Pluggable backend auto-detection factory
│   │       ├── subprocess_sandbox.py # Sanitized, resource-capped subprocess sandbox
│   │       └── docker_sandbox.py     # Containerized Docker sandbox (--memory=512m, 1.0 CPU)
│   ├── middleware/
│   │   ├── __init__.py         # Default global middleware pipeline exports
│   │   ├── base.py             # AgentMiddleware abstract base class & pipeline executor
│   │   ├── pii.py              # PIIMiddleware (mask, redact, hash sensitive data)
│   │   ├── rate_limit.py       # RateLimitMiddleware (sliding window & error budget circuit breaker)
│   │   ├── hitl.py             # HumanInTheLoopMiddleware (sensitive tool interceptor)
│   │   ├── summarizer.py       # SummarizationMiddleware (token/message trigger history compressor)
│   │   └── stock_middleware.py # StockThrottle, Telemetry, SelfCritique, ContextEditing
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py             # UserSignupRequest, UserLoginRequest, UserResponse, TokenResponse
│   │   ├── state.py            # LangGraph AgentState TypedDict & Classify Pydantic model
│   │   ├── research.py         # ResearchRequest, ResearchReport, ResearchStreamEvent
│   │   ├── chat.py             # ChatRequest, ChatResponse, DeleteSession
│   │   ├── sql.py              # SQLQueryRequest, SQLQueryResponse
│   │   ├── interact.py         # InteractionRequest, DeleteThreadRequest, GraphStateResponse
│   │   └── stock_analysis.py   # StockAnalysisRequest, StockAnalysisResponse, Finding, ChartSpec
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── react_agent.py      # ReAct agent with tools (DuckDuckGo/Tavily) & middleware
│   │   ├── sql_agent.py        # SQL agent with SQLDatabaseToolkit & query executor
│   │   └── classifier_agent.py # Structured JSON classifier with self-correcting retry loop
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── weather.py          # Weather forecast tool (WeatherAPI with Open-Meteo fallback)
│   │   ├── nifty_data.py       # Official NIFTY 500 CSV downloader & metric enricher
│   │   ├── stock_fact_store.py # In-memory DuckDB analytical fact store & SQL query tool
│   │   ├── gnews_tools.py      # GNews Indian stock market news & sentiment tool
│   │   ├── stock_pinecone_tools.py # Pinecone MCP vector search & narrative RAG
│   │   ├── quant_models.py     # 5,000-Path Monte Carlo GBM, VaR/CVaR & Markowitz Optimization
│   │   └── yahoo_finance_tools.py  # 7 yfinance tools (quotes, history, targets, peer comparison)
│   ├── graphs/
│   │   ├── __init__.py
│   │   ├── routing.py          # Conditional edge routing functions (decide_start_node)
│   │   ├── builder.py          # GraphBuilder & StateGraph compilation factory
│   │   ├── visualizer.py       # Centralized Mermaid rendering & PNG graph artifact generator
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # BaseGraphNode abstract class
│   │   │   ├── init_path.py    # user_initpath node
│   │   │   ├── classify.py     # classify_node
│   │   │   ├── device.py       # device_summary node
│   │   │   ├── knowledge.py    # knowledge_base node
│   │   │   ├── reason.py       # reason_llm node (tagged for SSE streaming)
│   │   │   └── feedback.py     # process_feedback node (LangGraph interrupt)
│   │   ├── research/
│   │   │   ├── __init__.py
│   │   │   ├── builder.py      # ResearchGraphBuilder with parallel branches & defer=True
│   │   │   └── nodes.py        # Planner, Approver, Dispatcher, Researcher, Synthesizer, Critics, Publisher
│   │   ├── mcp/
│   │   │   ├── __init__.py
│   │   │   ├── builder.py      # MCPTravelGraphBuilder with concurrent Airbnb/Weather fan-out
│   │   │   └── nodes.py        # Airbnb Agent (MCP tools), Weather Agent, and Tour Guide nodes
│   │   └── stock_analysis/     # Institutional NSE Stock Analysis Swarm (15 nodes)
│   │       ├── __init__.py
│   │       ├── builder.py      # StockAnalysisGraphBuilder with 15 nodes & parallel join
│   │       ├── nodes.py        # 15 Graph nodes with deepagents, reflection, judge, writers
│   │       ├── verify.py       # 4-Tier Verification Suite (Numeric, Quote, Digit, Skeptic)
│   │       └── charts.py       # Deterministic Matplotlib Chart Agent, Critic & Curator
│   └── retrievers/
│       ├── __init__.py
│       ├── hybrid_reranker.py  # Lightweight filtering & BM25 retrieval
│       └── ensemble.py         # Dynamic EnsembleRetriever builder
├── frontend/                   # Decoupled Standalone ChatGPT-Style SPA (Vanilla JS + ES Modules)
│   ├── index.html              # Cockpit with Quant Sandbox Console modal & Quick Simulators
│   ├── css/
│   │   ├── theme.css           # Design tokens, typography & dark/light palette
│   │   ├── components.css      # Custom buttons, modals, cards, tags & switch toggles
│   │   └── chat.css            # Monospace terminal console, stock report cards & grids
│   └── js/
│       ├── config.js           # API route mappings & localStorage persistence keys
│       ├── api.js              # Fetch wrapper, SSE reader & authenticated WebSocket client
│       ├── auth.js             # Argon2id signup, login, profile & JWT token management
│       ├── agents.js           # Agent metadata, capability flags (hasParams) & mode presets
│       ├── chat.js             # Stream renderer with violet DeepAgent Quant Sandbox badges
│       ├── decisionTree.js     # Policy navigator, state inspector & thread eviction
│       ├── research.js         # Parallel multi-critic runner & dynamic critic hints
│       ├── mcp.js              # Stdio MCP tool inspector & dual-mode travel/lore runner
│       ├── sqlAgent.js         # Natural language to SQL runner & interactive data table
│       ├── topology.js         # Mermaid flowchart drawer & node inspection
│       └── app.js              # Modal handlers, quick simulation runners & terminal formatter
├── scripts/
│   ├── init_postgres.sql       # Automatic auth_db and agent_db Docker bootstrap script
│   ├── run_stock_analysis.py   # Standalone CLI runner for institutional stock analysis swarm
│   ├── test_fe_stock_sandbox.py# Frontend-to-Backend Quant Sandbox E2E Suite (12/12 pass)
│   ├── test_sandbox_live.py    # Live Deep Agents Sandbox API integration suite (7/7 pass)
│   ├── test_stock_live.py      # Live Stock Swarm 12-test comprehensive suite (12/12 pass)
│   ├── test_all_endpoints.py   # Comprehensive live endpoint & edge-case test suite (45/45 pass)
│   ├── test_fe_live.py         # Live frontend simulation, CORS & asset test suite (11/11 pass)
│   ├── init_db.py              # CLI database table verification script
│   ├── test_client.py          # Python SSE client testing streaming & interrupt resume
│   └── test_ws_client.py       # Python WebSocket streaming client
└── tests/
    ├── __init__.py
    ├── test_api.py             # FastAPI endpoint integration tests
    ├── test_auth.py            # Signup, login, JWT verification, logout revocation, reset tests
    ├── test_middleware.py      # PII, RateLimit, HITL, Summarization unit & pipeline tests
    ├── test_classifier.py      # Structured classifier unit tests
    ├── test_graph_builder.py   # StateGraph builder and routing unit tests
    ├── test_hybrid_retriever.py# BM25 + filtering unit tests
    ├── test_research_graph.py  # Parallel research graph & defer=True join tests
    ├── test_mcp.py             # Model Context Protocol (MCP) and multi-agent travel tests
    ├── test_stock_analysis.py  # 10 unit & integration tests for stock analysis swarm (10/10 pass)
    └── test_sandbox.py         # 7 unit tests for Deep Agents Sandboxes & Quant Models (7/7 pass)
```

---

## 📡 API Endpoints Specification

### 1. Authentication & User Access (`auth_db`)
| Method | Path | Description | Key Request Params / Auth |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/signup` | Register a new user with Argon2id password hashing | `{"email": "...", "full_name": "...", "password": "..."}` |
| `POST` | `/auth/login` | OAuth2 Password login & JWT access token generation | `username`, `password` (Form data) |
| `GET` | `/auth/me` | Retrieve authenticated user profile | Bearer Token (`Authorization: Bearer <token>`) |
| `POST` | `/auth/logout` | Revoke token and add to `token_blacklist` | Bearer Token (`Authorization: Bearer <token>`) |
| `POST` | `/auth/forgot-password` | Generate cryptographic time-limited password reset token | `{"email": "..."}` |
| `POST` | `/auth/reset-password` | Verify reset token and update hashed password | `{"token": "...", "new_password": "..."}` |

### 2. Autonomous Research Pipeline (Parallel Multi-Critic + `defer=True`)
| Method | Path | Description | Key Request Params / Auth |
| :--- | :--- | :--- | :--- |
| `POST` | `/research/run` | Synchronous parallel research with DuckDuckGo search | `{"topic": "..."}`, `Bearer <token>` |
| `POST` | `/research/stream` | **SSE token & dynamic hint streaming** from Publisher | `{"topic": "..."}`, `Bearer <token>` |
| `GET` | `/research/mermaid` | Live Mermaid diagram of compiled parallel graph | None |

### 3. Model Context Protocol (MCP) Multi-Agent Intelligence Pipeline
| Method | Path | Description | Key Request Params / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/mcp/tools` | List registered MCP servers, connection status & discovered tools | Bearer Token (`Authorization: Bearer <token>`) |
| `POST` | `/mcp/run` | Synchronous execution of MCP subgraphs (`harry_potter` or `airbnb`) | `{"topic": "...", "mode": "harry_potter" \| "airbnb"}`, `Bearer <token>` |
| `POST` | `/mcp/stream` | **SSE streaming** with live agent hints and sub-agent token chunks | `{"topic": "...", "mode": "harry_potter" \| "airbnb"}`, `Bearer <token>` |
| `GET` | `/mcp/mermaid` | Mermaid flowchart definition of compiled sub-graph (`?mode=harry_potter` or `?mode=airbnb`) | None |

### 4. Stateful Policy Decision-Tree (`agent_db`)
| Method | Path | Description | Key Request Params / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Application health and database connection status | None |
| `GET` | `/graph/mermaid` | Mermaid flowchart definition of compiled LangGraph | None |
| `POST` | `/generic_chat` | Context-aware chat with `PostgresChatMessageHistory` | `{"user_input": "...", "session_id": "..."}`, `Bearer <token>` |
| `DELETE` | `/delete_session` | Delete chat messages for a session from PostgreSQL | `{"session_id": "..."}`, `Bearer <token>` |
| `POST` | `/get_sql_query` | Natural language Text-to-SQL agent query | `{"query": "..."}`, `Bearer <token>` |
| `POST` | `/interact` | **SSE streaming** graph execution with Human-in-the-Loop | `{"user_choices": {...}, "user_input": "..."}`, `Bearer <token>` |
| `GET` | `/thread/{thread_id}/state` | Live checkpoint inspection for active thread | `thread_id` (path param), `Bearer <token>` |
| `DELETE` | `/delete_thread` | Delete graph checkpoint from `AsyncPostgresSaver` | `{"thread_id": "..."}`, `Bearer <token>` |
| `WS` | `/ws/interact` | **WebSocket** bidirectional streaming & interrupts | JSON message payloads |

### 5. Institutional NSE Stock Analysis Swarm & Deep Agents Quant Sandbox
| Method | Path | Description | Key Request Params / Auth |
| :--- | :--- | :--- | :--- |
| `POST` | `/stock/analyze` | Execute institutional NSE stock analysis agentic swarm with embedded sandbox modeling | `{"query": "...", "sector_filter": "...", "max_lenses": 6}`, `Bearer <token>` (Required) |
| `GET` | `/stock/report/{run_id}` | View or download full publication-grade HTML research dossier with quant exhibits | `run_id` (path param), `Bearer <token>` or `?token=<jwt>` (Required) |
| `GET` | `/stock/health` | Embedded DuckDB Fact Store status & NIFTY 500 constituents count | None (Public Diagnostic) |
| `GET` | `/stock/mermaid` | Live Mermaid diagram of the 15-node compiled stock graph | None (Public Diagnostic) |
| `GET` | `/stock/sandbox/status` | Telemetry endpoint inspecting active sandbox provider, memory limit (`512m`), and status | `Bearer <token>` (Required) |
| `POST` | `/stock/quant/simulate` | On-demand 5,000-path Monte Carlo (GBM, VaR 95/99, CVaR) or Markowitz Portfolio Optimization | `{"symbol": "RELIANCE.NS", "simulation_type": "monte_carlo"}`, `Bearer <token>` (Required) |
| `POST` | `/stock/sandbox/execute` | Execute custom Python code inside isolated sandbox with resource ceilings and timeout guards | `{"code": "import numpy as np...", "timeout": 30}`, `Bearer <token>` (Required) |

---

## 🔧 Environment Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Primary Groq API Key for LLM inference | `gsk_...` |
| `DEFAULT_MODEL` | Default model identifier on Groq | `openai/gpt-oss-120b` |
| `PLANNER_MAX_TOKENS` | Maximum token limit for Planner node | `800` |
| `APPROVER_MAX_TOKENS` | Maximum token limit for Approver node | `500` |
| `SYNTHESIZER_MAX_TOKENS` | Maximum token limit for Synthesizer node | `1500` |
| `FACT_CRITIC_MAX_TOKENS` | Maximum token limit for Fact Critic node | `600` |
| `STYLE_CRITIC_MAX_TOKENS` | Maximum token limit for Style Critic nodes | `600` |
| `PUBLISHER_MAX_TOKENS` | Maximum token limit for Publisher node | `2500` |
| `GENERIC_CHAT_MAX_TOKENS` | Maximum token limit for Generic Chat agent | `1500` |
| `DATABASE_URL` / `DB_URI` | PostgreSQL connection string for `agent_db` | `postgresql://postgres:postgres@localhost:5432/agent_db` |
| `AUTH_DATABASE_URL` | PostgreSQL connection string for `auth_db` | `postgresql://postgres:postgres@localhost:5432/auth_db` |
| `JWT_SECRET_KEY` | Secret key for cryptographic signing of JWTs | `enterprise-langgraph-secret-key-32-chars-minimum-prod` |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifespan | `60` |
| `RESET_TOKEN_EXPIRE_MINUTES` | Password reset token lifespan | `15` |
| `ENABLE_DDG_SEARCH` | Enable DuckDuckGo live web intelligence | `True` |
| `TAVILY_API_KEY` | Optional Tavily Web Search API key | `""` |
| `ENABLE_AIRBNB_MCP` | Enable Airbnb Stdio MCP server | `True` |
| `AIRBNB_MCP_COMMAND` | Subprocess executable command | `npx` |
| `AIRBNB_MCP_ARGS` | Arguments passed to MCP server | `["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]` |
| `ENABLE_PINECONE_MCP` | Enable Pinecone Stdio MCP server | `True` |
| `PINECONE_API_KEY` | Pinecone API key for serverless vector retrieval | `""` |
| `PINECONE_INDEX_NAME` | Pinecone index name holding Harry Potter corpus | `hpvdb-openai` |
| `QDRANT_ENDPOINT` | Source Qdrant vector database URL (for migration script) | `""` |
| `QDRANT_API_KEY` | Source Qdrant API key | `""` |
| `WEATHER_API_KEY` | WeatherAPI.com API key (Open-Meteo fallback if empty) | `""` |
| `AIRBNB_AGENT_MAX_TOKENS` | Token ceiling for Airbnb MCP agent | `4096` |
| `HP_AGENT_MAX_TOKENS` | Token ceiling for Harry Potter Lore Scholar | `4096` |
| `WEATHER_AGENT_MAX_TOKENS` | Token ceiling for Weather agent | `2048` |
| `TOUR_AGENT_MAX_TOKENS` | Token ceiling for Tour Guide agent | `4096` |
| `LANGFUSE_ENABLED` | Enable Langfuse tracing | `False` |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array or comma-separated) | `["*"]` |

---

## 🏃 Quickstart & Running Locally (with `uv`)

### 1. Create Virtual Environment and Install Dependencies using `uv`
```bash
# Create Python 3.12 virtualenv with uv
uv venv --python 3.12 .venv

# Activate environment
source .venv/bin/activate

# Ultra-fast dependency installation with uv
uv pip install -r requirements.txt
```

### 2. Run Comprehensive Test Suites

#### A. Frontend-to-Backend Quant Sandbox E2E Suite (12 / 12 Passed &mdash; 100%)
Simulates browser user interactions against the live backend (`http://localhost:8000`), testing DOM elements, status telemetry, Quick Monte Carlo, Quick Markowitz Optimization, isolated custom scripting, zero-leak security audit, timeout enforcement, exception handling, and full swarm analysis:
```bash
# Run on host or inside running Docker container
docker exec -i langgraph_api python < scripts/test_fe_stock_sandbox.py
```

#### B. Dedicated Sandbox Unit & Integration Suite (7 / 7 Passed &mdash; 100%)
Validates `SandboxBackendProtocol` compliance, environment sanitization (zero API key leaks), POSIX timeout guards, dual-plane file operations, Monte Carlo VaR/CVaR calculations, Markowitz Sharpe optimization, and LangChain `create_deep_agent(backend=sandbox)` compilation:
```bash
docker exec langgraph_api pytest tests/test_sandbox.py -v
# or locally: uv run pytest tests/test_sandbox.py -v
```

#### C. Live Deep Agents Sandbox API Integration Suite (7 / 7 Passed &mdash; 100%)
Validates all sandbox REST endpoints (`/stock/sandbox/status`, `/stock/quant/simulate`, `/stock/sandbox/execute`), resource limits, timeout guards, and HTML publication exhibits:
```bash
docker exec -i langgraph_api python < scripts/test_sandbox_live.py
```

#### D. Live Stock Swarm Comprehensive Suite (12 / 12 Passed &mdash; 100%)
Validates DuckDB fact store, NIFTY 500 constituents, Mermaid DSL rendering, multi-lens swarm analysis, HTML report generation, and security edge cases:
```bash
docker exec -i langgraph_api python < scripts/test_stock_live.py
```

#### E. Live Backend Endpoint & Critical Edge-Case Suite (45 / 45 Passed &mdash; 100%)
Tests all 7 endpoint categories against the live backend (Public Health, Auth/Security, MCP Travel & Lore, Parallel Research, Stateful Policy Graph with PostgreSQL checkpointing, Text-to-SQL Agent with caching, and WebSocket security):
```bash
python scripts/test_all_endpoints.py
```

#### F. Frontend Simulation, CORS & Browser Integration Suite (11 / 11 Passed &mdash; 100%)
Validates HTML delivery, 14 CSS/ES modules, CORS preflight requests, live signup/login/profile flow, SSE streaming, and WebSocket connectivity from `http://localhost:3000`:
```bash
python scripts/test_fe_live.py
```

#### G. Full Pytest Unit & Middleware Suite
```bash
uv run pytest
```

### 3. Start the FastAPI Backend Server
```bash
# Run pure FastAPI API Gateway on port 8000
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Swagger UI Interactive Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc API Documentation: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Compiled Graph Mermaid View: [http://localhost:8000/graph/mermaid](http://localhost:8000/graph/mermaid)

### 4. Start the Standalone Chat Frontend (Decoupled)
```bash
# Start frontend client on independent port 3000
cd frontend
python3 -m http.server 3000
# or: npx serve -l 3000 .
```
- ChatGPT-Style Web UI (AgentSphere Theme): [http://localhost:3000/](http://localhost:3000/)
- *(Alternatively, the FastAPI backend also serves the frontend directly at [http://localhost:8000/](http://localhost:8000/))*

### 5. Run Institutional NSE Stock Analysis Swarm (CLI & Web UI)

#### A. Standalone Quantitative CLI Runner:
```bash
# 1. Plain-English Targeted Head-to-Head Stock Comparison (Master Deep Agent Planner):
uv run python scripts/run_stock_analysis.py \
  --query "compare HDFC Bank and Reliance performance for next 6 months"

# 2. Plain-English Single Stock Institutional Deep Dive:
uv run python scripts/run_stock_analysis.py \
  --query "research on HDFC Bank in depth"

# 3. Macro / Sector-Filtered Cohort Screen:
uv run python scripts/run_stock_analysis.py \
  --query "Analyze Automobile sector valuation multiples, operating efficiency, and return on equity" \
  --sector "Automobile and Auto Components" \
  --max-lenses 6
```
- Real-time terminal telemetry displays target entity resolution, horizon days, lens progress, verification votes, and section compilation.
- Compiles publication-grade HTML research report with Head-to-Head scorecard and figures to `report.html` and `app/static/top_charts/`.

#### B. AgentSphere Web UI:
- Open [http://localhost:8000/](http://localhost:8000/) or [http://localhost:3000/](http://localhost:3000/).
- Switch to the **NSE Stock Swarm** agent from the left sidebar or top dropdown.
- Type any plain-English query, for example:
  - `"compare HDFC Bank and Reliance performance for next 6 months"`
  - `"research on HDFC Bank in depth"`
  - `"compare Tata Motors and Mahindra & Mahindra performance for next 1 year"`
- The Master Deep Agent Planner resolves target companies and horizons, searches CSV constituents, DuckDB fact store, GNews, and Yahoo Finance, runs isolated Quant Sandbox simulations, passes 4-tier verification, and renders:
  - Target stock badges (`🏦 HDFCBANK`, `⚡ RELIANCE`), analysis mode, and time horizon.
  - Interactive **Head-to-Head Fundamental & Valuation Scorecard** (Price, MCap, P/E, P/B, ROE, 6M Returns).
  - Quantitative Sandbox metrics and Chart Critic-approved exhibits.
- Click **Open Publication Report** to inspect or export the full research dossier.

### 6. Interactive Quant Sandbox Console (Web UI)
- Open [http://localhost:8000/](http://localhost:8000/) or [http://localhost:3000/](http://localhost:3000/).
- Click the **`⚡ Quant Sandbox`** button in the top navigation bar to open the console modal.
- Check the real-time telemetry badge: `🟢 ISOLATED (512MB limit, 1.0 CPU)`.
- **Quick Monte Carlo Simulator**: Enter ticker (e.g. `RELIANCE.NS`), adjust volatility slider, and click **Run 5k Paths** to view mean terminal prices, 95% Value at Risk (VaR), and Conditional VaR (CVaR).
- **Quick Markowitz Optimizer**: Select or enter a basket of equities (`RELIANCE.NS,TCS.NS,HDFCBANK.NS,INFY.NS,ITC.NS`) and click **Optimize Portfolio** to compute optimal Sharpe ratio weights.
- **Custom Python Console**: Write or select math presets in the code editor, click **Run in Sandbox**, and observe real-time execution duration, exit code, and terminal stdout/stderr.

---

## 🐳 Docker & Docker Compose

To run the complete production stack (FastAPI app + PostgreSQL checkpointer & auth store):

```bash
docker compose up --build -d
```

> [!NOTE]
> `docker-compose.yml` automatically mounts [`scripts/init_postgres.sql`](file:///home/sushovan/sushovan/STUDY/Langchain-Langgraph-Notebooks/scripts/init_postgres.sql) into `/docker-entrypoint-initdb.d/`, bootstrapping both `agent_db` (LangGraph checkpointing & chat memory) and `auth_db` (Argon2id user accounts & JWT revocation blacklist) upon container creation.

Check service logs:
```bash
docker compose logs -f api
```

Stop containers:
```bash
docker compose down
```

---

## 🧪 Streaming & Interrupt Client Usage

### 1. Test SSE Streaming (`/interact`)
Run the Python streaming test client:
```bash
python scripts/test_client.py
```

Or test using `curl`:
```bash
curl -N -X POST http://localhost:8000/interact \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_access_token>" \
  -d '{
    "user_choices": {"system_tier": "Tier 2"},
    "user_input": "What are the baseline compliance requirements for an enterprise telemetry engine?",
    "useDeviceData": true,
    "user_provided_device_data": "Cloud Telemetry Ingestion Engine"
  }'
```
> *(Legacy payloads using `userProvidedDeiveceData` are automatically normalized for backward compatibility).*

### 2. Test Parallel Research SSE Stream (`/research/stream`)
```bash
curl -N -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_access_token>" \
  -d '{"topic": "Future of container security architectures and cloud governance standards"}'
```

### 3. Test Multi-Hop MCP Lore QA SSE Stream (`/mcp/stream` with `harry_potter`)
```bash
curl -N -X POST http://localhost:8000/mcp/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_access_token>" \
  -d '{
    "topic": "Explain how the Elder Wand allegiance passed to Harry Potter and list all 7 Horcruxes",
    "mode": "harry_potter"
  }'
```

### 4. Test Airbnb Travel & Weather SSE Stream (`/mcp/stream` with `airbnb`)
```bash
curl -N -X POST http://localhost:8000/mcp/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_access_token>" \
  -d '{
    "topic": "Find 3 cozy cottages near Glenfinnan Viaduct under $150/night for next weekend",
    "mode": "airbnb"
  }'
```

### 5. Test WebSocket Streaming (`/ws/interact`)
Connect to the authenticated WebSocket endpoint (requires query parameter `token`):
```bash
python scripts/test_ws_client.py
# Or connect with websockets: ws://localhost:8000/ws/interact?token=<your_jwt_access_token>
```

---

## 🔄 Adapting for Future Projects

To repurpose this codebase for any new domain (e.g. Legal Analysis, Financial Advising, Customer Service):

1. **State Schema ([app/schemas/state.py](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/schemas/state.py))**: Add custom keys (e.g. `financial_metrics`, `contract_clauses`).
2. **Nodes ([app/graphs/nodes/](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/graphs/nodes/))**: Implement domain nodes subclassing `BaseGraphNode`.
3. **Routing ([app/graphs/routing.py](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/graphs/routing.py))**: Define conditional branching functions.
4. **Graph Builder ([app/graphs/builder.py](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/graphs/builder.py))**: Connect nodes and edges using `StateGraph`.
5. **Retrievers ([app/retrievers/](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/retrievers/))**: Connect domain vector indices to `EnhancedGDNCRetriever`.
