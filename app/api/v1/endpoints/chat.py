"""Chat Endpoints with PostgreSQL Chat Message History and Session Management."""

import logging
import uuid
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_postgres import PostgresChatMessageHistory
from app.core.config import settings
from app.core.database import db_manager
from app.core.observability import flush_langfuse, get_runnable_config
from app.agents.react_agent import execute_generic_chat
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    DeleteSessionRequest,
    DeleteSessionResponse,
)

from app.api.deps import get_current_active_user
from app.schemas.auth import UserResponse

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory fallback for local dev when PostgreSQL is unavailable
_in_memory_chat_history: Dict[str, List[BaseMessage]] = {}


def _normalize_session_id(session_id: str) -> str:
    """Ensures session_id is a valid UUID string required by PostgresChatMessageHistory."""
    try:
        uuid.UUID(session_id)
        return session_id
    except (ValueError, TypeError):
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, session_id))


@router.post("/generic_chat", response_model=ChatResponse, tags=["Chat"])
async def generic_chat_endpoint(
    req: ChatRequest,
    request: Request,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Processes a generic chat query maintaining conversation history in PostgreSQL."""
    try:
        raw_session_id = req.session_id or f"user-{current_user.id}-{uuid.uuid4()}"
        session_id = _normalize_session_id(raw_session_id)
        db_pool = getattr(request.app.state, "db_pool", None)
        run_config = get_runnable_config(
            session_id=session_id,
            tags=["generic_chat"],
            metadata={"user_id": current_user.id, "email": current_user.email},
        )

        if db_pool:
            async with db_pool.connection() as conn:
                history = PostgresChatMessageHistory(
                    settings.TABLE_NAME,
                    session_id,
                    async_connection=conn,
                )
                msgs = await history.aget_messages()
                logger.info(f"Loaded {len(msgs)} previous messages for session: {session_id}")

                aimessage = await execute_generic_chat(
                    user_input=req.user_input,
                    chat_history=msgs,
                    config=run_config,
                )

                await history.aadd_messages([
                    HumanMessage(content=req.user_input),
                    AIMessage(content=aimessage),
                ])
        else:
            # In-memory fallback for development/testing
            msgs = _in_memory_chat_history.get(session_id, [])
            aimessage = await execute_generic_chat(
                user_input=req.user_input,
                chat_history=msgs,
                config=run_config,
            )
            if session_id not in _in_memory_chat_history:
                _in_memory_chat_history[session_id] = []
            _in_memory_chat_history[session_id].append(HumanMessage(content=req.user_input))
            _in_memory_chat_history[session_id].append(AIMessage(content=aimessage))

        flush_langfuse()
        return ChatResponse(session_id=session_id, response=aimessage)

    except Exception as e:
        logger.error(f"Error in generic_chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process chat: {str(e)}",
        )


@router.delete("/delete_session", response_model=DeleteSessionResponse, tags=["Chat"])
async def delete_session_endpoint(
    req: DeleteSessionRequest,
    request: Request,
    current_user: UserResponse = Depends(get_current_active_user),
):
    """Deletes all messages for a specific session_id from the PostgreSQL chat history table."""
    try:
        db_pool = getattr(request.app.state, "db_pool", None)
        session_id = _normalize_session_id(req.session_id)

        if db_pool:
            deleted = await db_manager.delete_chat_session(session_id)
            if not deleted:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No chat session found with this ID",
                )

            return DeleteSessionResponse(
                message="Chat session deleted successfully",
                session_id=req.session_id,
            )
        else:
            if session_id in _in_memory_chat_history:
                del _in_memory_chat_history[session_id]
                return DeleteSessionResponse(
                    message="Chat session deleted successfully",
                    session_id=req.session_id,
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No chat session found with this ID",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}",
        )
