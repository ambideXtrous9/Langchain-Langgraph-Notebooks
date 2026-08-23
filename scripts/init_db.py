"""Database Initialization Script.

Verifies PostgreSQL connectivity, creates required tables for chat history,
and tests the AsyncPostgresSaver checkpointer.
"""

import asyncio
import logging
from psycopg_pool import AsyncConnectionPool
from langchain_postgres import PostgresChatMessageHistory
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s")
logger = logging.getLogger("init_db")


async def init_database():
    db_uri = settings.effective_db_uri
    logger.info(f"Connecting to database: {db_uri.split('@')[-1] if '@' in db_uri else db_uri}")

    try:
        connection_kwargs = {"autocommit": True, "prepare_threshold": None}
        pool = AsyncConnectionPool(
            conninfo=db_uri,
            kwargs=connection_kwargs,
            open=False,
        )
        await pool.open(wait=True, timeout=10)

        # 1. Create chat history table
        async with pool.connection() as conn:
            logger.info(f"Creating / verifying chat message history table: '{settings.TABLE_NAME}'")
            await PostgresChatMessageHistory.acreate_tables(conn, settings.TABLE_NAME)

        # 2. Setup checkpointer tables
        logger.info("Setting up LangGraph checkpointer tables in PostgreSQL...")
        saver = AsyncPostgresSaver(pool)
        await saver.setup()

        logger.info("Database initialized successfully!")
        await pool.close()

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.info("Tip: If PostgreSQL is not running locally, use 'docker compose up postgres -d' to start it.")


if __name__ == "__main__":
    asyncio.run(init_database())
