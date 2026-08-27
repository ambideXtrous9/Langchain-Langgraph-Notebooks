"""Authentication Database Management Module (PostgreSQL auth_db)."""

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthDatabaseManager:
    """Manages PostgreSQL connection pool and user/auth tables in auth_db."""

    def __init__(self):
        self.pool: Optional[AsyncConnectionPool] = None
        self._in_memory_users: Dict[str, Dict[str, Any]] = {}
        self._in_memory_blacklist: set = set()
        self._in_memory_reset_tokens: Dict[str, Dict[str, Any]] = {}
        self._is_in_memory: bool = False
        self._load_fallback()

    def _get_fallback_file(self) -> str:
        os.makedirs("app/static", exist_ok=True)
        return "app/static/auth_store.json"

    def _load_fallback(self) -> None:
        """Loads persistent auth fallback accounts from disk."""
        try:
            path = self._get_fallback_file()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._in_memory_users = data.get("users", {})
                    self._in_memory_reset_tokens = data.get("reset_tokens", {})
                    logger.info(f"Loaded {len(self._in_memory_users)} cached user accounts from fallback file.")
        except Exception as e:
            logger.warning(f"Could not load auth fallback file: {e}")

    def _save_fallback(self) -> None:
        """Persists auth accounts to disk."""
        try:
            path = self._get_fallback_file()
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "users": self._in_memory_users,
                    "reset_tokens": self._in_memory_reset_tokens,
                }, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Could not save auth fallback file: {e}")

    async def initialize(self) -> None:
        """Initializes PostgreSQL connection pool and creates auth tables."""
        auth_uri = settings.AUTH_DATABASE_URL
        logger.info(f"Connecting to Auth Database at: {auth_uri.split('@')[-1] if '@' in auth_uri else 'local'}")

        # 1. Ensure auth_db exists on PostgreSQL server
        await self._ensure_database_exists(auth_uri)

        connection_kwargs = {
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": None,
        }

        try:
            self.pool = AsyncConnectionPool(
                conninfo=auth_uri,
                min_size=settings.AUTH_DB_POOL_MIN_SIZE,
                max_size=settings.AUTH_DB_POOL_MAX_SIZE,
                kwargs=connection_kwargs,
                open=False,
            )
            await self.pool.open(wait=True, timeout=settings.DB_POOL_TIMEOUT)

            # 2. Create Schema Tables
            await self._create_tables()

            # 3. Sync any cached fallback accounts to PostgreSQL
            await self._sync_fallback_to_postgres()

            self._is_in_memory = False
            logger.info("Auth Database (auth_db) initialized successfully.")

        except Exception as e:
            logger.warning(
                f"Failed to connect to PostgreSQL auth_db: {e}. "
                "Enabling In-Memory Auth Fallback with disk persistence."
            )
            if self.pool:
                try:
                    await self.pool.close()
                except Exception:
                    pass
                self.pool = None
            self._is_in_memory = True

    async def _sync_fallback_to_postgres(self) -> None:
        """Syncs cached users to PostgreSQL if any exist."""
        if not self.pool or not self._in_memory_users:
            return
        try:
            async with self.pool.connection() as conn:
                async with conn.cursor() as cur:
                    for email, u in self._in_memory_users.items():
                        await cur.execute(
                            """
                            INSERT INTO users (id, email, full_name, hashed_password, is_active, is_superuser, role)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (email) DO NOTHING
                            """,
                            (
                                u.get("id", str(uuid.uuid4())),
                                email,
                                u.get("full_name", ""),
                                u.get("hashed_password", ""),
                                u.get("is_active", True),
                                u.get("is_superuser", False),
                                u.get("role", "user"),
                            ),
                        )
            logger.info("Synced offline user accounts into PostgreSQL auth_db.")
        except Exception as e:
            logger.warning(f"Could not sync fallback users into PostgreSQL: {e}")

    async def _ensure_database_exists(self, auth_uri: str) -> None:
        """Connects to default postgres DB and creates auth_db if it does not exist."""
        try:
            base_uri, db_name = auth_uri.rsplit("/", 1)
            postgres_uri = f"{base_uri}/postgres"

            async with await psycopg.AsyncConnection.connect(postgres_uri, autocommit=True) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                    exists = await cur.fetchone()
                    if not exists:
                        logger.info(f"Database '{db_name}' does not exist. Creating database '{db_name}'...")
                        await cur.execute(f'CREATE DATABASE "{db_name}"')
                        logger.info(f"Database '{db_name}' created successfully.")
        except Exception as e:
            logger.debug(f"Database auto-creation check note: {e}")

    async def _create_tables(self) -> None:
        """Creates auth tables: users, token_blacklist, password_reset_tokens."""
        if not self.pool:
            return

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Users Table
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email VARCHAR(255) UNIQUE NOT NULL,
                        full_name VARCHAR(150),
                        hashed_password VARCHAR(255) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_superuser BOOLEAN DEFAULT FALSE,
                        role VARCHAR(50) DEFAULT 'user',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
                """)

                # 2. Token Blacklist Table
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS token_blacklist (
                        id SERIAL PRIMARY KEY,
                        token_jti VARCHAR(255) UNIQUE NOT NULL,
                        user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        revoked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_token_blacklist_jti ON token_blacklist(token_jti);
                """)

                # 3. Password Reset Tokens Table
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        id SERIAL PRIMARY KEY,
                        user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                        token_hash VARCHAR(255) UNIQUE NOT NULL,
                        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        is_used BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX IF NOT EXISTS idx_reset_token_hash ON password_reset_tokens(token_hash);
                """)

    async def close(self) -> None:
        """Closes the connection pool on application shutdown."""
        if self.pool:
            logger.info("Closing Auth Database connection pool...")
            await self.pool.close()
            self.pool = None
            logger.info("Auth Database connection pool closed successfully.")

    # --------------------------------------------------------------------------
    # User Operations
    # --------------------------------------------------------------------------
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Finds user by email address."""
        email_normalized = email.strip().lower()

        if self._is_in_memory or not self.pool:
            return self._in_memory_users.get(email_normalized)

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, email, full_name, hashed_password, is_active, is_superuser, role, created_at, updated_at "
                    "FROM users WHERE LOWER(email) = %s",
                    (email_normalized,),
                )
                row = await cur.fetchone()
                if row:
                    row["id"] = str(row["id"])
                return row

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Finds user by UUID identifier."""
        if self._is_in_memory or not self.pool:
            for u in self._in_memory_users.values():
                if u.get("id") == str(user_id):
                    return u
            return None

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id, email, full_name, hashed_password, is_active, is_superuser, role, created_at, updated_at "
                    "FROM users WHERE id = %s",
                    (user_id,),
                )
                row = await cur.fetchone()
                if row:
                    row["id"] = str(row["id"])
                return row

    async def create_user(
        self,
        email: str,
        full_name: str,
        hashed_password: str,
        role: str = "user",
        is_superuser: bool = False,
    ) -> Dict[str, Any]:
        """Creates a new user record in auth_db."""
        email_normalized = email.strip().lower()
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        if self._is_in_memory or not self.pool:
            user_record = {
                "id": user_id,
                "email": email_normalized,
                "full_name": full_name,
                "hashed_password": hashed_password,
                "is_active": True,
                "is_superuser": is_superuser,
                "role": role,
                "created_at": now,
                "updated_at": now,
            }
            self._in_memory_users[email_normalized] = user_record
            self._save_fallback()
            return user_record

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO users (id, email, full_name, hashed_password, is_active, is_superuser, role, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, email, full_name, is_active, is_superuser, role, created_at, updated_at
                    """,
                    (user_id, email_normalized, full_name, hashed_password, True, is_superuser, role, now, now),
                )
                row = await cur.fetchone()
                row["id"] = str(row["id"])
                return row

    async def update_user_password(self, user_id: str, new_hashed_password: str) -> bool:
        """Updates user password and timestamp."""
        now = datetime.now(timezone.utc)

        if self._is_in_memory or not self.pool:
            for u in self._in_memory_users.values():
                if u.get("id") == str(user_id):
                    u["hashed_password"] = new_hashed_password
                    u["updated_at"] = now
                    self._save_fallback()
                    return True
            return False

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE users SET hashed_password = %s, updated_at = %s WHERE id = %s",
                    (new_hashed_password, now, user_id),
                )
                return cur.rowcount > 0

    # --------------------------------------------------------------------------
    # Token Blacklist Operations (Logout / Revocation)
    # --------------------------------------------------------------------------
    async def blacklist_token(
        self,
        token_jti: str,
        user_id: Optional[str],
        expires_at: datetime,
    ) -> None:
        """Adds token jti to blacklist."""
        if self._is_in_memory or not self.pool:
            self._in_memory_blacklist.add(token_jti)
            return

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO token_blacklist (token_jti, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (token_jti) DO NOTHING
                    """,
                    (token_jti, user_id, expires_at),
                )

    async def is_token_blacklisted(self, token_jti: str) -> bool:
        """Checks if token jti is revoked."""
        if self._is_in_memory or not self.pool:
            return token_jti in self._in_memory_blacklist

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM token_blacklist WHERE token_jti = %s",
                    (token_jti,),
                )
                return (await cur.fetchone()) is not None

    # --------------------------------------------------------------------------
    # Password Reset Operations
    # --------------------------------------------------------------------------
    async def store_reset_token(
        self,
        user_id: str,
        token_str: str,
        expires_at: datetime,
    ) -> None:
        """Stores a password reset token hash."""
        token_hash = hashlib.sha256(token_str.encode()).hexdigest()

        if self._is_in_memory or not self.pool:
            self._in_memory_reset_tokens[token_hash] = {
                "user_id": user_id,
                "expires_at": expires_at,
                "is_used": False,
            }
            return

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, is_used)
                    VALUES (%s, %s, %s, FALSE)
                    """,
                    (user_id, token_hash, expires_at),
                )

    async def verify_and_consume_reset_token(self, token_str: str) -> Optional[str]:
        """Validates and marks password reset token as used, returning user_id."""
        token_hash = hashlib.sha256(token_str.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        if self._is_in_memory or not self.pool:
            rec = self._in_memory_reset_tokens.get(token_hash)
            if rec and not rec["is_used"] and rec["expires_at"] > now:
                rec["is_used"] = True
                return rec["user_id"]
            return None

        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT user_id, expires_at, is_used
                    FROM password_reset_tokens
                    WHERE token_hash = %s
                    """,
                    (token_hash,),
                )
                row = await cur.fetchone()
                if not row:
                    return None

                if row["is_used"] or row["expires_at"] <= now:
                    return None

                # Mark as used
                await cur.execute(
                    "UPDATE password_reset_tokens SET is_used = TRUE WHERE token_hash = %s",
                    (token_hash,),
                )
                return str(row["user_id"])


# Global singleton instance
auth_db_manager = AuthDatabaseManager()
