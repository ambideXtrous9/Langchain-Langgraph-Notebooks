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

#### C. Model Context Protocol (MCP) Multi-Agent Intelligence Graphs

##### Mode 1: ⚡ Multi-Hop Harry Potter Lore QA Graph (`@pinecone-database/mcp`)
```mermaid
flowchart TD
    Start([User Harry Potter Complex Question]) --> HPSearchAgent[1. hpSearchAgent\nMulti-Hop ReAct Agent\nPinecone MCP Index: hpvdb-openai\nTools: search-records, list-indexes,\ndescribe-index-stats, rerank-documents,\ncascading-search, search-docs]
    HPSearchAgent -->|Multi-Hop Trace & Reranked Passages| HPLoreScholar[2. hpLoreScholar\nMaster Lore Scholar Synthesizer\nChronological Causal Chain Analysis]
    HPLoreScholar --> EndNode([END])
    
    classDef default fill:#f2f0ff,line-height:1.2
```

##### Mode 2: 🏨 Airbnb Travel & Lodging Graph (`@openbnb/mcp-server-airbnb` + WeatherAPI)
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

---

## ⚙️ Core Mechanisms & Design Patterns

### 1. LangGraph StateGraph & Class-Based Nodes
- **`AgentState` TypedDict**: Manages `tree`, `user_choices`, `current_path_str`, `user_decisions_str`, `context_docs_str`, `classification`, `feedback`, `useDeviceData`, `userProvidedDeiveceData`, and `chat_history` with the `add_messages` reducer.
- **`MCPState` / `MCPTravelState` TypedDict**: Manages `topic`, `knowledge` (`add_messages` reducer), `hp_report` (HP QA), `airbnb_report`, `weather_report`, and `summary` (Airbnb mode).
- **Modular OOP Nodes**: Each node inherits from standardized execution boundaries, error handling, and tracing.

### 2. PostgreSQL Checkpointing (`AsyncPostgresSaver`)
- Persistent thread checkpoints stored asynchronously in PostgreSQL with `AsyncPostgresSaver(pool)`.
- Seamless development fallback to `MemorySaver` when PostgreSQL is offline.
- Dedicated `/delete_thread` endpoint for checkpoint eviction and GDPR compliance.

### 3. Server-Sent Events (SSE) & WebSocket Streaming
- **SSE Endpoint (`/interact`)**: Streams the generated `thread_id` first, then yields real-time token chunks using `graph.astream_events(..., version="v2")` filtered on `on_chat_model_stream` and `tags=["RegulatoryExpert"]`.
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
- **`HumanInTheLoopMiddleware`**: Intercepts sensitive tool calls (e.g. `execute_sql_mutation`, `submit_fda_filing`) and pauses execution until human authorization is granted.
- **`SummarizationMiddleware`**: Token- and message-count-aware chat history compressor (`trigger=[("tokens", 1200), ("messages", 8)]`), summarizing older dialogue while preserving recent context.

### 10. Centralized Streaming Engine (`app/core/streaming.py`)
- **DRY SSE Event Generation**: Unified `stream_graph_events` async generator eliminates repetitive SSE serialization across endpoints (`/interact`, `/research/stream`, `/mcp/stream`).
- **Granular Token & Hint Filtering**: Emits metadata events (`tool_start`, `tool_end`, `stage`, `hint`) while routing filtered `on_chat_model_stream` tokens with active agent tags (`RegulatoryExpert`, `HPLoreScholar`, `TourGuideExpert`, `Publisher`).
- **Heartbeat & Error Encapsulation**: Guarantees keep-alive heartbeats during long reasoning cycles and gracefully emits structured `{"error": "..."}` payloads if an upstream model or tool errors.

### 11. Graph Visualizer & Artifact Engine (`app/graphs/visualizer.py`)
- **Dynamic Mermaid & PNG Rendering**: Centralized compilation pipeline for generating Mermaid `.mmd` files and compiled `.png` image artifacts directly into `app/static/`.
- **Domain-Specific Graph Export**: Generates and serves diagrams for all 3 stateful graphs:
  - Regulatory Decision Graph (`graph.mmd`, `graph.png`)
  - Autonomous Parallel Research Graph (`research_graph.mmd`, `research_graph.png`)
  - Dual MCP Intelligence Graph (`mcp_graph_hp.mmd`, `mcp_graph_airbnb.mmd`, `mcp_graph.png`)

