"""Base Sandbox Implementation for Deep Agents.

Inherits from `deepagents.backends.sandbox.BaseSandbox` when available,
providing standard file operations (`read_file`, `write_file`, `edit_file`,
`ls`, `grep`, `glob`, `delete`) mapped to the sandbox execution plane.
"""

import abc
import asyncio
import logging
from typing import List, Optional, Tuple, Union
from app.core.sandbox.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
    SandboxBackendProtocol,
)

logger = logging.getLogger(__name__)

try:
    from deepagents.backends.sandbox import BaseSandbox as _DeepAgentsBaseSandbox
except ImportError:
    _DeepAgentsBaseSandbox = None


if _DeepAgentsBaseSandbox is not None:
    class BaseSandbox(_DeepAgentsBaseSandbox, abc.ABC):
        """Base class for deepagents sandboxes inheriting official LangChain implementation."""
        pass
else:
    class BaseSandbox(SandboxBackendProtocol, abc.ABC):
        """Fallback Base Sandbox implementing file tools over execute()."""

        @property
        @abc.abstractmethod
        def id(self) -> str:
            """Unique identifier for this sandbox instance."""
            raise NotImplementedError

        @abc.abstractmethod
        def execute(self, command: str, *, timeout: Optional[int] = None) -> ExecuteResponse:
            """Execute a command in the sandbox environment."""
            raise NotImplementedError

        async def aexecute(self, command: str, *, timeout: Optional[int] = None) -> ExecuteResponse:
            """Async execution delegating to thread pool."""
            return await asyncio.to_thread(self.execute, command, timeout=timeout)

        @abc.abstractmethod
        def upload_files(self, files: List[Tuple[str, bytes]]) -> List[FileUploadResponse]:
            """Upload multiple files to the sandbox filesystem."""
            raise NotImplementedError

        @abc.abstractmethod
        def download_files(self, paths: List[str]) -> List[FileDownloadResponse]:
            """Download multiple files from the sandbox filesystem."""
            raise NotImplementedError

        # File Operations mapped to shell execution
        def read(self, path: str, *, offset: int = 0, limit: Optional[int] = None) -> str:
            res = self.execute(f"cat '{path}'")
            if res.exit_code != 0:
                raise FileNotFoundError(f"File '{path}' not found or error reading: {res.output}")
            content = res.output
            if offset > 0 or limit is not None:
                lines = content.splitlines(keepends=True)
                end = None if limit is None else offset + limit
                return "".join(lines[offset:end])
            return content

        def write(self, path: str, content: str) -> None:
            import base64
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            cmd = f"python3 -c \"import base64, pathlib; p = pathlib.Path('{path}'); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(base64.b64decode('{b64}'))\""
            res = self.execute(cmd)
            if res.exit_code != 0:
                raise IOError(f"Failed to write to '{path}': {res.output}")

        def ls(self, path: str = ".") -> List[str]:
            res = self.execute(f"ls -1 '{path}'")
            if res.exit_code != 0:
                return []
            return [line.strip() for line in res.output.splitlines() if line.strip()]

        def delete(self, path: str) -> bool:
            res = self.execute(f"rm -rf '{path}'")
            return res.exit_code == 0


__all__ = ["BaseSandbox"]
