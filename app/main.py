"""FastAPI Main Application Entrypoint with Lifespan, CORS, and Endpoint Routing."""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import db_manager
from app.core.auth_database import auth_db_manager
from app.core.mcp import mcp_manager
from app.core.exceptions import register_exception_handlers
from app.core.observability import flush_langfuse, init_langfuse
from app.graphs.builder import create_graph, GraphBuilder
from app.graphs.research.builder import ResearchGraphBuilder
from app.graphs.mcp.builder import MCPTravelGraphBuilder
from app.api.v1.router import api_router

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager handling resource initialization and cleanup."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")

    # 1. Initialize & Authenticate Langfuse Observability Client
    init_langfuse()

    # 2. Initialize PostgreSQL Pool & Checkpointer (agent_db)
    await db_manager.initialize()
    app.state.db_pool = db_manager.pool
    app.state.checkpointer = db_manager.checkpointer

    # 3. Initialize Authentication Database Pool & Tables (auth_db)
    await auth_db_manager.initialize()
    app.state.auth_db_pool = auth_db_manager.pool

    # 4. Initialize MCP (Model Context Protocol) Client Manager & Load Tools
    await mcp_manager.initialize()
    app.state.mcp_manager = mcp_manager

    # 5. Build & Compile Main Policy Decision Graph
    builder = GraphBuilder(checkpointer=app.state.checkpointer)
    builder.build()
    app.state.graph = builder.compile()

    # 6. Build & Compile Parallel Research, Critic & Publisher Graph (defer=True)
    research_builder = ResearchGraphBuilder(checkpointer=app.state.checkpointer)
    research_builder.build()
    app.state.research_graph = research_builder.compile()

    # 7. Build & Compile MCP Travel & Intelligence Multi-Agent Graph
    mcp_travel_builder = MCPTravelGraphBuilder(checkpointer=app.state.checkpointer)
    app.state.mcp_travel_graph = mcp_travel_builder.build_graph()

    # 8. Export Graph Visualizations
    os.makedirs("app/static", exist_ok=True)
    builder.save_visualization("app/static/graph.png")
    research_builder.save_visualization("app/static/research_graph.png")
    mcp_travel_builder.save_visualization("app/static/mcp_graph.png")

    logger.info("Application initialization complete. Ready to serve requests.")

    yield

    # Teardown
    logger.info("Shutting down application resources...")
    await mcp_manager.shutdown()
    flush_langfuse()
    await auth_db_manager.close()
    await db_manager.close()
    logger.info("Application shutdown complete.")


# Create FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Enterprise-grade LangGraph production template featuring PostgreSQL checkpointing, "
        "Server-Sent Events (SSE) and WebSocket streaming, Langfuse observability, "
        "Hybrid Cross-Encoder Reranking, SQL Agent, and Human-in-the-Loop interrupt capabilities."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Custom Exception Handlers
register_exception_handlers(app)

# Mount Static Files (e.g. Graph diagrams)
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount Routers
# Direct root routes matching AgentNotes.ipynb specifications
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