### 12. Modern Decoupled Frontend UX (`frontend/`)
- **Custom MCP Mode Dropdown**: Replaced the hybrid native `<select>` with a custom dropdown (`#mcp-dropdown-trigger` & `#mcp-dropdown-menu`). Completely resolves duplicate emoji rendering (`🏨 🏨` -> `🏨`), OS-level popup collisions, and establishes mutual exclusion with the Agent menu.
- **Context-Aware Dynamic Parameter Input**: The top navbar `[ Parameters ]` button is automatically displayed only for agents that require configurable parameters (`regulatory`) and hidden for all other agents. Pre-populates form state on click and dynamically binds values to live SSE execution payloads.
- **WebSocket Handshake Authentication**: Automatically appends `?token=${encodeURIComponent(token)}` to the connection URI, ensuring seamless compatibility with WebSocket JWT authorization.
- **Schema Normalization**: Fully supports the standardized `user_provided_device_data` attribute while preserving backward compatibility with legacy `userProvidedDeiveceData` payloads.

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
│   │   ├── observability.py    # Langfuse callback handlers and RunnableConfig builder
│   │   └── streaming.py        # Centralized async SSE & token streaming event generator
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
│   │   └── mcp/
│   │       ├── __init__.py
│   │       ├── builder.py      # MCPTravelGraphBuilder with concurrent Airbnb/Weather fan-out
│   │       └── nodes.py        # Airbnb Agent (MCP tools), Weather Agent, and Tour Guide nodes
│   └── retrievers/
│       ├── __init__.py
│       ├── hybrid_reranker.py  # Lightweight filtering & BM25 retrieval
│       └── ensemble.py         # Dynamic EnsembleRetriever builder
├── frontend/                   # Decoupled Standalone ChatGPT-Style SPA (Vanilla JS + ES Modules)
│   ├── index.html              # Modern multi-agent interface with custom MCP dropdown
│   ├── css/
│   │   ├── theme.css           # Design tokens, typography & dark/light palette
│   │   ├── components.css      # Custom buttons, modals, cards, tags & switch toggles
│   │   └── chat.css            # Chat layouts, thinking accordions & custom dropdowns
│   └── js/
│       ├── config.js           # API route mappings & localStorage persistence keys
│       ├── api.js              # Fetch wrapper, SSE reader & authenticated WebSocket client
│       ├── auth.js             # Argon2id signup, login, profile & JWT token management
│       ├── agents.js           # Agent metadata, capability flags (hasParams) & mode presets
│       ├── chat.js             # Dynamic agent switcher, param visibility & streaming loop
│       ├── decisionTree.js     # Regulatory navigator, state inspector & thread eviction
│       ├── research.js         # Parallel multi-critic runner & dynamic critic hints
│       ├── mcp.js              # Stdio MCP tool inspector & dual-mode travel/lore runner
│       ├── sqlAgent.js         # Natural language to SQL runner & interactive data table
│       ├── topology.js         # Mermaid flowchart drawer & node inspection
│       └── app.js              # Application bootstrapper, modal management & toast alerts
├── scripts/
│   ├── init_postgres.sql       # Automatic auth_db and agent_db Docker bootstrap script
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

### 3. Model Context Protocol (MCP) Multi-Agent Intelligence Pipeline
| Method | Path | Description | Key Request Params / Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/mcp/tools` | List registered MCP servers, connection status & discovered tools | Bearer Token (`Authorization: Bearer <token>`) |
| `POST` | `/mcp/run` | Synchronous execution of MCP subgraphs (`harry_potter` or `airbnb`) | `{"topic": "...", "mode": "harry_potter" \| "airbnb"}`, `Bearer <token>` |
| `POST` | `/mcp/stream` | **SSE streaming** with live agent hints and sub-agent token chunks | `{"topic": "...", "mode": "harry_potter" \| "airbnb"}`, `Bearer <token>` |
| `GET` | `/mcp/mermaid` | Mermaid flowchart definition of compiled sub-graph (`?mode=harry_potter` or `?mode=airbnb`) | None |

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

#### A. Live Backend Endpoint & Critical Edge-Case Suite (45 / 45 Passed &mdash; 100%)
Tests all 7 endpoint categories against the live backend (Public Health, Auth/Security, MCP Travel & Lore, Parallel Research, Stateful Regulatory Graph with PostgreSQL checkpointing, Text-to-SQL Agent with caching, and WebSocket security):
```bash
python scripts/test_all_endpoints.py
```

#### B. Frontend Simulation, CORS & Browser Integration Suite (11 / 11 Passed &mdash; 100%)
Validates HTML delivery, 14 CSS/ES modules, CORS preflight requests, live signup/login/profile flow, SSE streaming, and WebSocket connectivity from `http://localhost:3000`:
```bash
python scripts/test_fe_live.py
```

#### C. Unit & Middleware Tests (Pytest)
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
- ChatGPT-Style Web UI (RP360 Theme): [http://localhost:3000/](http://localhost:3000/)

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
    "user_choices": {"device_class": "Class II"},
    "user_input": "What is the 510k pathway requirements for a diagnostic monitor?",
    "useDeviceData": true,
    "user_provided_device_data": "Digital ECG monitor"
  }'
```
> *(Legacy payloads using `userProvidedDeiveceData` are automatically normalized for backward compatibility).*

### 2. Test Parallel Research SSE Stream (`/research/stream`)
```bash
curl -N -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_access_token>" \
  -d '{"topic": "Future of robotic laparoscopic surgery and FDA safety alerts"}'
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
