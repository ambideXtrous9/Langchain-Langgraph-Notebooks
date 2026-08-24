# 🚀 Enterprise LangGraph Production Architecture Template

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Langfuse](https://img.shields.io/badge/Observability-Langfuse-purple.svg)](https://langfuse.com/)
[![Docker](https://img.shields.io/badge/Docker-Multi--Stage-2496ED.svg)](https://www.docker.com/)
[![uv](https://img.shields.io/badge/Package%20Manager-uv-blueviolet.svg)](https://astral.sh/uv)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A reference implementation and production-grade boilerplate for building robust, observable, and stateful AI agent applications with **LangGraph**, **FastAPI**, **OAuth2 Multi-DB Authentication & Blacklisting**, **Agent Middleware Suite (PII, Rate Limiting, HITL, Summarization)**, **Per-Agent Token Budgeting**, **Parallel Multi-Critic Research (`defer=True`)**, **PostgreSQL Checkpointing (`AsyncPostgresSaver`)**, **Langfuse Tracing**, **Server-Sent Events (SSE)**, and **WebSocket Streaming**.

---

## 📑 Table of Contents

- [Architectural Overview](#-architectural-overview)
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

### 1. System Gateway & Multi-DB Architecture (Authentication & Authorization)

The system is decoupled into **Public Authentication** and **Protected Agent Services** backed by dual isolated databases in PostgreSQL:

```
                                  ┌─────────────────────────────────────────────────────────┐
                                  │                     FASTAPI GATEWAY                     │
                                  └────────────────────────────┬────────────────────────────┘
                                                               │
                                       ┌───────────────────────┴───────────────────────┐
                                       │                                               │
                           [Public Auth Endpoints]                         [Protected Agent Endpoints]
                                       │                                               │
                     ┌─────────────────┴─────────────────┐                             │  Depends(get_current_user)
                     │  POST /auth/signup                │                             ▼
                     │  POST /auth/login                 │                 ┌───────────────────────┐
                     │  POST /auth/forgot-password       │                 │ POST /research/run    │
                     │  POST /auth/reset-password        │                 │ POST /research/stream │
                     │  POST /auth/logout                │                 │ POST /interact        │
                     └─────────────────┬─────────────────┘                 │ POST /generic_chat    │
                                       │                                   │ POST /get_sql_query   │
                                       │                                   └───────────┬───────────┘
                                       ▼                                               │
                     ┌───────────────────────────────────┐                             │ (user_id isolation)
                     │       POSTGRES: auth_db           │                             ▼
                     │  - users                          │                 ┌───────────────────────┐
                     │  - token_blacklist                │                 │  POSTGRES: agent_db   │
                     │  - password_reset_tokens          │                 │  - checkpoints        │
                     └───────────────────────────────────┘                 │  - chat_history       │
                                                                           └───────────────────────┘
```

---

### 2. Workflow Graphs

#### A. Regulatory Decision-Tree Graph (Stateful Human-in-the-Loop)
```mermaid
flowchart TD
    Start([User Request]) --> UserInitPath[1. user_initpath\nExtract User Decision & Path]
    UserInitPath --> ClassifyNode[2. classify_node\nStructured Pydantic Classifier with Retries]
    
    ClassifyNode -- "exit" --> EndNode([END])
    ClassifyNode -- "generic" --> FeedbackLoop[6. process_feedback\nHuman-in-the-Loop Interrupt]
    ClassifyNode -- "fda / useDeviceData=True" --> DeviceSummary[3. device_summary\nExtract & Summarize Device Specs]
    ClassifyNode -- "fda / useDeviceData=False" --> KnowledgeBase[4. knowledge_base\nHybrid BM25 + Dense Retrieval]
    
    DeviceSummary --> KnowledgeBase
    KnowledgeBase --> ReasonLLM[5. reason_llm\nDomain Regulatory Reasoning & SSE Tag]
    ReasonLLM --> FeedbackLoop
    FeedbackLoop --> ClassifyNode
```

#### B. Parallel Multi-Critic Research Graph (`defer = True` Join)
```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	planner(planner)
	approver(approver<br/><small><em>autonomous review</em></small>)
	researcher_dispatcher(researcher_dispatcher)
	researcher(researcher<br/><small><em>DuckDuckGo live search</em></small>)
	synthesizer(synthesizer)
	fact_critic(fact_critic<br/><small><em>Branch A: Fact Audit</em></small>)
	style_critic_1(style_critic_1<br/><small><em>Branch B1: Tone & Clarity</em></small>)
	style_critic_2(style_critic_2<br/><small><em>Branch B2: Executive Polish</em></small>)
	publisher(publisher<hr/><small><em>defer = True</em></small>)
	__end__([<p>__end__</p>]):::last
	
	__start__ --> planner;
	planner --> approver;
	approver -. &nbsp;revise&nbsp; .-> planner;
	approver -. &nbsp;dispatch&nbsp; .-> researcher_dispatcher;
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

#### C. Model Context Protocol (MCP) Multi-Agent Travel Graph (Parallel Fan-Out / Fan-In)
```mermaid
flowchart TD
    Start([User Travel Query]) --> AirbnbAgent[1. airbnbAgent\nReAct Agent with Airbnb MCP Tools]
    Start --> WeatherAgent[2. weatherAgent\nReAct Agent with WeatherAPI / Open-Meteo]
    
    AirbnbAgent --> TourAgent[3. tourAgent\nTour Guide Synthesizer & Stay-Weather Match]
    WeatherAgent --> TourAgent
    TourAgent --> EndNode([END])
    
    classDef default fill:#f2f0ff,line-height:1.2
```

---

## ⚙️ Core Mechanisms & Design Patterns

### 1. LangGraph StateGraph & Class-Based Nodes
- **`AgentState` TypedDict**: Manages `tree`, `user_choices`, `current_path_str`, `user_decisions_str`, `context_docs_str`, `classification`, `feedback`, `useDeviceData`, `userProvidedDeiveceData`, and `chat_history` with the `add_messages` reducer.
- **`MCPTravelState` TypedDict**: Manages `topic`, `knowledge` (`add_messages` reducer), `airbnb_report`, `weather_report`, and `summary`.
- **Modular OOP Nodes**: Each node inherits from [BaseGraphNode](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/graphs/nodes/base.py) providing standardized execution boundaries, error handling, and tracing.

### 2. PostgreSQL Checkpointing (`AsyncPostgresSaver`)
- Persistent thread checkpoints stored asynchronously in PostgreSQL with `AsyncPostgresSaver(pool)`.
- Seamless development fallback to `MemorySaver` when PostgreSQL is offline.
- Dedicated `/delete_thread` endpoint for checkpoint eviction and GDPR compliance.

### 3. Server-Sent Events (SSE) & WebSocket Streaming
- **SSE Endpoint (`/interact`)**: Streams the generated `thread_id` first, then yields real-time token chunks using `graph.astream_events(..., version="v2")` filtered on `on_chat_model_stream` and `tags=["RegulatoryExpert"]`.
- **SSE MCP Travel Endpoint (`/mcp/travel/stream`)**: Yields dynamic agent execution hints (`airbnbAgent`, `weatherAgent`, `tourAgent`) and streams raw token chunks tagged with `tags=["TourGuideExpert"]`.
- **WebSocket Endpoint (`/ws/interact`)**: Full-duplex bidirectional streaming supporting initial conversations and instant interrupt resume commands.

### 4. Human-in-the-Loop Interrupts & Resumes
- The `process_feedback` node uses LangGraph's `interrupt()` primitive to safely suspend execution without blocking threads.
- Graph resumes execution upon receiving user feedback via `Command(resume=..., update=...)`.

### 5. Model Context Protocol (MCP) Integration & Lifespan Architecture (`app/core/mcp.py`)

#### A. Architecture & Lifespan Flow
```
                               ┌─────────────────────────────────────────────────────────┐
                               │           FASTAPI APPLICATION LIFESPAN STARTUP          │
                               └────────────────────────────┬────────────────────────────┘
                                                            │
                                                            ▼
                               ┌─────────────────────────────────────────────────────────┐
                               │            MCPClientManager.initialize()                │
                               │  - Spawns stdio subprocess:                             │
                               │    npx -y @openbnb/mcp-server-airbnb --ignore-robots-txt│
                               │  - Opens ClientSession over stdio transport             │
                               │  - Calls session.initialize() handshake                 │
                               │  - load_mcp_tools(session) -> LangChain BaseTool list   │
                               │  - Caches tools in app.state.mcp_manager                │
                               └────────────────────────────┬────────────────────────────┘
                                                            │
                               ┌────────────────────────────┴────────────────────────────┐
                               │                                                         │
                               ▼                                                         ▼
            ┌──────────────────────────────────────┐                  ┌──────────────────────────────────────┐
            │          airbnbAgent (Node)          │                  │          weatherAgent (Node)         │
            │  - Bound with MCP discovered tools   │                  │  - Bound with WeatherForecast tool   │
            │  - Invokes create_react_agent        │                  │  - WeatherAPI with Open-Meteo fallback│
            └──────────────────┬───────────────────┘                  └──────────────────┬───────────────────┘
                               │                                                         │
                               └────────────────────────────┬────────────────────────────┘
                                                            │ (Fan-In)
                                                            ▼
                               ┌─────────────────────────────────────────────────────────┐
                               │             tourAgent Synthesis Node                    │
                               │  - Merges Airbnb property listings & Weather forecast   │
                               │  - Synthesizes customized travel advisory & stay match  │
                               │  - Streams tokens tagged with ["TourGuideExpert"]       │
                               └────────────────────────────┬────────────────────────────┘
                                                            │
                                                            ▼
                               ┌─────────────────────────────────────────────────────────┐
                               │           FASTAPI APPLICATION LIFESPAN SHUTDOWN         │
                               │  - MCPClientManager.shutdown()                          │
                               │  - Closes stdio sessions and terminates subprocesses    │
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
- **`HumanInTheLoopMiddleware`**: Intercepts sensitive tool calls (e.g. `execute_sql_mutation`, `submit_fda_filing`) and pauses execution until human authorization is granted.
- **`SummarizationMiddleware`**: Token- and message-count-aware chat history compressor (`trigger=[("tokens", 1200), ("messages", 8)]`), summarizing older dialogue while preserving recent context.

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
│   │           └── websocket.py# /ws/interact (Bidirectional streaming WebSocket)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Pydantic BaseSettings (DB, LLM, Token Budgets, Auth, Langfuse)
│   │   ├── database.py         # AsyncConnectionPool & Postgres checkpointing manager (agent_db)
│   │   ├── auth_database.py    # Auth DB connection pool, table DDL, and token blacklist (auth_db)
│   │   ├── security.py         # Argon2id password hashing & PyJWT token utilities
│   │   ├── llm.py              # ChatGroq LLM factory with per-node token limit support
│   │   ├── exceptions.py       # Custom application exceptions and error handlers
│   │   └── observability.py    # Langfuse callback handlers and RunnableConfig builder
│   ├── middleware/
│   │   ├── __init__.py         # Default global middleware pipeline exports
│   │   ├── base.py             # AgentMiddleware abstract base class & pipeline executor
│   │   ├── pii.py              # PIIMiddleware (mask, redact, hash sensitive data)
│   │   ├── rate_limit.py       # RateLimitMiddleware (sliding window & error budget circuit breaker)
│   │   ├── hitl.py             # HumanInTheLoopMiddleware (sensitive tool interceptor)
│   │   └── summarizer.py       # SummarizationMiddleware (token/message trigger history compressor)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py             # UserSignupRequest, UserLoginRequest, UserResponse, TokenResponse
│   │   ├── state.py            # LangGraph AgentState TypedDict & Classify Pydantic model
│   │   ├── research.py         # ResearchRequest, ResearchReport, ResearchStreamEvent
│   │   ├── chat.py             # ChatRequest, ChatResponse, DeleteSession
│   │   ├── sql.py              # SQLQueryRequest, SQLQueryResponse
│   │   └── interact.py         # InteractionRequest, DeleteThreadRequest, GraphStateResponse
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── react_agent.py      # ReAct agent with tools (DuckDuckGo/Tavily) & middleware
│   │   ├── sql_agent.py        # SQL agent with SQLDatabaseToolkit & query executor
│   │   └── classifier_agent.py # Structured JSON classifier with self-correcting retry loop
│   ├── tools/
│   │   ├── __init__.py
│   │   └── weather.py          # Weather forecast tool (WeatherAPI with Open-Meteo fallback)
│   ├── graphs/
│   │   ├── __init__.py
│   │   ├── routing.py          # Conditional edge routing functions (decide_start_node)
│   │   ├── builder.py          # GraphBuilder & StateGraph compilation factory
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
│   │   └── mcp/
│   │       ├── __init__.py
│   │       ├── builder.py      # MCPTravelGraphBuilder with concurrent Airbnb/Weather fan-out
│   │       └── nodes.py        # Airbnb Agent (MCP tools), Weather Agent, and Tour Guide nodes
│   └── retrievers/
│       ├── __init__.py
│       ├── hybrid_reranker.py  # Lightweight filtering & BM25 retrieval
│       └── ensemble.py         # Dynamic EnsembleRetriever builder
├── scripts/
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
    └── test_mcp.py             # Model Context Protocol (MCP) and multi-agent travel tests
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

### 3. Model Context Protocol (MCP) Multi-Agent Travel Pipeline
| Method | Path | Description | Key Request Params / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/mcp/tools` | List registered MCP servers, connection status & discovered tools | Bearer Token (`Authorization: Bearer <token>`) |
| `POST` | `/mcp/travel/run` | Synchronous execution of concurrent Airbnb MCP & Weather agents | `{"topic": "..."}`, `Bearer <token>` |
| `POST` | `/mcp/travel/stream` | **SSE streaming** with live agent hints and Tour Guide tokens | `{"topic": "..."}`, `Bearer <token>` |
| `GET` | `/mcp/travel/mermaid` | Mermaid flowchart definition of compiled MCP graph | None |

### 4. Stateful Regulatory Decision-Tree (`agent_db`)
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
| `WEATHER_API_KEY` | WeatherAPI.com API key (Open-Meteo fallback if empty) | `""` |
| `AIRBNB_AGENT_MAX_TOKENS` | Token ceiling for Airbnb MCP agent | `1500` |
| `WEATHER_AGENT_MAX_TOKENS` | Token ceiling for Weather agent | `1000` |
| `TOUR_AGENT_MAX_TOKENS` | Token ceiling for Tour Guide agent | `2500` |
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

### 2. Run Test Suite
```bash
# Run pytest with uv
uv run pytest
```

### 3. Start the FastAPI Server
```bash
# Run FastAPI server with hot-reload
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Swagger UI Interactive Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc API Documentation: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Compiled Graph Mermaid View: [http://localhost:8000/graph/mermaid](http://localhost:8000/graph/mermaid)

---

## 🐳 Docker & Docker Compose

To run the complete production stack (FastAPI app + PostgreSQL checkpointer):

```bash
docker compose up --build -d
```

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
  -d '{
    "user_choices": {"device_class": "Class II"},
    "user_input": "What is the 510k pathway requirements for a diagnostic monitor?",
    "useDeviceData": true,
    "userProvidedDeiveceData": "Digital ECG monitor"
  }'
```

### 2. Test Parallel Research SSE Stream (`/research/stream`)
```bash
curl -N -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_access_token>" \
  -d '{"topic": "Future of robotic laparoscopic surgery and FDA safety alerts"}'
```

### 3. Test MCP Travel & Accommodation SSE Stream (`/mcp/travel/stream`)
```bash
curl -N -X POST http://localhost:8000/mcp/travel/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_access_token>" \
  -d '{"topic": "Find me the top 5 Airbnb in Darjeeling for next 3 days within 8000 for 2 people"}'
```

### 4. Test WebSocket Streaming (`/ws/interact`)
Run the WebSocket test script:
```bash
python scripts/test_ws_client.py
```

---

## 🔄 Adapting for Future Projects

To repurpose this codebase for any new domain (e.g. Legal Analysis, Financial Advising, Customer Service):

1. **State Schema ([app/schemas/state.py](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/schemas/state.py))**: Add custom keys (e.g. `financial_metrics`, `contract_clauses`).
2. **Nodes ([app/graphs/nodes/](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/graphs/nodes/))**: Implement domain nodes subclassing `BaseGraphNode`.
3. **Routing ([app/graphs/routing.py](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/graphs/routing.py))**: Define conditional branching functions.
4. **Graph Builder ([app/graphs/builder.py](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/graphs/builder.py))**: Connect nodes and edges using `StateGraph`.
5. **Retrievers ([app/retrievers/](file:///home/sushovan/sushovan/STUDY/langgraph-project/app/retrievers/))**: Connect domain vector indices to `EnhancedGDNCRetriever`.
