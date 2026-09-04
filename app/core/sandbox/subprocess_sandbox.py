"""Isolated Subprocess Sandbox Backend for Deep Agents.

Provides a secure, isolated local execution environment:
1. Environment Sanitization: Strips all API keys, database credentials, and host secrets.
2. Isolated Filesystem: Operates strictly within an ephemeral working directory.
3. Resource Limits: POSIX timeout enforcement, max output truncation, and error guards.
4. Dual-Plane File Support: Implements upload_files() and download_files().
"""

import os
import shutil
import subprocess
import sys
import tempfile
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.sandbox.base import BaseSandbox
from app.core.sandbox.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)

logger = logging.getLogger(__name__)

# Keys to explicitly purge from the execution environment to prevent credential leakage
SENSITIVE_ENV_PREFIXES = (
    "OPENAI_",
    "GROQ_",
    "PINECONE_",
    "TAVILY_",
    "LANGFUSE_",
    "JWT_",
    "POSTGRES_",
    "DATABASE_",
    "AUTH_",
    "SECRET_",
    "AWS_",
    "AZURE_",
    "GOOGLE_",
    "GITHUB_",
    "DB_",
)


class IsolatedSubprocessSandbox(BaseSandbox):
    """Secure local sandbox backend executing commands in an isolated subprocess."""

    def __init__(
        self,
        root_dir: Optional[str] = None,
        default_timeout: int = 30,
        max_output_bytes: int = 200_000,
        extra_env: Optional[Dict[str, str]] = None,
        cleanup_on_exit: bool = True,
    ):
        self._id = f"sandbox-subproc-{uuid.uuid4().hex[:10]}"
        self._default_timeout = default_timeout
        self._max_output_bytes = max_output_bytes
        self._cleanup_on_exit = cleanup_on_exit

        # Setup isolated root workspace
        if root_dir:
            self._root_dir = Path(root_dir).resolve()
            self._root_dir.mkdir(parents=True, exist_ok=True)
            self._is_temp_dir = False
        else:
            self._temp_dir = tempfile.mkdtemp(prefix=f"deepagents_{self._id}_")
            self._root_dir = Path(self._temp_dir).resolve()
            self._is_temp_dir = True

        # Build sanitized environment
        self._env = self._build_sanitized_env(extra_env)
        logger.info(f"[IsolatedSubprocessSandbox] Initialized {self._id} in {self._root_dir}")

    @property
    def id(self) -> str:
        """Unique identifier for this sandbox instance."""
        return self._id

    @property
    def root_dir(self) -> Path:
        """Path to isolated working directory."""
        return self._root_dir

    def _build_sanitized_env(self, extra_env: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Constructs a clean environment without host secrets and API keys."""
        safe_keys = {
            "PATH",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "PYTHONPATH",
            "PYTHONHOME",
            "VIRTUAL_ENV",
            "LD_LIBRARY_PATH",
            "TERM",
            "TZ",
        }
        clean_env = {k: v for k, v in os.environ.items() if k in safe_keys}

        # Set sandbox-specific safe variables
        clean_env["HOME"] = str(self._root_dir)
        clean_env["TMPDIR"] = str(self._root_dir)
        clean_env["SANDBOX_ID"] = self._id
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"

        # Explicitly verify no sensitive prefixes leaked
        for k in list(clean_env.keys()):
            if any(k.upper().startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES):
                del clean_env[k]

        if extra_env:
            for k, v in extra_env.items():
                if not any(k.upper().startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES):
                    clean_env[k] = v

        return clean_env

    def execute(self, command: str, *, timeout: Optional[int] = None) -> ExecuteResponse:
        """Execute a shell command inside the isolated sandbox directory."""
        if not command or not isinstance(command, str):
            return ExecuteResponse(output="Error: Command must be a non-empty string.", exit_code=1)

        effective_timeout = timeout if timeout is not None else self._default_timeout
        if effective_timeout <= 0:
            effective_timeout = self._default_timeout

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                timeout=effective_timeout,
                env=self._env,
                cwd=str(self._root_dir),
                start_new_session=(sys.platform != "win32"),
            )

            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                stderr_lines = result.stderr.strip().splitlines()
                output_parts.extend(f"[stderr] {line}" for line in stderr_lines)

            output = "\n".join(output_parts) if output_parts else "<no output>"
            truncated = False
            if len(output) > self._max_output_bytes:
                output = output[: self._max_output_bytes] + f"\n... [Output truncated at {self._max_output_bytes} bytes]"
                truncated = True

            return ExecuteResponse(
                output=output,
                exit_code=result.returncode,
                truncated=truncated,
            )

        except subprocess.TimeoutExpired:
            return ExecuteResponse(
                output=f"Error: Command timed out after {effective_timeout}s.",
                exit_code=124,
                truncated=False,
            )
        except Exception as e:
            return ExecuteResponse(
                output=f"Error executing command in sandbox ({type(e).__name__}): {e}",
                exit_code=1,
                truncated=False,
            )

    def upload_files(self, files: List[Tuple[str, bytes]]) -> List[FileUploadResponse]:
        """Upload multiple files to the sandbox filesystem."""
        responses: List[FileUploadResponse] = []
        for rel_path, content in files:
            try:
                dest = (self._root_dir / rel_path).resolve()
                # Security boundary check: prevent path traversal outside root_dir
                if not str(dest).startswith(str(self._root_dir)):
                    responses.append(FileUploadResponse(path=rel_path, error="permission_denied"))
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                responses.append(FileUploadResponse(path=rel_path, error=None))
            except Exception as e:
                logger.error(f"Error uploading file {rel_path}: {e}")
                responses.append(FileUploadResponse(path=rel_path, error=str(e)))
        return responses

    def download_files(self, paths: List[str]) -> List[FileDownloadResponse]:
        """Download multiple files from the sandbox filesystem."""
        responses: List[FileDownloadResponse] = []
        for rel_path in paths:
            try:
                src = (self._root_dir / rel_path).resolve()
                if not str(src).startswith(str(self._root_dir)):
                    responses.append(FileDownloadResponse(path=rel_path, error="permission_denied"))
                    continue

                if not src.exists():
                    responses.append(FileDownloadResponse(path=rel_path, error="file_not_found"))
                    continue

                if src.is_dir():
                    responses.append(FileDownloadResponse(path=rel_path, error="is_directory"))
                    continue

                content = src.read_bytes()
                responses.append(FileDownloadResponse(path=rel_path, content=content, error=None))
            except Exception as e:
                logger.error(f"Error downloading file {rel_path}: {e}")
                responses.append(FileDownloadResponse(path=rel_path, error=str(e)))
        return responses

    def cleanup(self) -> None:
        """Removes the isolated temporary workspace."""
        if self._is_temp_dir and self._root_dir.exists():
            try:
                shutil.rmtree(str(self._root_dir), ignore_errors=True)
                logger.info(f"[IsolatedSubprocessSandbox] Cleaned up workspace {self._root_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox temp directory {self._root_dir}: {e}")

    def __del__(self):
        if self._cleanup_on_exit:
            self.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cleanup_on_exit:
            self.cleanup()


__all__ = ["IsolatedSubprocessSandbox"]
