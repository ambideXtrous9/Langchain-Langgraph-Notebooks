"""Pydantic Models for SQL Agent Endpoint."""

from typing import Optional
from pydantic import BaseModel, Field


class SQLQueryRequest(BaseModel):
    """Request payload for /get_sql_query endpoint."""

    query: str = Field(..., description="Natural language question to query against the SQL database", min_length=1)
    db_uri: Optional[str] = Field(
        default=None,
        description="Optional custom database connection URI. If omitted, the default app DB is used.",
    )


class SQLQueryResponse(BaseModel):
    """Response payload for /get_sql_query endpoint."""

    user_query: str = Field(..., description="The original natural language question asked by the user")
    final_answer: str = Field(..., description="The synthesized natural language answer from the SQL agent")
    sql_query: Optional[str] = Field(None, description="The SQL query generated and executed by the agent")
    table_result: Optional[str] = Field(None, description="The raw tabular results returned from the database")
