"""Sandbox Backend Protocol and Execution Result Interfaces for Deep Agents.

Adheres strictly to the LangChain Deep Agents `SandboxBackendProtocol` contract:
https://docs.langchain.com/oss/python/deepagents/sandboxes
"""

from typing import List, Literal, Optional, Tuple, Union
from dataclasses import dataclass

try:
    from deepagents.backends.protocol import (
        ExecuteResponse,
        FileUploadResponse,
        FileDownloadResponse,
        SandboxBackendProtocol,
    )
except ImportError:
    # Graceful fallback definitions matching deepagents.backends.protocol exactly
    @dataclass
    class ExecuteResponse:
        """Result of code or bash command execution in the sandbox."""
        output: str
        exit_code: Optional[int] = None
        truncated: bool = False

    @dataclass
    class FileUploadResponse:
        """Result of an individual file upload attempt."""
        path: str
        error: Optional[Union[Literal["file_not_found", "permission_denied", "is_directory", "invalid_path"], str]] = None

    @dataclass
    class FileDownloadResponse:
        """Result of an individual file download attempt."""
        path: str
        content: Optional[bytes] = None
        error: Optional[Union[Literal["file_not_found", "permission_denied", "is_directory", "invalid_path"], str]] = None

    class SandboxBackendProtocol:
        """Protocol for isolated sandbox backends executing shell & code."""
        @property
        def id(self) -> str:
            raise NotImplementedError

        def execute(self, command: str, *, timeout: Optional[int] = None) -> ExecuteResponse:
            raise NotImplementedError

        async def aexecute(self, command: str, *, timeout: Optional[int] = None) -> ExecuteResponse:
            raise NotImplementedError


__all__ = [
    "ExecuteResponse",
    "FileUploadResponse",
    "FileDownloadResponse",
    "SandboxBackendProtocol",
]
