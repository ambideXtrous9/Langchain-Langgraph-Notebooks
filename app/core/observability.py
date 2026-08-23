"""Observability and Tracing module with Langfuse integration."""

import logging
from typing import Any, Dict, List, Optional
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler
from app.core.config import settings

logger = logging.getLogger(__name__)

_langfuse_client = None


def init_langfuse() -> Optional[Any]:
    """Initializes and verifies the Langfuse client singleton during application startup."""
    global _langfuse_client
    if not settings.LANGFUSE_ENABLED:
        logger.info("Langfuse observability is disabled.")
        return None

    pub_key = settings.LANGFUSE_PUBLIC_KEY.strip("\"' ")
    sec_key = settings.LANGFUSE_SECRET_KEY.strip("\"' ")
    host = settings.LANGFUSE_HOST.strip("\"' ")

    if not pub_key or not sec_key:
        logger.warning("Langfuse credentials missing in environment. Tracing will be disabled.")
        return None

    try:
        # Initialize client with explicit credentials and host
        Langfuse(
            public_key=pub_key,
            secret_key=sec_key,
            host=host,
        )
        _langfuse_client = get_client()

        # Verify connection
        if not _langfuse_client.auth_check():
            logger.error("Langfuse authentication failed. Please check credentials and host.")
            _langfuse_client = None
            return None

        logger.info("Langfuse client authenticated and initialized successfully.")
        return _langfuse_client
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse client: {e}")
        _langfuse_client = None
        return None


def get_langfuse_handler() -> Optional[CallbackHandler]:
    """Instantiates a fresh Langfuse LangChain CallbackHandler for execution runs."""
    global _langfuse_client
    if _langfuse_client is None and settings.LANGFUSE_ENABLED:
        init_langfuse()

    if _langfuse_client is None:
        return None

    try:
        return CallbackHandler()
    except Exception as e:
        logger.error(f"Failed to create Langfuse CallbackHandler: {e}")
        return None


def flush_langfuse() -> None:
    """Flushes queued traces to the Langfuse cloud server."""
    global _langfuse_client
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
        except Exception as e:
            logger.debug(f"Langfuse flush error: {e}")


def get_runnable_config(
    thread_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> RunnableConfig:
    """Builds a standardized RunnableConfig for LangGraph and LangChain invocations.

    Includes thread_id, session_id in metadata/tags, and the Langfuse callback handler if active.
    """
    config_tags = list(tags) if tags else []
    config_metadata = dict(metadata) if metadata else {}

    if session_id:
        config_metadata["session_id"] = session_id
        config_metadata["langfuse_session_id"] = session_id
        config_tags.append(f"session:{session_id}")

    if thread_id:
        config_metadata["thread_id"] = thread_id
        config_metadata["langfuse_session_id"] = thread_id
        config_tags.append(f"thread:{thread_id}")

    config: RunnableConfig = {
        "configurable": {},
        "tags": config_tags,
        "metadata": config_metadata,
        "callbacks": [],
    }

    if thread_id:
        config["configurable"]["thread_id"] = thread_id

    handler = get_langfuse_handler()
    if handler:
        config["callbacks"].append(handler)

    return config
