"""Sandbox Factory Module.

Provides dynamic, pluggable instantiation of Deep Agents sandboxes
based on environment capabilities and application configuration.
"""

import logging
from typing import Optional

from app.core.config import settings
from app.core.sandbox.base import BaseSandbox
from app.core.sandbox.docker_sandbox import DockerSandbox, is_docker_available
from app.core.sandbox.langsmith_sandbox import get_langsmith_sandbox
from app.core.sandbox.subprocess_sandbox import IsolatedSubprocessSandbox

logger = logging.getLogger(__name__)


def get_sandbox_backend(
    provider: Optional[str] = None,
    root_dir: Optional[str] = None,
    timeout: Optional[int] = None,
    cleanup_on_exit: bool = True,
) -> BaseSandbox:
    """Instantiates and returns the configured sandbox backend adhering to SandboxBackendProtocol.

    Args:
        provider: "auto", "docker", "local", or "langsmith". If None, reads from settings.
        root_dir: Optional root working directory for local sandbox.
        timeout: Execution timeout in seconds.
        cleanup_on_exit: Whether to automatically delete temporary workspace / container on exit.

    Returns:
        BaseSandbox compliant with LangChain Deep Agents SandboxBackendProtocol.
    """
    selected_provider = (provider or getattr(settings, "SANDBOX_PROVIDER", "auto")).lower()
    default_timeout = timeout or getattr(settings, "SANDBOX_DEFAULT_TIMEOUT", 30)

    if selected_provider == "docker":
        return DockerSandbox(
            image=getattr(settings, "SANDBOX_DOCKER_IMAGE", "python:3.12-slim"),
            memory_limit=getattr(settings, "SANDBOX_MEMORY_LIMIT", "512m"),
            cpu_limit=getattr(settings, "SANDBOX_CPU_LIMIT", 1.0),
            default_timeout=default_timeout,
            cleanup_on_exit=cleanup_on_exit,
        )

    elif selected_provider == "langsmith":
        return get_langsmith_sandbox(default_timeout=default_timeout)

    elif selected_provider in ("local", "subprocess", "isolated"):
        return IsolatedSubprocessSandbox(
            root_dir=root_dir,
            default_timeout=default_timeout,
            cleanup_on_exit=cleanup_on_exit,
        )

    # "auto" provider:
    # In containerized/CI environments, prefer IsolatedSubprocessSandbox for instant execution
    # with zero overhead; DockerSandbox is used when Docker daemon is available and accessible.
    if is_docker_available():
        return DockerSandbox(
            image=getattr(settings, "SANDBOX_DOCKER_IMAGE", "python:3.12-slim"),
            memory_limit=getattr(settings, "SANDBOX_MEMORY_LIMIT", "512m"),
            cpu_limit=getattr(settings, "SANDBOX_CPU_LIMIT", 1.0),
            default_timeout=default_timeout,
            cleanup_on_exit=cleanup_on_exit,
        )

    return IsolatedSubprocessSandbox(
        root_dir=root_dir,
        default_timeout=default_timeout,
        cleanup_on_exit=cleanup_on_exit,
    )


__all__ = ["get_sandbox_backend"]
