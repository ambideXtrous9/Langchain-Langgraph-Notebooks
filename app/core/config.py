"""Application Configuration Module using Pydantic Settings."""

import json
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    PROJECT_NAME: str = "Enterprise LangGraph Agent API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Security & CORS ---
    CORS_ORIGINS: Union[List[str], str] = ["*"]
    ALLOWED_HOSTS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", "ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # --- Groq & LLM Settings ---
    GROQ_API_KEY: str = Field(default="", description="Groq API Key")
    OPENAI_API_KEY: str = Field(default="", description="Optional fallback API Key")
    DEFAULT_MODEL: str = "openai/gpt-oss-120b"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_RETRIES: int = 3

    # --- Per-Agent Token Limits (Token Budget Controls) ---
    PLANNER_MAX_TOKENS: int = 800
    APPROVER_MAX_TOKENS: int = 500
    SYNTHESIZER_MAX_TOKENS: int = 1500
    FACT_CRITIC_MAX_TOKENS: int = 600
    STYLE_CRITIC_MAX_TOKENS: int = 600
    PUBLISHER_MAX_TOKENS: int = 2500
    GENERIC_CHAT_MAX_TOKENS: int = 1500

    # --- Database Settings (PostgreSQL: agent_db) ---
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/agent_db",
        description="PostgreSQL Database Connection URI for Agents and LangGraph",
    )
    DB_URI: str = Field(
        default="",
        description="Alternative alias for DATABASE_URL as in AgentNotes.ipynb",
    )
    TABLE_NAME: str = "chat_message_history"
    DB_POOL_MIN_SIZE: int = 2
    DB_POOL_MAX_SIZE: int = 10
    DB_POOL_TIMEOUT: int = 3

    # --- Authentication & JWT Settings (PostgreSQL: auth_db) ---
    AUTH_DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/auth_db",
        description="PostgreSQL Connection URI for Authentication and Users (auth_db)",
    )
    AUTH_DB_POOL_MIN_SIZE: int = 2
    AUTH_DB_POOL_MAX_SIZE: int = 10
    JWT_SECRET_KEY: str = Field(
        default="enterprise-langgraph-secret-key-32-chars-minimum-prod",
        description="Secret key for signing JWT tokens",
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    RESET_TOKEN_EXPIRE_MINUTES: int = 15

    # --- External Search Tools ---
    TAVILY_API_KEY: str = Field(default="", description="Tavily Search API Key")
    ENABLE_DDG_SEARCH: bool = True

    # --- Langfuse Observability ---
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # --- MCP (Model Context Protocol) Settings ---
    ENABLE_AIRBNB_MCP: bool = True
    AIRBNB_MCP_COMMAND: str = "npx"
    AIRBNB_MCP_ARGS: Union[List[str], str] = ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
    WEATHER_API_KEY: str = Field(default="", description="WeatherAPI.com API Key")
    AIRBNB_AGENT_MAX_TOKENS: int = 1500
    WEATHER_AGENT_MAX_TOKENS: int = 1000
    TOUR_AGENT_MAX_TOKENS: int = 2500

    # --- Hybrid Retriever & Reranking ---
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    BM25_DEFAULT_WEIGHT: float = 0.3
    RERANKER_MIN_SCORE: float = 0.1
    DEFAULT_TOP_K: int = 5

    @property
    def effective_db_uri(self) -> str:
        """Returns the active DB URI, falling back to DATABASE_URL if DB_URI is empty."""
        return self.DB_URI.strip() if self.DB_URI.strip() else self.DATABASE_URL.strip()


settings = Settings()
