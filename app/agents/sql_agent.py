"""SQL Agent for Natural Language Database Querying and Analysis."""

import logging
from typing import Any, Dict, Optional, Tuple
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from app.core.config import settings
from app.core.llm import get_llm

logger = logging.getLogger(__name__)


def create_demo_sqlite_db() -> SQLDatabase:
    """Creates a sample in-memory SQLite database for testing and demonstration."""
    from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()

    # Create sample Enterprise Systems table
    systems = Table(
        "enterprise_systems",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("system_name", String(100)),
        Column("system_tier", String(20)),
        Column("certification_year", Integer),
        Column("risk_level", String(20)),
        Column("vendor", String(100)),
    )

    metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(
            systems.insert(),
            [
                {
                    "system_name": "CloudIdentity Pro",
                    "system_tier": "Tier 3",
                    "certification_year": 2021,
                    "risk_level": "High",
                    "vendor": "SecureTech Corp",
                },
                {
                    "system_name": "DataPipeline Sensor",
                    "system_tier": "Tier 2",
                    "certification_year": 2022,
                    "risk_level": "Moderate",
                    "vendor": "InfraSense Inc",
                },
                {
                    "system_name": "Telemetry Gateway AI",
                    "system_tier": "Tier 2",
                    "certification_year": 2023,
                    "risk_level": "Low",
                    "vendor": "CloudSound Ltd",
                },
            ],
        )
        conn.commit()

    return SQLDatabase(engine)


_agent_cache: Dict[str, Any] = {}


def load_sql_agent(db_uri: Optional[str] = None, llm: Optional[Any] = None):
    """Loads and compiles the SQL Agent Executor with toolkit."""
    cache_key = f"{db_uri or settings.effective_db_uri or 'demo'}"
    if cache_key in _agent_cache:
        return _agent_cache[cache_key]

    if llm is None:
        llm = get_llm(max_tokens=1000)

    try:
        if db_uri:
            uri = db_uri
            if uri.startswith("postgresql://") and "+psycopg" not in uri:
                uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
            db = SQLDatabase.from_uri(uri)
        else:
            try:
                uri = settings.effective_db_uri
                if uri.startswith("postgresql://") and "+psycopg" not in uri:
                    uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
                db = SQLDatabase.from_uri(uri)
            except Exception:
                logger.warning("Could not connect to PostgreSQL for SQL Agent. Using demo SQLite database.")
                db = create_demo_sqlite_db()
    except Exception as e:
        logger.warning(f"Error connecting to database: {e}. Falling back to demo SQLite DB.")
        db = create_demo_sqlite_db()

    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    agent = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=settings.DEBUG,
        agent_type="openai-tools",
        agent_executor_kwargs={"return_intermediate_steps": True},
    )
    _agent_cache[cache_key] = agent
    return agent


def execute_sql_query(
    query: str,
    db_uri: Optional[str] = None,
    agent=None,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Optional[str], Optional[str]]:
    """Executes a natural language query with the SQL Agent.

    Returns:
        Tuple containing (final_answer, sql_query, table_result).
    """
    if agent is None:
        agent = load_sql_agent(db_uri=db_uri)

    try:
        result = agent.invoke({"input": query}, config=config)
        final_answer = result.get("output", "No answer generated.")
        intermediate_steps = result.get("intermediate_steps", [])

        sql_query = None
        table_result = None

        # Extract SQL query and execution output from intermediate steps
        for action, observation in intermediate_steps:
            if hasattr(action, "tool") and "sql_db_query" in action.tool:
                sql_query = action.tool_input if isinstance(action.tool_input, str) else str(action.tool_input.get("query", action.tool_input))
                table_result = str(observation)

        return final_answer, sql_query, table_result

    except Exception as e:
        logger.error(f"SQL Agent execution error: {e}")
        return f"Failed to execute SQL query: {str(e)}", None, None
