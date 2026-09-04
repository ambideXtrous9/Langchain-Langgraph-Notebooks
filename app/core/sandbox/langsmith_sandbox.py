"""LangSmith Sandbox Backend Integration for Deep Agents.

Wraps `deepagents.backends.LangSmithSandbox` for enterprise users utilizing
LangSmith Cloud Sandboxes:
https://docs.langchain.com/oss/python/deepagents/sandboxes
"""

import logging
from typing import Optional
from app.core.sandbox.base import BaseSandbox
from app.core.sandbox.subprocess_sandbox import IsolatedSubprocessSandbox

logger = logging.getLogger(__name__)


def get_langsmith_sandbox(
    api_key: Optional[str] = None,
    default_timeout: int = 30,
) -> BaseSandbox:
    """Instantiates a LangSmith Sandbox backend or falls back to IsolatedSubprocessSandbox."""
    try:
        from deepagents.backends import LangSmithSandbox
        logger.info("[LangSmithSandbox] Initializing LangSmith cloud sandbox backend...")
        # If credentials and SDK are available, instantiate LangSmithSandbox
        return LangSmithSandbox()
    except Exception as e:
        logger.warning(f"[LangSmithSandbox] Could not initialize LangSmithSandbox ({e}). Falling back to IsolatedSubprocessSandbox.")
        return IsolatedSubprocessSandbox(default_timeout=default_timeout)


__all__ = ["get_langsmith_sandbox"]
