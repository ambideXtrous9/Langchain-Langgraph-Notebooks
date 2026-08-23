"""SQL Agent Endpoint for Natural Language Database Queries."""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.agents.sql_agent import execute_sql_query
from app.api.deps import get_current_active_user
from app.core.observability import flush_langfuse, get_runnable_config
from app.schemas.auth import UserResponse
from app.schemas.sql import SQLQueryRequest, SQLQueryResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/get_sql_query", response_model=SQLQueryResponse, tags=["SQL Agent"])
async def get_sql_query_endpoint(
    request: SQLQueryRequest,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Executes a natural language question against the SQL database and returns query details."""
    try:
        run_config = get_runnable_config(
            tags=["sql_agent", "text_to_sql"],
            metadata={"user_id": current_user.id, "email": current_user.email},
        )

        final_answer, sql_query, table_result = execute_sql_query(
            query=request.query,
            db_uri=request.db_uri,
            config=run_config,
        )

        flush_langfuse()

        if final_answer is None or "Failed to execute" in final_answer:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=final_answer or "Failed to generate SQL query.",
            )

        return SQLQueryResponse(
            user_query=request.query,
            final_answer=final_answer,
            sql_query=sql_query,
            table_result=table_result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SQL query endpoint exception: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SQL Agent processing error: {str(e)}",
        )
