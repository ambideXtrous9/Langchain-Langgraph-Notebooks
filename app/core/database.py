"""Database Management and Connection Pooling Module."""

import logging
from typing import Optional
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from psycopg import sql
from langchain_postgres import PostgresChatMessageHistory
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL connection pool, chat message history tables, and LangGraph checkpointer."""

    def __init__(self):
        self.pool: Optional[AsyncConnectionPool] = None
        self.checkpointer = None
        self._is_in_memory: bool = False

    async def initialize(self) -> None:
        """Initializes the AsyncConnectionPool, creates chat history tables, and sets up AsyncPostgresSaver."""
        db_uri = settings.effective_db_uri
        logger.info(f"Connecting to database at: {db_uri.split('@')[-1] if '@' in db_uri else 'local'}")

        connection_kwargs = {"autocommit": True, "prepare_threshold": None}

        try:
            self.pool = AsyncConnectionPool(
                conninfo=db_uri,
                min_size=settings.DB_POOL_MIN_SIZE,
                max_size=settings.DB_POOL_MAX_SIZE,
                kwargs=connection_kwargs,
                open=False,
            )
            await self.pool.open(wait=True, timeout=settings.DB_POOL_TIMEOUT)

            # 1. Initialize PostgresChatMessageHistory table
            async with self.pool.connection() as conn:
                logger.info(f"Ensuring chat history table '{settings.TABLE_NAME}' exists...")
                await PostgresChatMessageHistory.acreate_tables(conn, settings.TABLE_NAME)

            # 2. Initialize AsyncPostgresSaver checkpointer for LangGraph
            logger.info("Setting up LangGraph AsyncPostgresSaver checkpointer...")
            self.checkpointer = AsyncPostgresSaver(self.pool)
            await self.checkpointer.setup()

            self._is_in_memory = False
            logger.info("Database connection and checkpointer initialized successfully.")

        except Exception as e:
            logger.error(
                f"Failed to connect to PostgreSQL: {e}. "
                "Falling back to in-memory checkpointer for local development/testing."
            )
            if self.pool:
                try:
                    await self.pool.close()
                except Exception:
                    pass
            self.pool = None
            self._is_in_memory = True
            self.checkpointer = MemorySaver()

    async def close(self) -> None:
        """Closes the AsyncConnectionPool."""
        if self.pool and not self._is_in_memory:
            try:
                await self.pool.close()
                logger.info("Database connection pool closed successfully.")
            except Exception as e:
                logger.warning(f"Error while closing database connection pool: {e}")

    @asynccontextmanager
    async def get_connection(self):
        """Context manager yielding a pooled connection."""
        if not self.pool or self._is_in_memory:
            raise RuntimeError("Database pool is not connected. Check DATABASE_URL configuration.")
        async with self.pool.connection() as conn:
            yield conn

    async def get_chat_history(
        self, session_id: str, conn=None
    ) -> PostgresChatMessageHistory:
        """Returns a PostgresChatMessageHistory instance for a given session."""
        if self._is_in_memory or not self.pool:
            raise RuntimeError("PostgresChatMessageHistory requires a connected PostgreSQL database.")
        connection = conn or await self.pool.getconn()
        return PostgresChatMessageHistory(
            settings.TABLE_NAME,
            session_id,
            async_connection=connection,
        )

    async def delete_chat_session(self, session_id: str) -> bool:
        """Deletes all messages for a specific session_id from the chat history table."""
        if self._is_in_memory or not self.pool:
            return False

        query = sql.SQL("DELETE FROM {} WHERE session_id = %s").format(
            sql.Identifier(settings.TABLE_NAME)
        )
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (session_id,))
                deleted_rows = cur.rowcount
                return deleted_rows > 0

    @property
    def is_in_memory(self) -> bool:
        """Returns True if the checkpointer is running in-memory fallback."""
        return self._is_in_memory


db_manager = DatabaseManager()
